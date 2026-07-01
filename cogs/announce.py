from loguru import logger as l
import discord
from discord import app_commands
from discord.ext import commands

from modules.audit import AuditLogger
import utils as u


class AnnounceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.c = bot.config  # ty:ignore[unresolved-attribute]
        self.audit: AuditLogger | None = getattr(bot, "audit", None)

    # ========== /subscribe ==========

    @app_commands.command(
        name="subscribe",
        description="[MOD] Follow the announcement channel in your server",
    )
    @app_commands.describe(target="Channel to receive announcements (default: current)")
    @u.requires(u.Permission.MOD)
    async def subscribe(
        self,
        interaction: discord.Interaction,
        target: discord.TextChannel | None = None,
    ):
        source_id = self.c.announce.source_channel
        if not source_id:
            await interaction.response.send_message(
                ":x: **Announcements are not configured**", ephemeral=True
            )
            return

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

        source = self.bot.get_channel(source_id)
        if source is None:
            try:
                source = await self.bot.fetch_channel(source_id)
            except (discord.NotFound, discord.Forbidden):
                await interaction.response.send_message(
                    ":x: **Announcement channel not found**", ephemeral=True
                )
                return

        if not isinstance(source, discord.TextChannel):
            await interaction.response.send_message(
                ":x: **Configured source channel is not a text channel**",
                ephemeral=True,
            )
            return

        if not source.is_news():
            await interaction.response.send_message(
                ":x: **Configured source channel is not an announcement/news channel**",
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
            f":white_check_mark: **{destination.mention} now follows the announcement channel.**\n"
            f"> Messages published there will appear here.\n"
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


async def setup(bot: commands.Bot):
    announce_cfg = getattr(bot.config, "announce", None)  # ty:ignore[unresolved-attribute]
    if announce_cfg and announce_cfg.source_channel:
        await bot.add_cog(AnnounceCog(bot))
        l.info("AnnounceCog loaded.")
