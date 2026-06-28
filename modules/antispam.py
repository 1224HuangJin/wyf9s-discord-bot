from datetime import datetime, timedelta, timezone
import typing as t

from loguru import logger as l
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

    def _is_ignored(
        self, member: discord.Member, rule: _SpamCatcherRuleConfigModel
    ) -> bool:
        ignored_role_ids = self._parse_role_ids(rule.ignored_roles, member.guild)
        if not ignored_role_ids:
            return False
        member_role_ids = {role.id for role in member.roles}
        return bool(member_role_ids & ignored_role_ids)

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
            write_audit=False,
        )
        return result.replace(f"\n-# {CLEAR_MESSAGE_MARKER}", "").replace(
            CLEAR_MESSAGE_MARKER, ""
        )

    @staticmethod
    def _build_public_notice(
        member: discord.Member,
        category: str,
        action_label: str,
        should_ping: bool,
    ) -> str:
        """构建发往频道的双语提示 (中文一行, 英文一行, 合并为单条消息)"""
        mention = member.mention
        if should_ping:
            # 疑似被盗 (mute)
            return (
                f":rotating_light: {mention} 你的账号疑似被盗，已被临时禁言，请联系管理员。\n"
                f":rotating_light: {mention} Your account looks compromised and has been "
                f"temporarily muted. Please contact an admin."
            )
        # 陌生账号 (kick/ban) 公开记录
        return (
            f":rotating_light: 已触发 antispam: {mention} -> **{category}/{action_label}**\n"
            f":rotating_light: antispam triggered: {mention} -> **{category}/{action_label}**"
        )

    @staticmethod
    def _action_permission(action: str | int) -> tuple[str, str]:
        """返回 (动作类型, 所需 Discord 权限名称)"""
        if action == "kick":
            return "kick", "kick_members"
        if action == "ban":
            return "ban", "ban_members"
        return "mute", "moderate_members"

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

    async def _audit_failure(
        self,
        *,
        actor: discord.User,
        guild: discord.Guild,
        channel: discord.TextChannel,
        target: discord.Member,
        category: str,
        action_type: str,
        reason: str,
        error: str,
    ) -> None:
        """将自动化操作失败 (含权限错误) 写入 audit log 频道"""
        if not self.audit:
            return
        await self.audit.log(
            action="antispam-auto-catch",
            user=actor,
            guild=guild,
            channel=channel,
            detail=(
                f"目标: {target} ({target.id})"
                f"\n分类: {category}"
                f"\n动作: {action_type}"
                f"\n失败原因: {reason}"
                f"\n错误信息: {error[:400]}"
            ),
            success=False,
            auto=True,
        )

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
        except discord.Forbidden as e:
            action_type, perm_name = self._action_permission(action)
            me = guild.me
            has_perm = bool(getattr(guild.me.guild_permissions, perm_name, False))
            if has_perm:
                # 拥有权限却仍被拒绝, 几乎可以确定是身份组层级问题
                reason = (
                    f"机器人已有 {perm_name} 权限, 但目标的最高身份组 "
                    f"({target.top_role.name}) 不低于机器人的最高身份组 "
                    f"({me.top_role.name}), 请将机器人身份组拖到目标之上"
                )
            else:
                reason = f"机器人缺少 {perm_name} 权限"
            l.warning(
                f"[antispam] 权限不足, 无法对 {target} ({target.id}) 执行 "
                f"{action_type} (需要权限: {perm_name}): {reason} | {e}"
            )
            await self._audit_failure(
                actor=actor,
                guild=guild,
                channel=trigger_channel,
                target=target,
                category=category,
                action_type=action_type,
                reason=f"权限不足 (需要 {perm_name}): {reason}",
                error=str(e),
            )
            return False, category, "failed", False
        except discord.HTTPException as e:
            action_type, _ = self._action_permission(action)
            l.warning(
                f"[antispam] 执行 {action_type} 对 {target} ({target.id}) 时出错: {e}"
            )
            await self._audit_failure(
                actor=actor,
                guild=guild,
                channel=trigger_channel,
                target=target,
                category=category,
                action_type=action_type,
                reason="执行操作时发生 HTTP 错误",
                error=str(e),
            )
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
                auto=True,
            )

        return True, category, action_label, should_ping

    async def _handle_auto_message(self, message: discord.Message):
        try:
            await self._handle_auto_message_inner(message)
        except Exception as e:
            l.exception(f"[antispam] 处理消息时出错: {e}")

    async def _handle_auto_message_inner(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild is None:
            return

        rule = self._resolve_rule(message.channel.id)
        if rule is None:
            return

        l.debug(
            f"[antispam] 命中规则: channel={message.channel.id} "
            f"author={message.author} ({message.author.id})"
        )

        if not isinstance(
            message.channel,
            (discord.TextChannel, discord.Thread, discord.VoiceChannel),
        ):
            l.warning(
                f"[antispam] 频道类型不受支持: channel={message.channel.id} "
                f"type={type(message.channel).__name__}"
            )
            return
        if not isinstance(message.author, discord.Member):
            l.warning(
                f"[antispam] 消息作者不是 Member (无法处理): author={message.author}"
            )
            return

        if self._is_ignored(message.author, rule):
            l.debug(
                f"[antispam] 成员拥有忽略角色, 跳过: {message.author} ({message.author.id})"
            )
            return

        actor = self.client.user
        if not isinstance(actor, discord.ClientUser):
            l.warning("[antispam] client.user 不可用, 跳过处理")
            return

        ok, category, action_label, should_ping = await self._process_target(
            actor=t.cast(discord.User, actor),
            guild=message.guild,
            trigger_channel=t.cast(discord.TextChannel, message.channel),
            target=message.author,
            rule=rule,
        )
        if not ok:
            l.warning(
                f"[antispam] 处理失败 (可能权限不足): target={message.author} "
                f"({message.author.id}) category={category}"
            )
            return

        l.info(
            f"[antispam] 已处理: {message.author} ({message.author.id}) "
            f"-> {category}/{action_label}"
        )

        if rule.public_log:
            notice = self._build_public_notice(
                member=message.author,
                category=category,
                action_label=action_label,
                should_ping=should_ping,
            )
            await message.channel.send(notice)
