from datetime import datetime, timedelta, timezone
import typing as t

from loguru import logger as l
import discord
from discord.ext import commands

from config import _SpamCatcherRuleConfigModel
from modules.audit import AuditLogger
from modules.clear_message import CLEAR_MESSAGE_MARKER, ClearMessageService


class AntiSpamCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.c = bot.config  # ty:ignore[unresolved-attribute]
        self.audit: AuditLogger | None = getattr(bot, "audit", None)
        self.clear_message = ClearMessageService(
            config=self.c, client=bot, audit=self.audit
        )

    @commands.Cog.listener("on_message")
    async def antispam_auto_handler(self, message: discord.Message):
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
        mention = member.mention
        if should_ping:
            return (
                f":rotating_light: {mention} Account looks compromised "
                f"- temporarily muted. Contact an admin.\n"
                f":rotating_light: {mention} 账号疑似被盗，已被临时禁言，请联系管理员。"
            )
        return (
            f":rotating_light: Antispam triggered: {mention} -> **{category}/{action_label}**\n"
            f":rotating_light: 已触发 antispam: {mention} -> **{category}/{action_label}**"
        )

    @staticmethod
    def _action_permission(action: str | int) -> tuple[str, str]:
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
        if not self.audit:
            return
        await self.audit.log(
            action="antispam-auto-catch",
            user=actor,
            guild=guild,
            channel=channel,
            detail=(
                f"Target: {target} ({target.id})"
                f"\nCategory: {category}"
                f"\nAction: {action_type}"
                f"\nReason: {reason}"
                f"\nError: {error[:400]}"
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
                guild=guild, target=target, category=category, action=action
            )
        except discord.Forbidden as e:
            action_type, perm_name = self._action_permission(action)
            me = guild.me
            has_perm = bool(getattr(me.guild_permissions, perm_name, False))
            if has_perm:
                reason = (
                    f"Bot has {perm_name} but target's top role "
                    f"({target.top_role.name}) is higher or equal to bot's "
                    f"({me.top_role.name}), move bot role above target"
                )
            else:
                reason = f"Bot lacks {perm_name} permission"
            l.warning(
                f"[antispam] Cannot {action_type} {target} ({target.id}): {reason} | {e}"
            )
            await self._audit_failure(
                actor=actor,
                guild=guild,
                channel=trigger_channel,
                target=target,
                category=category,
                action_type=action_type,
                reason=f"Permission ({perm_name}): {reason}",
                error=str(e),
            )
            return False, category, "failed", False
        except discord.HTTPException as e:
            action_type, _ = self._action_permission(action)
            l.warning(f"[antispam] HTTP error {action_type} on {target}: {e}")
            await self._audit_failure(
                actor=actor,
                guild=guild,
                channel=trigger_channel,
                target=target,
                category=category,
                action_type=action_type,
                reason="HTTP error during action",
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
                    f"Target: {target} ({target.id})"
                    f"\nCategory: {category}"
                    f"\nAction: {action_label}"
                    f"\nCleanup mins: {rule.clear_message}"
                    + (f"\nCleanup: {clear_result[:900]}" if clear_result else "")
                ),
                success=True,
                auto=True,
            )

        return True, category, action_label, should_ping

    async def _handle_auto_message(self, message: discord.Message):
        try:
            await self._handle_auto_message_inner(message)
        except Exception as e:
            l.exception(f"[antispam] Error handling message: {e}")

    async def _handle_auto_message_inner(self, message: discord.Message):
        if message.author.bot:
            return
        if message.guild is None:
            return

        rule = self._resolve_rule(message.channel.id)
        if rule is None:
            return

        l.debug(
            f"[antispam] Rule hit: channel={message.channel.id} "
            f"author={message.author} ({message.author.id})"
        )

        if not isinstance(
            message.channel,
            (discord.TextChannel, discord.Thread, discord.VoiceChannel),
        ):
            l.warning(
                f"[antispam] Unsupported channel type: channel={message.channel.id}"
            )
            return
        if not isinstance(message.author, discord.Member):
            l.warning(f"[antispam] Author is not Member: {message.author}")
            return

        if self._is_ignored(message.author, rule):
            l.debug(f"[antispam] Member has ignored role, skipping: {message.author}")
            return

        actor = self.bot.user
        if not isinstance(actor, discord.ClientUser):
            l.warning("[antispam] client.user unavailable")
            return

        ok, category, action_label, should_ping = await self._process_target(
            actor=t.cast(discord.User, actor),
            guild=message.guild,
            trigger_channel=t.cast(discord.TextChannel, message.channel),
            target=message.author,
            rule=rule,
        )
        if not ok:
            l.warning(f"[antispam] Failed: target={message.author} category={category}")
            return

        l.info(f"[antispam] Handled: {message.author} -> {category}/{action_label}")

        if rule.public_log:
            notice = self._build_public_notice(
                member=message.author,
                category=category,
                action_label=action_label,
                should_ping=should_ping,
            )
            await message.channel.send(notice)


async def setup(bot: commands.Bot):
    if bot.config.antispam.enabled:  # ty:ignore[unresolved-attribute]
        await bot.add_cog(AntiSpamCog(bot))
        l.info("AntiSpamCog loaded.")
