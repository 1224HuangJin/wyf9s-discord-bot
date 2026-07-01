import time
from datetime import datetime, timezone

from loguru import logger as l
import discord
from discord import app_commands
from discord.ext import commands

from modules.audit import AuditLogger
import utils as u


_ANNOUNCE_COOLDOWN = 60


class ConfirmAnnounceView(discord.ui.View):
    def __init__(self, announce: "AnnounceCog", content: str):
        super().__init__(timeout=300)
        self.announce = announce
        self.content = content
        self.confirmed: bool | None = None

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
        self.stop()
        await interaction.response.defer()
        await interaction.edit_original_response(
            content=":loudspeaker: **Publishing announcement...**", view=None
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
        self._last_announce = 0.0

    # ========== /subscribe ==========

    @app_commands.command(
        name="subscribe",
        description="Follow this server's announcement channel for updates",
    )
    @app_commands.describe(
        target="Channel in this server to receive announcements (default: current)"
    )
    @u.requires(u.Permission.MOD)
    async def subscribe(
        self,
        interaction: discord.Interaction,
        target: discord.TextChannel | None = None,
    ):
        destination = target or interaction.channel
        if not isinstance(destination, discord.TextChannel):
            await interaction.response.send_message(
                ":x: **Must be a text channel**", ephemeral=True
            )
            return

        if not interaction.guild:
            await interaction.response.send_message(
                ":x: **Server-only command**", ephemeral=True
            )
            return

        source = interaction.channel
        if not isinstance(source, discord.TextChannel):
            await interaction.response.send_message(
                ":x: **Source channel must be a text channel**", ephemeral=True
            )
            return

        # The source must be an announcement/news channel
        if not source.is_news():
            await interaction.response.send_message(
                ":x: **This channel is not an announcement channel. "
                "Use /subscribe in a news/announcement channel.**",
                ephemeral=True,
            )
            return

        try:
            await destination.follow(
                destination=source,
                reason=f"Subscribed by {interaction.user} via wyf9-bot",
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                ":x: **Bot needs Manage Webhooks permission in the target channel**",
                ephemeral=True,
            )
            return
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f":x: **Failed to follow:** `{e}`", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f":white_check_mark: **{destination.mention} now follows this announcement channel.**\n"
            f"> Messages published here will appear in {destination.mention}.\n"
            f"> To unsubscribe, delete the webhook in channel settings."
        )

        if self.audit:
            await self.audit.log(
                action="subscribe",
                user=interaction.user,
                guild=interaction.guild,
                channel=interaction.channel,
                detail=f"Followed {destination.name} ({destination.id}) from announcement channel",
            )

    # ========== /announce ==========

    @app_commands.command(
        name="announce",
        description="Publish an announcement to all following channels (admin only)",
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

        if not isinstance(channel, discord.TextChannel):
            await u.send_msg(
                source,
                ":x: **Must be used in a text channel**",
                ephemeral=True,
                delete_after=10,
            )
            return

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

        content = ""

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

        # Preview with confirm/cancel
        view = ConfirmAnnounceView(self, content)
        if is_interaction:
            await source.response.send_message(
                f"**Preview:**\n{content[:1900]}", view=view
            )
        else:
            await source.send(f"**Preview:**\n{content[:1900]}", view=view)

        await view.wait()
        if not view.confirmed:
            return

        # Publish to this channel (Discord auto-forwards to all followers)
        user = source.user if is_interaction else source.author
        timestamp = int(datetime.now(timezone.utc).timestamp())
        announce_content = f"{content}\n\n-# Sent by {user} · <t:{timestamp}:f>"

        try:
            msg = await channel.send(announce_content)
            if channel.is_news():
                await msg.publish()
        except discord.HTTPException as e:
            await u.send_msg(
                source,
                f":x: **Failed to publish:** `{e}`",
                ephemeral=True,
                delete_after=10,
            )
            return

        self._last_announce = time.monotonic()

        if is_interaction:
            await source.followup.send(
                ":loudspeaker: **Announcement published.** Discord will forward to following channels."
            )
        else:
            await source.send(
                ":loudspeaker: **Announcement published.** Discord will forward to following channels."
            )

        if self.audit:
            await self.audit.log(
                action="announce",
                user=user,
                guild=source.guild,
                channel=source.channel,
                detail=f"Published announcement: {content[:500]}",
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(AnnounceCog(bot))
    l.info("AnnounceCog loaded.")
