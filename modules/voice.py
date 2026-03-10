# -*- coding: utf-8 -*-
from loguru import logger as l
import discord
from discord import app_commands
from discord.ext import commands

from config import ConfigModel


class VoiceChannelModule:
    '''
    语音频道控制模块
    - joinvc: 让机器人加入语音频道
    - leavevc: 让机器人离开语音频道
    '''

    c: ConfigModel
    client: commands.Bot

    def __init__(self, config: ConfigModel, client: commands.Bot):
        self.c = config
        self.client = client

        # Create command group
        @client.tree.command(
            name="joinvc",
            description="让机器人加入语音频道（你当前所在频道 或 指定频道）"
        )
        @app_commands.describe(
            channel="要加入的语音频道（留空则使用你当前所在的语音频道）"
        )
        async def joinvc(
            interaction: discord.Interaction,
            channel: discord.VoiceChannel | None = None
        ):
            # Check permissions
            if not self._check_user_allowed(interaction.user):
                await interaction.response.send_message(
                    f"你没有权限使用此命令。*(UserID: `{interaction.user.id}`, UserName: `{interaction.user.name}`)*",
                    ephemeral=True
                )
                return

            if channel is None and isinstance(interaction.user, discord.Member):
                if not interaction.user.voice or not interaction.user.voice.channel or isinstance(interaction.user.voice.channel, discord.StageChannel):
                    await interaction.response.send_message(
                        "你需要先加入一个语音频道，或者明确指定要加入的频道。",
                        ephemeral=True
                    )
                    return
                channel = interaction.user.voice.channel

            if not isinstance(channel, discord.VoiceChannel):
                await interaction.response.send_message("目标不是语音频道。", ephemeral=True)
                return

            try:
                if interaction.guild and interaction.guild.voice_client:
                    if isinstance(interaction.guild.voice_client.channel, discord.VoiceChannel) and interaction.guild.voice_client.channel.id == channel.id:
                        await interaction.response.send_message(
                            f"已经在 **{channel.name}** 里了。",
                            ephemeral=True
                        )
                        return
                    await interaction.guild.voice_client.disconnect(force=False)
                    await channel.connect(
                        self_deaf=True,
                        self_mute=True
                    )
                    await interaction.response.send_message(f"已移动到 **{channel.name}**")
                else:
                    await channel.connect(
                        self_deaf=True,
                        self_mute=True
                    )
                    await interaction.response.send_message(f"已加入 **{channel.name}**")

                # Update bot status
                await self.client.change_presence(
                    activity=discord.Activity(
                        type=discord.ActivityType.listening,
                        name=channel.name
                    )
                )
                l.info(f'Bot joined voice channel: {channel.name} (ID: {channel.id})')

            except discord.errors.ConnectionClosed as exc:
                if exc.code == 4017:
                    await interaction.followup.send(
                        "频道要求 DAVE 加密，但连接失败。",
                        ephemeral=True
                    )
                else:
                    raise
            except discord.ClientException as e:
                await interaction.response.send_message(f"连接失败：{e}", ephemeral=True)
                l.error(f'Failed to join voice channel: {e}')
            except Exception as e:
                await interaction.response.send_message(f"发生错误：{type(e).__name__}", ephemeral=True)
                l.error(f'Unexpected error in joinvc: {type(e).__name__}: {e}')

        @client.tree.command(
            name="leavevc",
            description="让机器人离开当前语音频道"
        )
        async def leavevc(interaction: discord.Interaction):
            # Check permissions
            if not self._check_user_allowed(interaction.user):
                await interaction.response.send_message(
                    "你没有权限使用此命令。",
                    ephemeral=True
                )
                return

            if not interaction.guild or not interaction.guild.voice_client:
                await interaction.response.send_message("我目前没在任何语音频道里。", ephemeral=True)
                return

            if not isinstance(interaction.guild.voice_client.channel, discord.VoiceChannel):
                await interaction.response.send_message("机器人未在有效的语音频道中。", ephemeral=True)
                return

            channel_name = interaction.guild.voice_client.channel.name
            await interaction.guild.voice_client.disconnect(force=False)
            await interaction.response.send_message(f"已离开 **{channel_name}**")

            # Restore bot status to idle
            await self.client.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="等待指令..."
                )
            )
            l.info(f'Bot left voice channel: {channel_name}')

    def _check_user_allowed(self, user: discord.User | discord.Member) -> bool:
        '''
        检查用户是否被允许使用此功能

        如果 allowed_user_ids 为空，则所有人都被允许
        如果 allowed_user_ids 不为空，则只有列表中的用户被允许
        '''
        return any((
            not self.c.voicechannel.allowed_user_ids,  # whitelist not set
            user.id in self.c.voicechannel.allowed_user_ids,  # user id match
            user.name in self.c.voicechannel.allowed_user_ids  # username match
        ))
