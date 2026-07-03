from datetime import datetime, timezone

from loguru import logger as l
import discord
from discord.ext import commands

from config import ConfigModel
from i18n import t as _t
from lang_store import LangStore


class AntispamActionView(discord.ui.View):
    def __init__(
        self,
        *,
        guild_id: int,
        target_id: int,
        target_name: str,
        action_label: str,
        lang: str,
        lang_store: LangStore,
    ):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.target_id = target_id
        self.target_name = target_name
        self.action_label = action_label
        self.lang = lang
        self.lang_store = lang_store

        if "ban" in action_label.lower():
            self._add_btn_unban()
        elif "mute" in action_label.lower():
            self._add_btn_unmute()

    def _add_btn_unban(self):
        btn = discord.ui.Button(
            label=_t("antispam.snapshot_button_unban", self.lang),
            style=discord.ButtonStyle.danger,
            custom_id=f"antispam:unban:{self.guild_id}:{self.target_id}",
        )
        btn.callback = self._handle_unban  # ty:ignore[invalid-assignment]
        self.add_item(btn)

    def _add_btn_unmute(self):
        btn = discord.ui.Button(
            label=_t("antispam.snapshot_button_unmute", self.lang),
            style=discord.ButtonStyle.danger,
            custom_id=f"antispam:unmute:{self.guild_id}:{self.target_id}",
        )
        btn.callback = self._handle_unmute  # ty:ignore[invalid-assignment]
        self.add_item(btn)

    async def _resolve_lang(self, interaction: discord.Interaction) -> str:
        return self.lang_store.resolve(
            interaction.user.id, interaction.guild.id if interaction.guild else None
        )

    async def _finalize_button(
        self, interaction: discord.Interaction, lang: str, action_label: str
    ) -> None:
        """成功后: 禁用按钮并改为 '已由 {moderator} {action}', 更新原消息"""
        actor = getattr(interaction.user, "display_name", str(interaction.user))
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
                item.label = _t(
                    "antispam.snapshot_button_done",
                    lang,
                    actor=actor,
                    action=action_label,
                )[:80]
        self.stop()
        try:
            await interaction.response.edit_message(view=self)
        except discord.HTTPException:
            pass

    async def _handle_unban(self, interaction: discord.Interaction):
        lang = await self._resolve_lang(interaction)
        guild = interaction.client.get_guild(self.guild_id)
        if guild is None:
            await interaction.response.send_message(
                _t("antispam.guild_not_found", lang), ephemeral=True
            )
            return
        if not (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.ban_members
        ):
            await interaction.response.send_message(
                _t("antispam.snapshot_button_no_permission", lang),
                ephemeral=True,
            )
            return
        try:
            user = await interaction.client.fetch_user(self.target_id)
            await guild.unban(
                user,
                reason=_t("antispam.unban_reason", lang, actor=str(interaction.user)),
            )
            await self._finalize_button(
                interaction, lang, _t("antispam.action_unban", lang)
            )
        except discord.NotFound:
            await interaction.response.send_message(
                _t("antispam.user_not_found_ban", lang), ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                _t("antispam.snapshot_button_no_permission", lang),
                ephemeral=True,
            )
        except Exception as e:
            await interaction.response.send_message(
                _t("antispam.snapshot_button_failed", lang, error=str(e)[:400]),
                ephemeral=True,
            )

    async def _handle_unmute(self, interaction: discord.Interaction):
        lang = await self._resolve_lang(interaction)
        guild = interaction.client.get_guild(self.guild_id)
        if guild is None:
            await interaction.response.send_message(
                _t("antispam.guild_not_found", lang), ephemeral=True
            )
            return
        if not (
            isinstance(interaction.user, discord.Member)
            and interaction.user.guild_permissions.moderate_members
        ):
            await interaction.response.send_message(
                _t("antispam.snapshot_button_no_permission", lang),
                ephemeral=True,
            )
            return
        try:
            member = await guild.fetch_member(self.target_id)
            await member.timeout(
                None,
                reason=_t("antispam.unmute_reason", lang, actor=str(interaction.user)),
            )
            await self._finalize_button(
                interaction, lang, _t("antispam.action_unmute", lang)
            )
        except discord.NotFound:
            await interaction.response.send_message(
                _t("antispam.member_not_found", lang), ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                _t("antispam.snapshot_button_no_permission", lang),
                ephemeral=True,
            )
        except Exception as e:
            await interaction.response.send_message(
                _t("antispam.snapshot_button_failed", lang, error=str(e)[:400]),
                ephemeral=True,
            )


