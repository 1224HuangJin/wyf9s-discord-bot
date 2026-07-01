import io
import time
from datetime import datetime, timezone

from loguru import logger as l
import discord
from discord import app_commands
from discord.ext import commands

from modules.audit import AuditLogger
import utils as u
from cogs.subscribe_store import SubscribeStore


_ANNOUNCE_COOLDOWN = 60  # seconds between announces


class ConfirmAnnounceView(discord.ui.View):
    def __init__(
        self, announce: "AnnounceCog", content: str, attachment: discord.File | None
    ):
        super().__init__(timeout=300)
        self.announce = announce
        self.content = content
        self.attachment = attachment
        self.confirmed: bool | None = None
        self.confirmed_by: discord.User | discord.Member | None = None

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def btn_confirm(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not u.is_admin(interaction.user, self.announce.c):
            await interaction.response.send_message(
                ":x: **Only bot admins can confirm** :x:", ephemeral=True
            )
            return
        self.confirmed = True
        self.confirmed_by = interaction.user
        self.stop()
        await interaction.response.defer()
        await interaction.edit_original_response(
            content=":loudspeaker: **Sending announcement...**", view=None
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def btn_cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not u.is_admin(interaction.user, self.announce.c):
            await interaction.response.send_message(
                ":x: **Only bot admins can cancel** :x:", ephemeral=True
            )
            return
        self.confirmed = False
        self.stop()
        await interaction.response.defer()
        await interaction.edit_original_response(
            content=":x: **Announcement cancelled**", view=None
        )

    async def on_timeout(self):
        self.confirmed = False


class AnnounceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.c = bot.config  # ty:ignore[unresolved-attribute]
        self.audit: AuditLogger | None = getattr(bot, "audit", None)
        self.store = getattr(bot, "subscribe_store", SubscribeStore())
        bot.subscribe_store = self.store  # ty:ignore[unresolved-attribute]
        self._last_announce = 0.0

    # ========== /subscribe ==========

    @app_commands.command(
        name="subscribe", description="Subscribe a channel for announcements"
    )
    @app_commands.describe(
        channel="Channel to receive announcements (default: current)"
    )
    @u.requires(u.Permission.MOD)
    async def subscribe(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel | None = None,
    ):
        target = channel or interaction.channel
        if not isinstance(target, discord.TextChannel):
            await interaction.response.send_message(
                ":x: **Must be a text channel**", ephemeral=True
            )
            return

        if not interaction.guild:
            await interaction.response.send_message(
                ":x: **Server-only command**", ephemeral=True
            )
            return

        self.store.add(interaction.guild.id, target.id, interaction.user.id)
        await interaction.response.send_message(
            f":white_check_mark: **Subscribed** {target.mention} for announcements.\n"
            f"> Use `/subscribe` again to change channel."
        )

        if self.audit:
            await self.audit.log(
                action="subscribe",
                user=interaction.user,
                guild=interaction.guild,
                channel=interaction.channel,
                detail=f"Subscribed {target.name} ({target.id}) for announcements",
            )

    # ========== /announce ==========

    @app_commands.command(
        name="announce",
        description="Send an announcement to all subscribers (admin only)",
    )
    @app_commands.describe(
        message="Announcement text",
        file="Upload a .md file for the announcement",
        message_id="Message ID to forward (in this channel)",
    )
    async def slash_announce(
        self,
        interaction: discord.Interaction,
        message: str | None = None,
        file: discord.Attachment | None = None,
        message_id: str | None = None,
    ):
        if not u.is_admin(interaction.user, self.c):
            await interaction.response.send_message(
                ":x: **No permission** :x:", ephemeral=True
            )
            return

        await self._handle_announce(interaction, message, file, message_id)

    async def _handle_announce(
        self,
        source,
        message: str | None,
        file: discord.Attachment | None,
        message_id: str | None,
    ):
        is_interaction = isinstance(source, discord.Interaction)
        channel = source.channel

        # Rate limit
        now = time.monotonic()
        elapsed = now - self._last_announce
        if elapsed < _ANNOUNCE_COOLDOWN and self._last_announce > 0:
            remaining = _ANNOUNCE_COOLDOWN - elapsed
            await u.send_msg(
                source,
                f":hourglass: **Cooldown: wait `{remaining:.0f}s`**",
                ephemeral=True,
                delete_after=10,
            )
            return

        # Build content
        content = ""
        attachment = None

        if message:
            content = message
        elif file:
            if not file.filename.endswith(".md"):
                await u.send_msg(
                    source,
                    ":x: **File must be .md format**",
                    ephemeral=True,
                    delete_after=10,
                )
                return
            try:
                file_bytes = await file.read()
                content = file_bytes.decode("utf-8")
            except Exception as e:
                await u.send_msg(
                    source,
                    f":x: **Failed to read file: `{e}`**",
                    ephemeral=True,
                    delete_after=10,
                )
                return
        elif message_id:
            try:
                mid = int(message_id)
                msg = await channel.fetch_message(mid)
                content = msg.content
                if msg.attachments:
                    for att in msg.attachments:
                        if att.filename.endswith(".md"):
                            try:
                                file_bytes = await att.read()
                                content += "\n" + file_bytes.decode("utf-8")
                            except Exception:
                                pass
            except (ValueError, discord.NotFound, discord.Forbidden) as e:
                await u.send_msg(
                    source,
                    f":x: **Failed to fetch message: `{e}`**",
                    ephemeral=True,
                    delete_after=10,
                )
                return
        else:
            await u.send_msg(
                source,
                ":x: **Provide one of: `message`, `file`, or `message_id`**",
                ephemeral=True,
                delete_after=10,
            )
            return

        if not content.strip():
            await u.send_msg(
                source,
                ":x: **Announcement content is empty**",
                ephemeral=True,
                delete_after=10,
            )
            return

        # Send preview with confirm/cancel
        view = ConfirmAnnounceView(self, content, attachment)
        if is_interaction:
            await source.response.send_message(
                f"**Preview:**\n{content[:1900]}",
                view=view,
            )
        else:
            await source.send(f"**Preview:**\n{content[:1900]}", view=view)

        # Wait for confirm
        await view.wait()

        if not view.confirmed:
            return

        # Send to all subscribers
        user = source.user if is_interaction else source.author
        timestamp = int(datetime.now(timezone.utc).timestamp())

        subs = self.store.get_all()
        sent = 0
        failed = 0

        for sub in subs:
            try:
                target = self.bot.get_channel(sub.channel_id)
                if target is None:
                    target = await self.bot.fetch_channel(sub.channel_id)
                if isinstance(target, discord.TextChannel):
                    announce_content = (
                        f"{content}\n\n-# Sent by {user} · <t:{timestamp}:f>"
                    )
                    if len(announce_content) > 2000:
                        buf = io.BytesIO(announce_content.encode("utf-8"))
                        await target.send(
                            file=discord.File(fp=buf, filename="announcement.md")
                        )
                    else:
                        await target.send(announce_content)
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                l.warning(f"[announce] Failed to send to {sub.channel_id}: {e}")
                failed += 1

        self._last_announce = time.monotonic()

        result_msg = (
            f":loudspeaker: **Announcement sent**\n"
            f"> Sent: `{sent}` · Failed: `{failed}`"
        )
        if is_interaction:
            await source.followup.send(result_msg)
        else:
            await source.send(result_msg)

        if self.audit:
            await self.audit.log(
                action="announce",
                user=user,
                guild=source.guild,
                channel=source.channel,
                detail=f"Announced to {sent} channels ({failed} failed)",
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(AnnounceCog(bot))
    l.info("AnnounceCog loaded.")
