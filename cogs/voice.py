from loguru import logger as l
import discord
from discord import app_commands
from discord.ext import commands

from modules.audit import AuditLogger
import utils as u


def _voice_permission(
    module: "VoiceCog",
    user: discord.User | discord.Member,
    guild: discord.Guild | None,
) -> bool:
    allowed = module.c.voicechannel.allowed_user_ids
    if user.id in allowed or user.name in allowed:
        return True
    return u.is_mod(user, module.c, guild)


class VoiceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.c = bot.config  # ty:ignore[unresolved-attribute]
        self.audit: AuditLogger | None = getattr(bot, "audit", None)

    @app_commands.command(
        name="joinvc", description="Join a voice channel (yours or specified)"
    )
    @app_commands.describe(channel="Voice channel to join (default: your current)")
    @u.requires(_voice_permission, perm_module="voice")
    async def slash_joinvc(
        self,
        interaction: discord.Interaction,
        channel: discord.VoiceChannel | None = None,
    ):
        await self._handle_joinvc(interaction, channel)

    @app_commands.command(name="leavevc", description="Leave current voice channel")
    @u.requires(_voice_permission, perm_module="voice")
    async def slash_leavevc(self, interaction: discord.Interaction):
        await self._handle_leavevc(interaction)

    @commands.command(name="joinvc")
    @u.requires(_voice_permission, perm_module="voice")
    async def prefix_joinvc(
        self, ctx: commands.Context, channel: discord.VoiceChannel | None = None
    ):
        await self._handle_joinvc(ctx, channel)

    @commands.command(name="leavevc")
    @u.requires(_voice_permission, perm_module="voice")
    async def prefix_leavevc(self, ctx: commands.Context):
        await self._handle_leavevc(ctx)

    async def _handle_joinvc(self, source, channel: discord.VoiceChannel | None = None):
        user = source.user if isinstance(source, discord.Interaction) else source.author

        if channel is None and isinstance(user, discord.Member):
            if (
                not user.voice
                or not user.voice.channel
                or isinstance(user.voice.channel, discord.StageChannel)
            ):
                await u.send_msg(
                    source,
                    "Join a voice channel first, or specify one",
                    ephemeral=True,
                    delete_after=10,
                )
                return
            channel = user.voice.channel

        if not isinstance(channel, discord.VoiceChannel):
            await u.send_msg(
                source, "Target is not a voice channel", ephemeral=True, delete_after=10
            )
            return

        try:
            guild = source.guild
            if guild and guild.voice_client:
                if (
                    isinstance(guild.voice_client.channel, discord.VoiceChannel)
                    and guild.voice_client.channel.id == channel.id
                ):
                    await u.send_msg(
                        source,
                        f"Already in **{channel.name}**",
                        ephemeral=True,
                        delete_after=10,
                    )
                    return
                await guild.voice_client.disconnect(force=False)
                await channel.connect(self_deaf=True, self_mute=True)
                await u.send_msg(source, f"Moved to **{channel.name}**")
            else:
                await channel.connect(self_deaf=True, self_mute=True)
                await u.send_msg(source, f"Joined **{channel.name}**")

            await self.bot.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening, name=channel.name
                )
            )
            l.info(f"Bot joined voice: {channel.name} ({channel.id})")
            if self.audit:
                await self.audit.log(
                    action="joinvc",
                    user=user,
                    guild=source.guild,
                    channel=source.channel,
                    detail=f"Joined voice `{channel.name}` (`{channel.id}`)",
                )
        except discord.errors.ConnectionClosed as exc:
            if exc.code == 4017:
                await u.send_msg(
                    source,
                    "Channel requires DAVE encryption, connection failed",
                    ephemeral=True,
                    delete_after=10,
                )
            else:
                raise
        except discord.ClientException as e:
            await u.send_msg(
                source, f"Connection failed: {e}", ephemeral=True, delete_after=10
            )
            l.error(f"Failed to join voice: {e}")
        except Exception as e:
            await u.send_msg(
                source,
                f"Error: {type(e).__name__}",
                ephemeral=True,
                delete_after=10,
            )
            l.error(f"Unexpected error in joinvc: {type(e).__name__}: {e}")

    async def _handle_leavevc(self, source):
        user = source.user if isinstance(source, discord.Interaction) else source.author

        guild = source.guild
        if not guild or not guild.voice_client:
            await u.send_msg(
                source, "Not in any voice channel", ephemeral=True, delete_after=10
            )
            return

        if not isinstance(guild.voice_client.channel, discord.VoiceChannel):
            await u.send_msg(
                source,
                "Not in a valid voice channel",
                ephemeral=True,
                delete_after=10,
            )
            return

        channel_name = guild.voice_client.channel.name
        await guild.voice_client.disconnect(force=False)
        await u.send_msg(source, f"Left **{channel_name}**")

        await self.bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="Idle..."
            )
        )
        l.info(f"Bot left voice: {channel_name}")
        if self.audit:
            await self.audit.log(
                action="leavevc",
                user=user,
                guild=source.guild,
                channel=source.channel,
                detail=f"Left voice `{channel_name}`",
            )


async def setup(bot: commands.Bot):
    if bot.config.voicechannel.enabled:  # ty:ignore[unresolved-attribute]
        await bot.add_cog(VoiceCog(bot))
        l.info("VoiceCog loaded.")
