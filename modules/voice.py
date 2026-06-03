# -*- coding: utf-8 -*-
from loguru import logger as l
import discord
from discord import app_commands
from discord.ext import commands

from config import ConfigModel
from modules.audit import AuditLogger


class VoiceChannelModule:
    """
    语音频道控制模块
    指令: joinvc, leavevc
    """

    c: ConfigModel
    client: commands.Bot
    audit: AuditLogger | None

    def __init__(
        self, config: ConfigModel, client: commands.Bot, audit: AuditLogger | None
    ):
        self.c = config
        self.client = client
        self.audit = audit

        if self.c.voicechannel.slash:
            self._register_slash_commands(client)

        if self.c.voicechannel.prefix:
            self._register_prefix_commands(client)

    def _register_slash_commands(self, client: commands.Bot):
        @client.tree.command(
            name="joinvc",
            description="让机器人加入语音频道（你当前所在频道 或 指定频道）",
        )
        @app_commands.describe(
            channel="要加入的语音频道（留空则使用你当前所在的语音频道）"
        )
        async def joinvc(
            interaction: discord.Interaction,
            channel: discord.VoiceChannel | None = None,
        ):
            await self._handle_joinvc(interaction, channel)

        @client.tree.command(name="leavevc", description="让机器人离开当前语音频道")
        async def leavevc(interaction: discord.Interaction):
            await self._handle_leavevc(interaction)

    def _register_prefix_commands(self, client: commands.Bot):
        @client.command(name="joinvc")
        async def prefix_joinvc(
            ctx: commands.Context, channel: discord.VoiceChannel | None = None
        ):
            await self._handle_joinvc(ctx, channel)

        @client.command(name="leavevc")
        async def prefix_leavevc(ctx: commands.Context):
            await self._handle_leavevc(ctx)

    # ========== Shared Logic ==========

    async def _handle_joinvc(self, source, channel: discord.VoiceChannel | None = None):
        user = source.user if isinstance(source, discord.Interaction) else source.author

        if not self._check_user_allowed(user):
            err_msg = (
                f"你没有权限使用此命令 *(UserID: `{user.id}`, UserName: `{user.name}`)*"
            )
            if isinstance(source, discord.Interaction):
                await source.response.send_message(err_msg, ephemeral=True)
            else:
                await source.send(err_msg, delete_after=10)
            return

        if channel is None and isinstance(user, discord.Member):
            if (
                not user.voice
                or not user.voice.channel
                or isinstance(user.voice.channel, discord.StageChannel)
            ):
                err_msg = "你需要先加入一个语音频道，或者明确指定要加入的频道"
                if isinstance(source, discord.Interaction):
                    await source.response.send_message(err_msg, ephemeral=True)
                else:
                    await source.send(err_msg, delete_after=10)
                return
            channel = user.voice.channel

        if not isinstance(channel, discord.VoiceChannel):
            err_msg = "目标不是语音频道"
            if isinstance(source, discord.Interaction):
                await source.response.send_message(err_msg, ephemeral=True)
            else:
                await source.send(err_msg, delete_after=10)
            return

        try:
            guild = source.guild
            if guild and guild.voice_client:
                if (
                    isinstance(guild.voice_client.channel, discord.VoiceChannel)
                    and guild.voice_client.channel.id == channel.id
                ):
                    msg = f"已经在 **{channel.name}** 里了"
                    if isinstance(source, discord.Interaction):
                        await source.response.send_message(msg, ephemeral=True)
                    else:
                        await source.send(msg, delete_after=10)
                    return
                await guild.voice_client.disconnect(force=False)
                await channel.connect(self_deaf=True, self_mute=True)
                msg = f"已移动到 **{channel.name}**"
                if isinstance(source, discord.Interaction):
                    await source.response.send_message(msg)
                else:
                    await source.send(msg)
            else:
                await channel.connect(self_deaf=True, self_mute=True)
                msg = f"已加入 **{channel.name}**"
                if isinstance(source, discord.Interaction):
                    await source.response.send_message(msg)
                else:
                    await source.send(msg)

            await self.client.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.listening, name=channel.name
                )
            )
            l.info(f"Bot joined voice channel: {channel.name} (ID: {channel.id})")
            if self.audit:
                await self.audit.log(
                    action="joinvc",
                    user=user,
                    guild=source.guild,
                    channel=source.channel,
                    detail=f"加入语音频道 `{channel.name}` (`{channel.id}`)",
                )

        except discord.errors.ConnectionClosed as exc:
            if exc.code == 4017:
                err_msg = "频道要求 DAVE 加密，但连接失败"
                if isinstance(source, discord.Interaction):
                    await source.followup.send(err_msg, ephemeral=True)
                else:
                    await source.send(err_msg, delete_after=10)
            else:
                raise
        except discord.ClientException as e:
            err_msg = f"连接失败：{e}"
            if isinstance(source, discord.Interaction):
                await source.response.send_message(err_msg, ephemeral=True)
            else:
                await source.send(err_msg, delete_after=10)
            l.error(f"Failed to join voice channel: {e}")
        except Exception as e:
            err_msg = f"发生错误：{type(e).__name__}"
            if isinstance(source, discord.Interaction):
                await source.response.send_message(err_msg, ephemeral=True)
            else:
                await source.send(err_msg, delete_after=10)
            l.error(f"Unexpected error in joinvc: {type(e).__name__}: {e}")

    async def _handle_leavevc(self, source):
        user = source.user if isinstance(source, discord.Interaction) else source.author

        if not self._check_user_allowed(user):
            err_msg = "你没有权限使用此命令"
            if isinstance(source, discord.Interaction):
                await source.response.send_message(err_msg, ephemeral=True)
            else:
                await source.send(err_msg, delete_after=10)
            return

        guild = source.guild
        if not guild or not guild.voice_client:
            err_msg = "我目前没在任何语音频道里"
            if isinstance(source, discord.Interaction):
                await source.response.send_message(err_msg, ephemeral=True)
            else:
                await source.send(err_msg, delete_after=10)
            return

        if not isinstance(guild.voice_client.channel, discord.VoiceChannel):
            err_msg = "机器人未在有效的语音频道中"
            if isinstance(source, discord.Interaction):
                await source.response.send_message(err_msg, ephemeral=True)
            else:
                await source.send(err_msg, delete_after=10)
            return

        channel_name = guild.voice_client.channel.name
        await guild.voice_client.disconnect(force=False)

        msg = f"已离开 **{channel_name}**"
        if isinstance(source, discord.Interaction):
            await source.response.send_message(msg)
        else:
            await source.send(msg)

        await self.client.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching, name="等待指令..."
            )
        )
        l.info(f"Bot left voice channel: {channel_name}")
        if self.audit:
            await self.audit.log(
                action="leavevc",
                user=user,
                guild=source.guild,
                channel=source.channel,
                detail=f"离开语音频道 `{channel_name}`",
            )

    def _check_user_allowed(self, user: discord.User | discord.Member) -> bool:
        """
        检查用户是否被允许使用此功能

        如果 allowed_user_ids 为空，则所有人都被允许
        如果 allowed_user_ids 不为空，则只有列表中的用户被允许
        """
        return any(
            (
                not self.c.voicechannel.allowed_user_ids,  # whitelist not set
                user.id in self.c.voicechannel.allowed_user_ids,  # user id match
                user.name in self.c.voicechannel.allowed_user_ids,  # username match
            )
        )