class AuditLogger:
    c: ConfigModel
    client: commands.Bot
    lang_store: LangStore

    def __init__(
        self, config: ConfigModel, client: commands.Bot, lang_store: LangStore
    ):
        self.c = config
        self.client = client
        self.lang_store = lang_store

    def _resolve_targets(
        self, guild: discord.Guild | None, category: str = "action"
    ) -> list[int]:
        """
        解析某一类别 (action / audit) 的日志目标频道

        :param category: "action" (普通指令日志) 或 "audit" (审计日志)
        """
        targets: list[int] = []
        seen: set[int] = set()

        global_ch = (
            self.c.audit.global_action
            if category == "action"
            else self.c.audit.global_audit
        )
        if global_ch:
            targets.append(global_ch)
            seen.add(global_ch)

        if guild is not None:
            guild_conf = self.c.audit.guilds.get(
                guild.id, self.c.audit.guilds.get(str(guild.id))
            )
            if guild_conf is not None:
                ch = guild_conf.action if category == "action" else guild_conf.audit
                if ch is not None and ch not in seen:
                    targets.append(ch)

        return targets

    def _resolve_lang(self, guild: discord.Guild | None) -> str:
        if guild is not None:
            return self.lang_store.resolve(0, guild.id)
        return "zh"

    def _build_embed(
        self,
        *,
        lang: str,
        action: str,
        user: discord.User | discord.Member,
        guild: discord.Guild | None,
        channel: discord.abc.GuildChannel
        | discord.abc.PrivateChannel
        | discord.Thread
        | None,
        detail: str,
        success: bool,
        auto: bool,
    ) -> discord.Embed:
        color = discord.Color.green() if success else discord.Color.red()

        if auto:
            title_key = "audit.title_auto_ok" if success else "audit.title_auto_fail"
        else:
            title_key = (
                "audit.title_manual_ok" if success else "audit.title_manual_fail"
            )

        embed = discord.Embed(
            title=_t(title_key, lang),
            color=color,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(
            name=_t("audit.field_action", lang),
            value=f"`{action}`",
            inline=True,
        )
        embed.add_field(
            name=_t("audit.field_actor", lang),
            value=f"{user.mention} (`{user.name}` / `{user.id}`)",
            inline=True,
        )
        if guild is not None:
            embed.add_field(
                name=_t("audit.field_guild", lang),
                value=f"`{guild.name}` (`{guild.id}`)",
                inline=False,
            )
        if channel is not None:
            channel_repr = getattr(channel, "mention", None) or getattr(
                channel, "name", str(channel)
            )
            embed.add_field(
                name=_t("audit.field_channel", lang),
                value=str(channel_repr),
                inline=False,
            )
        if detail:
            embed.add_field(
                name=_t("audit.field_detail", lang),
                value=detail[:1024],
                inline=False,
            )
        return embed

    async def _send_to_channel(
        self,
        channel_id: int,
        *,
        embed: discord.Embed | None = None,
        view: discord.ui.View | None = None,
    ):
        try:
            target = self.client.get_channel(channel_id)
            if target is None:
                target = await self.client.fetch_channel(channel_id)
            if not isinstance(target, (discord.TextChannel, discord.Thread)):
                l.warning(
                    f"[audit] Log channel {channel_id} is not a text channel, skipped"
                )
                return None
            kwargs = {}
            if embed:
                kwargs["embed"] = embed
            if view:
                kwargs["view"] = view
            return await target.send(**kwargs)  # ty:ignore[no-matching-overload]
        except discord.Forbidden:
            l.warning(f"[audit] No permission to send to log channel {channel_id}")
        except discord.NotFound:
            l.warning(f"[audit] Log channel {channel_id} not found")
        except Exception as e:
            l.warning(f"[audit] Error sending log to channel {channel_id}: {e}")
        return None

    async def log(
        self,
        *,
        action: str,
        user: discord.User | discord.Member,
        guild: discord.Guild | None = None,
        channel: discord.abc.GuildChannel
        | discord.abc.PrivateChannel
        | discord.Thread
        | None = None,
        detail: str = "",
        success: bool = True,
        auto: bool = False,
        category: str = "action",
    ):
        if not self.c.audit.enabled:
            return

        targets = self._resolve_targets(guild, category)
        if not targets:
            return

        lang = self._resolve_lang(guild)
        embed = self._build_embed(
            lang=lang,
            action=action,
            user=user,
            guild=guild,
            channel=channel,
            detail=detail,
            success=success,
            auto=auto,
        )

        for channel_id in targets:
            await self._send_to_channel(channel_id, embed=embed)

    @staticmethod
    def _build_message_snapshot_embed(
        message: discord.Message,
        lang: str,
    ) -> discord.Embed:
        embed = discord.Embed(
            title=_t("antispam.snapshot_title", lang),
            color=discord.Color.blue(),
            timestamp=message.created_at,
        )

        content = message.content or ""
        if not content and message.embeds:
            content = _t("audit.snapshot_content_embed", lang)
        if not content and message.attachments:
            content = _t("audit.snapshot_content_attachment", lang)
        if not content:
            content = _t("antispam.snapshot_content_empty", lang)

        embed.add_field(
            name=_t("audit.snapshot_field_content", lang),
            value=content[:1024] if len(content) <= 1024 else content[:1021] + "...",
            inline=False,
        )

        embed.add_field(
            name=_t("audit.snapshot_field_author", lang),
            value=f"{message.author} (`{message.author.id}`)",
            inline=True,
        )
        embed.add_field(
            name=_t("antispam.snapshot_field_channel", lang),
            value=f"{message.channel} (`{message.channel.id}`)",
            inline=True,
        )

        attachment_urls = [a.url for a in message.attachments]
        sticker_urls = [s.url for s in message.stickers if hasattr(s, "url") and s.url]
        all_urls = attachment_urls + sticker_urls
        if all_urls:
            embed.add_field(
                name=_t("antispam.snapshot_field_attachments", lang),
                value="\n".join(all_urls)[:1024],
                inline=False,
            )
        else:
            embed.add_field(
                name=_t("antispam.snapshot_field_attachments", lang),
                value=_t("antispam.snapshot_field_no_attachments", lang),
                inline=False,
            )

        if message.jump_url:
            embed.add_field(
                name=_t("audit.snapshot_field_jump", lang),
                value=message.jump_url,
                inline=False,
            )

        if message.author.avatar:
            embed.set_thumbnail(url=message.author.avatar.url)

        embed.set_footer(text=_t("audit.snapshot_footer", lang, id=message.id))
        return embed

    async def log_antispam_with_snapshot(
        self,
        *,
        user: discord.User | discord.Member,
        guild: discord.Guild,
        channel: discord.TextChannel,
        detail: str,
        success: bool,
        trigger_message: discord.Message,
        category: str,
        action_label: str,
    ):
        if not self.c.audit.enabled:
            return

        targets = self._resolve_targets(guild, "audit")
        if not targets:
            return

        lang = self._resolve_lang(guild)

        embed = self._build_embed(
            lang=lang,
            action="antispam-auto-catch",
            user=user,
            guild=guild,
            channel=channel,
            detail=detail,
            success=success,
            auto=True,
        )

        snapshot_embed = self._build_message_snapshot_embed(trigger_message, lang)

        view = AntispamActionView(
            guild_id=guild.id,
            target_id=user.id,
            target_name=str(user),
            action_label=action_label,
            lang=lang,
            lang_store=self.lang_store,
        )

        for channel_id in targets:
            await self._send_to_channel(channel_id, embed=embed)
            await self._send_to_channel(channel_id, embed=snapshot_embed, view=view)
