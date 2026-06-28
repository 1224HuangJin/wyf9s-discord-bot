from datetime import datetime, timedelta, timezone
import typing as t

import discord
from discord.ext import commands

from config import ConfigModel, _SpamCatcherRuleConfigModel
from modules.audit import AuditLogger
from modules.clear_message import CLEAR_MESSAGE_MARKER, ClearMessageService


class AntiSpamModule:
    c: ConfigModel
    client: commands.Bot
    audit: AuditLogger | None

    def __init__(
        self,
        config: ConfigModel,
        client: commands.Bot,
        audit: AuditLogger | None,
    ):
        self.c = config
        self.client = client
        self.audit = audit
        self.clear_message = ClearMessageService(
            config=config, client=client, audit=audit
        )

        @client.listen("on_message")
        async def antispam_auto_handler(message: discord.Message):
            await self._handle_auto_message(message)

    def _resolve_rule(self, channel_id: int) -> _SpamCatcherRuleConfigModel | None:
        return self.c.antispam.spam_catcher.get(
            channel_id, self.c.antispam.spam_catcher.get(str(channel_id))
        )

    @staticmethod
    def _parse_role_ids(
        values: list[int | str], guild: discord.Guild | None = None
    ) -> set[int]:
        role_ids: set[int] = set()
        name_to_ids: dict[str, set[int]] | None = None
        for value in values:
            if isinstance(value, int):
                role_ids.add(value)
            elif isinstance(value, str) and value.isdigit():
                role_ids.add(int(value))
            elif isinstance(value, str) and guild is not None:
                # 按身份组名称解析 (可能存在同名身份组)
                if name_to_ids is None:
                    name_to_ids = {}
                    for role in guild.roles:
                        name_to_ids.setdefault(role.name, set()).add(role.id)
                role_ids.update(name_to_ids.get(value, set()))
        return role_ids

    def _is_spammer(
        self, member: discord.Member, rule: _SpamCatcherRuleConfigModel
    ) -> bool:
        role_ids = {role.id for role in member.roles if not role.is_default()}
        if not role_ids:
            return True
        stranger_role_ids = self._parse_role_ids(rule.stranger_roles, member.guild)
        return bool(stranger_role_ids) and role_ids.issubset(stranger_role_ids)

    async def _cleanup_messages(
        self,
        actor: discord.User,
        guild: discord.Guild,
        channel: discord.TextChannel,
        target: discord.Member,
        within_minutes: int | None,
    ) -> str | None:
        if within_minutes is None or within_minutes <= 0:
            return None
        result = await self.clear_message.do_clear_message(
            author=actor,
            guild=guild,
            channel=channel,
            user=t.cast(discord.User, target),
            within_minutes=within_minutes,
            scope="server",
        )
        return result.replace(f"\n-# {CLEAR_MESSAGE_MARKER}", "").replace(
            CLEAR_MESSAGE_MARKER, ""
        )

    async def _execute_action(
        self,
        guild: discord.Guild,
        target: discord.Member,
        category: str,
        action: str | int,
    ) -> tuple[str, bool]:
        should_ping = False
        if action == "kick":
            await target.kick(reason=f"antispam/{category}")
            return "kick", should_ping
        if action == "ban":
            await guild.ban(target, reason=f"antispam/{category}")
            return "ban", should_ping

        mute_minutes = 60
        if isinstance(action, int):
            mute_minutes = max(1, action)
        until = datetime.now(timezone.utc) + timedelta(minutes=mute_minutes)
        await target.timeout(until, reason=f"antispam/{category}")
        should_ping = True
        return f"mute {mute_minutes}m", should_ping

    async def _process_target(
        self,
        *,
        actor: discord.User,
        guild: discord.Guild,
        trigger_channel: discord.TextChannel,
        target: discord.Member,
        rule: _SpamCatcherRuleConfigModel,
    ) -> tuple[bool, str, str, bool]:
        is_spammer = self._is_spammer(target, rule)
        category = "spammer" if is_spammer else "hacked"
        action: str | int = rule.spammer if is_spammer else rule.hacked

        try:
            action_label, should_ping = await self._execute_action(
                guild=guild,
                target=target,
                category=category,
                action=action,
            )
        except (discord.Forbidden, discord.HTTPException):
            return False, category, "failed", False

        clear_result = await self._cleanup_messages(
            actor=actor,
            guild=guild,
            channel=trigger_channel,
            target=target,
            within_minutes=rule.clear_message,
        )

        if self.audit:
            await self.audit.log(
                action="antispam-auto-catch",
                user=actor,
                guild=guild,
                channel=trigger_channel,
                detail=(
                    f"目标: {target} ({target.id})"
                    f"\n分类: {category}"
                    f"\n动作: {action_label}"
                    f"\n清理分钟: {rule.clear_message}"
                    + (f"\n清理结果: {clear_result[:900]}" if clear_result else "")
                ),
                success=True,
            )

        return True, category, action_label, should_ping

    async def _handle_auto_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild is None:
            return
        if not isinstance(message.channel, discord.TextChannel):
            return
        if not isinstance(message.author, discord.Member):
            return

        rule = self._resolve_rule(message.channel.id)
        if rule is None:
            return

        actor = self.client.user
        if not isinstance(actor, discord.ClientUser):
            return

        ok, category, action_label, should_ping = await self._process_target(
            actor=t.cast(discord.User, actor),
            guild=message.guild,
            trigger_channel=message.channel,
            target=message.author,
            rule=rule,
        )
        if not ok:
            return

        if rule.public_log:
            await message.channel.send(
                f":rotating_light: 已触发 antispam: {message.author.mention} -> **{category}/{action_label}**"
            )
        if should_ping:
            await message.channel.send(
                f"{message.author.mention} 你的账号疑似被盗，已被临时禁言，请联系管理员。"
            )
