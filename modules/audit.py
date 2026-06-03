# -*- coding: utf-8 -*-
"""
管理员操作执行日志模块

- 全局日志: 所有服务器的管理操作发送到 `audit.global_channel`
- 按服务器日志: `audit.guilds` 中为每个服务器单独配置目标频道
- 全局与按服务器日志互不影响: 若两者都配置, 则两个频道都会收到日志
"""

from datetime import datetime, timezone

from loguru import logger as l
import discord
from discord.ext import commands

from config import ConfigModel


class AuditLogger:
    c: ConfigModel
    client: commands.Bot

    def __init__(self, config: ConfigModel, client: commands.Bot):
        self.c = config
        self.client = client

    def _resolve_channels(self, guild: discord.Guild | None) -> list[int]:
        """
        计算本次日志需要发送到的频道 ID 列表 (去重, 保持全局优先)
        """
        channel_ids: list[int] = []

        # 全局频道
        if self.c.audit.global_channel:
            channel_ids.append(self.c.audit.global_channel)

        # 按服务器配置的频道 (与全局互不影响)
        if guild is not None:
            guild_channel = self.c.audit.guilds.get(
                guild.id, self.c.audit.guilds.get(str(guild.id))
            )
            if guild_channel and guild_channel not in channel_ids:
                channel_ids.append(guild_channel)

        return channel_ids

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
    ):
        """
        记录一条管理员操作日志

        :param action: 操作名称, 如 `/delete`, `/clear-message`
        :param user: 执行操作的用户
        :param guild: 操作所在的服务器 (用于按服务器配置)
        :param channel: 操作所在的频道 (可选, 用于补充上下文)
        :param detail: 操作的额外说明
        :param success: 操作是否成功
        """
        if not self.c.audit.enabled:
            return

        channel_ids = self._resolve_channels(guild)
        if not channel_ids:
            return

        color = discord.Color.green() if success else discord.Color.red()
        status_emoji = ":white_check_mark:" if success else ":x:"

        embed = discord.Embed(
            title=f"{status_emoji} 管理操作日志",
            color=color,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="操作", value=f"`{action}`", inline=True)
        embed.add_field(
            name="执行者",
            value=f"{user.mention} (`{user.name}` / `{user.id}`)",
            inline=True,
        )
        if guild is not None:
            embed.add_field(
                name="服务器", value=f"`{guild.name}` (`{guild.id}`)", inline=False
            )
        if channel is not None:
            channel_repr = getattr(channel, "mention", None) or getattr(
                channel, "name", str(channel)
            )
            embed.add_field(name="频道", value=str(channel_repr), inline=False)
        if detail:
            # Discord embed field value 上限 1024
            embed.add_field(name="详情", value=detail[:1024], inline=False)

        for channel_id in channel_ids:
            try:
                target = self.client.get_channel(channel_id)
                if target is None:
                    target = await self.client.fetch_channel(channel_id)
                if not isinstance(target, (discord.TextChannel, discord.Thread)):
                    l.warning(
                        f"[audit] 日志频道 {channel_id} 不是可发送消息的文字频道, 已跳过"
                    )
                    continue
                await target.send(embed=embed)
            except discord.Forbidden:
                l.warning(f"[audit] 无权限向日志频道 {channel_id} 发送消息")
            except discord.NotFound:
                l.warning(f"[audit] 找不到日志频道 {channel_id}")
            except Exception as e:
                l.warning(f"[audit] 向日志频道 {channel_id} 发送日志时出错: {e}")
