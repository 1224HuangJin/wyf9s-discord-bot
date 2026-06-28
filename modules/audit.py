# -*- coding: utf-8 -*-
"""
操作执行日志模块

- 全局日志: 所有服务器的管理操作发送到 `audit.global_channel`
- 按服务器日志: `audit.guilds` 中为每个服务器单独配置目标频道与语言
- 全局与按服务器日志互不影响: 若两者都配置, 则两个频道都会收到日志
"""

from datetime import datetime, timezone

from loguru import logger as l
import discord
from discord.ext import commands

from config import AuditLang, ConfigModel


# 文案 (中/英) ----------------------------------------------------------------

_TEXT: dict[str, dict[AuditLang, str]] = {
    "title_manual_ok": {"zh": "✅ 操作日志", "en": "✅ Action Log"},
    "title_manual_fail": {"zh": "❌ 操作日志", "en": "❌ Action Log"},
    "title_auto_ok": {"zh": "🚨 自动操作日志", "en": "🚨 Automated Action Log"},
    "title_auto_fail": {
        "zh": "⚠️ 自动操作失败",
        "en": "⚠️ Automated Action Failed",
    },
    "field_action": {"zh": "操作", "en": "Action"},
    "field_actor": {"zh": "执行者", "en": "Actor"},
    "field_guild": {"zh": "服务器", "en": "Server"},
    "field_channel": {"zh": "频道", "en": "Channel"},
    "field_detail": {"zh": "详情", "en": "Detail"},
}


def _t(key: str, lang: AuditLang) -> str:
    entry = _TEXT.get(key)
    if not entry:
        return key
    return entry.get(lang, entry["zh"])


class AuditLogger:
    c: ConfigModel
    client: commands.Bot

    def __init__(self, config: ConfigModel, client: commands.Bot):
        self.c = config
        self.client = client

    def _resolve_targets(
        self, guild: discord.Guild | None
    ) -> list[tuple[int, AuditLang]]:
        """
        计算本次日志需要发送到的 (频道 ID, 语言) 列表 (按频道去重, 保持全局优先)
        """
        targets: list[tuple[int, AuditLang]] = []
        seen: set[int] = set()

        # 全局频道
        if self.c.audit.global_channel:
            targets.append((self.c.audit.global_channel, self.c.audit.global_lang))
            seen.add(self.c.audit.global_channel)

        # 按服务器配置的频道 (与全局互不影响)
        if guild is not None:
            guild_conf = self.c.audit.guilds.get(
                guild.id, self.c.audit.guilds.get(str(guild.id))
            )
            if guild_conf is not None and guild_conf.channel not in seen:
                targets.append((guild_conf.channel, guild_conf.lang))
                seen.add(guild_conf.channel)

        return targets

    def _build_embed(
        self,
        *,
        lang: AuditLang,
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
            title_key = "title_auto_ok" if success else "title_auto_fail"
        else:
            title_key = "title_manual_ok" if success else "title_manual_fail"

        embed = discord.Embed(
            title=_t(title_key, lang),
            color=color,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name=_t("field_action", lang), value=f"`{action}`", inline=True)
        embed.add_field(
            name=_t("field_actor", lang),
            value=f"{user.mention} (`{user.name}` / `{user.id}`)",
            inline=True,
        )
        if guild is not None:
            embed.add_field(
                name=_t("field_guild", lang),
                value=f"`{guild.name}` (`{guild.id}`)",
                inline=False,
            )
        if channel is not None:
            channel_repr = getattr(channel, "mention", None) or getattr(
                channel, "name", str(channel)
            )
            embed.add_field(
                name=_t("field_channel", lang), value=str(channel_repr), inline=False
            )
        if detail:
            # Discord embed field value 上限 1024
            embed.add_field(
                name=_t("field_detail", lang), value=detail[:1024], inline=False
            )
        return embed

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
    ):
        """
        记录一条操作日志

        :param action: 操作名称, 如 `/delete`, `/clear-message`, `antispam-auto-catch`
        :param user: 执行操作的用户
        :param guild: 操作所在的服务器 (用于按服务器配置)
        :param channel: 操作所在的频道 (可选, 用于补充上下文)
        :param detail: 操作的额外说明
        :param success: 操作是否成功
        :param auto: 是否为自动化操作 (如 antispam), 影响日志标题
        """
        if not self.c.audit.enabled:
            return

        targets = self._resolve_targets(guild)
        if not targets:
            return

        # 同一语言的 embed 缓存, 避免重复构建
        embed_cache: dict[AuditLang, discord.Embed] = {}

        for channel_id, lang in targets:
            if lang not in embed_cache:
                embed_cache[lang] = self._build_embed(
                    lang=lang,
                    action=action,
                    user=user,
                    guild=guild,
                    channel=channel,
                    detail=detail,
                    success=success,
                    auto=auto,
                )
            embed = embed_cache[lang]
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
