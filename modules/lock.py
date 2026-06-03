# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger as l
from pydantic import BaseModel
import discord
from discord import app_commands
from discord.ext import commands, tasks
from yaml import safe_load, safe_dump

from config import ConfigModel
from modules.audit import AuditLogger
import utils as u


class ScheduledLock(BaseModel):
    """一条计划锁定记录"""

    channel_id: int
    """目标频道 ID"""

    lock_at: datetime | None = None
    """锁定时间 (UTC), None 表示立即锁定"""

    unlock_at: datetime | None = None
    """解锁时间 (UTC), None 表示不自动解锁"""

    created_by: int
    """创建者用户 ID"""

    created_at: datetime = datetime.now(timezone.utc)
    """创建时间"""


class ScheduleStore:
    """YAML 文件存储计划锁定"""

    def __init__(self, path: str = "schedules.yaml"):
        self._path = Path(path)
        self.schedules: list[ScheduledLock] = []
        self._load()

    def _load(self):
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = safe_load(f) or []
                self.schedules = [ScheduledLock.model_validate(item) for item in data]
            except Exception as e:
                l.warning(f"[lock] Failed to load schedules: {e}")
                self.schedules = []

    def _save(self):
        data = [s.model_dump(mode="json") for s in self.schedules]
        with open(self._path, "w", encoding="utf-8") as f:
            safe_dump(data, f, allow_unicode=True, default_flow_style=False)

    def add(self, schedule: ScheduledLock):
        self.schedules.append(schedule)
        self._save()

    def remove(self, channel_id: int):
        self.schedules = [s for s in self.schedules if s.channel_id != channel_id]
        self._save()

    def get_pending_locks(self, now: datetime) -> list[ScheduledLock]:
        """获取需要执行锁定的计划"""
        return [s for s in self.schedules if s.lock_at is not None and s.lock_at <= now]

    def get_pending_unlocks(self, now: datetime) -> list[ScheduledLock]:
        """获取需要执行解锁的计划"""
        return [
            s for s in self.schedules if s.unlock_at is not None and s.unlock_at <= now
        ]


class LockModule:
    """
    频道锁定模块
    指令: lock, unlock, plan-lock
    """

    c: ConfigModel
    client: commands.Bot
    audit: AuditLogger | None
    store: ScheduleStore

    def __init__(
        self, config: ConfigModel, client: commands.Bot, audit: AuditLogger | None
    ):
        self.c = config
        self.client = client
        self.audit = audit
        self.store = ScheduleStore()

        if self.c.lock.slash:
            self._register_slash_commands(client)

        if self.c.lock.prefix:
            self._register_prefix_commands(client)

    async def start_scheduler(self):
        """在 on_ready 中调用以启动定时任务"""
        self._check_schedules.start()

    def _register_slash_commands(self, client: commands.Bot):
        @client.tree.command(
            name="lock",
            description="锁定频道 (禁止 @everyone 发送消息)",
        )
        @app_commands.describe(channel="要锁定的频道 (可选, 默认当前频道)")
        async def slash_lock(
            interaction: discord.Interaction,
            channel: discord.TextChannel
            | discord.VoiceChannel
            | discord.StageChannel
            | None = None,
        ):
            await self._handle_lock(interaction, channel)

        @client.tree.command(
            name="unlock",
            description="解锁频道 (恢复 @everyone 发送消息权限)",
        )
        @app_commands.describe(channel="要解锁的频道 (可选, 默认当前频道)")
        async def slash_unlock(
            interaction: discord.Interaction,
            channel: discord.TextChannel
            | discord.VoiceChannel
            | discord.StageChannel
            | None = None,
        ):
            await self._handle_unlock(interaction, channel)

        @client.tree.command(
            name="plan-lock",
            description="计划锁定/解锁频道",
        )
        @app_commands.describe(
            channel="目标频道",
            lock_at="锁定时间 (ISO 格式, 如 2026-06-04T22:00:00+08:00, 留空=立即)",
            unlock_at="解锁时间 (ISO 格式, 如 2026-06-05T08:00:00+08:00, 留空=不自动解锁)",
        )
        async def slash_plan_lock(
            interaction: discord.Interaction,
            channel: discord.TextChannel | discord.VoiceChannel | discord.StageChannel,
            lock_at: str | None = None,
            unlock_at: str | None = None,
        ):
            await self._handle_plan_lock(interaction, channel, lock_at, unlock_at)

    def _register_prefix_commands(self, client: commands.Bot):
        @client.command(name="lock")
        async def prefix_lock(
            ctx: commands.Context,
            channel: discord.TextChannel
            | discord.VoiceChannel
            | discord.StageChannel
            | None = None,
        ):
            await self._handle_lock(ctx, channel)

        @client.command(name="unlock")
        async def prefix_unlock(
            ctx: commands.Context,
            channel: discord.TextChannel
            | discord.VoiceChannel
            | discord.StageChannel
            | None = None,
        ):
            await self._handle_unlock(ctx, channel)

        @client.command(name="plan-lock")
        async def prefix_plan_lock(
            ctx: commands.Context,
            channel: discord.TextChannel | discord.VoiceChannel | discord.StageChannel,
            lock_at: str | None = None,
            unlock_at: str | None = None,
        ):
            await self._handle_plan_lock(ctx, channel, lock_at, unlock_at)

    # ========== Shared Logic ==========

    async def _handle_lock(self, source, channel=None):
        user = source.user if isinstance(source, discord.Interaction) else source.author

        if not self._can_use_lock(user, source.guild):
            await u.send_msg(
                source,
                ":x: **你没有权限使用此指令** :x:",
                ephemeral=True,
                delete_after=10,
            )
            return

        target = channel or source.channel
        if not isinstance(
            target, (discord.TextChannel, discord.VoiceChannel, discord.StageChannel)
        ):
            await u.send_msg(
                source,
                ":x: **此频道类型不支持锁定** :x:",
                ephemeral=True,
                delete_after=10,
            )
            return

        try:
            is_voice = isinstance(target, (discord.VoiceChannel, discord.StageChannel))
            everyone = target.guild.default_role

            overwrites = target.overwrites_for(everyone)
            overwrites.send_messages = False
            overwrites.send_messages_in_threads = False
            if is_voice:
                overwrites.connect = False

            await target.set_permissions(
                everyone, overwrite=overwrites, reason=f"频道锁定 by {user}"
            )

            if is_voice:
                msg = f":lock: **频道已锁定** :lock:\n> 语音/讲堂频道 `{target.name}` 已被锁定，无法加入"
            else:
                msg = f":lock: **频道已锁定** :lock:\n> `{target.name}` 已被锁定，无法发送消息"

            await u.send_msg(source, msg)

            if self.audit:
                await self.audit.log(
                    action="lock",
                    user=user,
                    guild=source.guild,
                    channel=target,
                    detail=f"锁定频道 `{target.name}`",
                )

            self.store.remove(target.id)

        except discord.Forbidden:
            await u.send_msg(
                source,
                ":x: **权限不足，无法修改频道权限** :x:",
                ephemeral=True,
                delete_after=10,
            )
        except Exception as e:
            await u.send_msg(
                source, f":x: **锁定失败: `{e}`** :x:", ephemeral=True, delete_after=10
            )

    async def _handle_unlock(self, source, channel=None):
        user = source.user if isinstance(source, discord.Interaction) else source.author

        if not self._can_use_lock(user, source.guild):
            await u.send_msg(
                source,
                ":x: **你没有权限使用此指令** :x:",
                ephemeral=True,
                delete_after=10,
            )
            return

        target = channel or source.channel
        if not isinstance(
            target, (discord.TextChannel, discord.VoiceChannel, discord.StageChannel)
        ):
            await u.send_msg(
                source,
                ":x: **此频道类型不支持解锁** :x:",
                ephemeral=True,
                delete_after=10,
            )
            return

        try:
            is_voice = isinstance(target, (discord.VoiceChannel, discord.StageChannel))
            everyone = target.guild.default_role

            overwrites = target.overwrites_for(everyone)
            overwrites.send_messages = None
            overwrites.send_messages_in_threads = None
            if is_voice:
                overwrites.connect = None

            await target.set_permissions(
                everyone, overwrite=overwrites, reason=f"频道解锁 by {user}"
            )

            if is_voice:
                msg = f":unlock: **频道已解锁** :unlock:\n> 语音/讲堂频道 `{target.name}` 已解锁，可以加入"
            else:
                msg = f":unlock: **频道已解锁** :unlock:\n> `{target.name}` 已解锁，可以发送消息"

            await u.send_msg(source, msg)

            if self.audit:
                await self.audit.log(
                    action="unlock",
                    user=user,
                    guild=source.guild,
                    channel=target,
                    detail=f"解锁频道 `{target.name}`",
                )

            self.store.remove(target.id)

        except discord.Forbidden:
            await u.send_msg(
                source,
                ":x: **权限不足，无法修改频道权限** :x:",
                ephemeral=True,
                delete_after=10,
            )
        except Exception as e:
            await u.send_msg(
                source, f":x: **解锁失败: `{e}`** :x:", ephemeral=True, delete_after=10
            )

    async def _handle_plan_lock(
        self, source, channel, lock_at: str | None = None, unlock_at: str | None = None
    ):
        user = source.user if isinstance(source, discord.Interaction) else source.author

        if not self._can_use_lock(user, source.guild):
            await u.send_msg(
                source,
                ":x: **你没有权限使用此指令** :x:",
                ephemeral=True,
                delete_after=10,
            )
            return

        if not isinstance(
            channel, (discord.TextChannel, discord.VoiceChannel, discord.StageChannel)
        ):
            await u.send_msg(
                source,
                ":x: **此频道类型不支持计划锁定** :x:",
                ephemeral=True,
                delete_after=10,
            )
            return

        parsed_lock: datetime | None = None
        parsed_unlock: datetime | None = None

        if lock_at:
            try:
                parsed_lock = self._parse_time(lock_at)
            except ValueError as e:
                await u.send_msg(
                    source,
                    f":x: **lock_at 格式错误: `{e}`** :x:",
                    ephemeral=True,
                    delete_after=10,
                )
                return

        if unlock_at:
            try:
                parsed_unlock = self._parse_time(unlock_at)
            except ValueError as e:
                await u.send_msg(
                    source,
                    f":x: **unlock_at 格式错误: `{e}`** :x:",
                    ephemeral=True,
                    delete_after=10,
                )
                return

        if not parsed_lock and not parsed_unlock:
            await u.send_msg(
                source,
                ":x: **请至少指定 lock_at 或 unlock_at 中的一个** :x:",
                ephemeral=True,
                delete_after=10,
            )
            return

        if parsed_lock and parsed_unlock and parsed_lock >= parsed_unlock:
            await u.send_msg(
                source,
                ":x: **lock_at 必须早于 unlock_at** :x:",
                ephemeral=True,
                delete_after=10,
            )
            return

        # 移除该频道的旧计划
        self.store.remove(channel.id)

        schedule = ScheduledLock(
            channel_id=channel.id,
            lock_at=parsed_lock,
            unlock_at=parsed_unlock,
            created_by=user.id,
        )
        self.store.add(schedule)

        parts = []
        if parsed_lock:
            parts.append(f"锁定: <t:{int(parsed_lock.timestamp())}:f>")
        if parsed_unlock:
            parts.append(f"解锁: <t:{int(parsed_unlock.timestamp())}:f>")

        is_voice = isinstance(channel, (discord.VoiceChannel, discord.StageChannel))
        ch_type = "语音/讲堂频道" if is_voice else "频道"

        await u.send_msg(
            source,
            f":clock3: **已计划{ch_type}操作** :clock3:\n"
            f"> {ch_type}: `{channel.name}`\n"
            f"> {', '.join(parts)}",
        )

        if self.audit:
            await self.audit.log(
                action="plan-lock",
                user=user,
                guild=source.guild,
                channel=channel,
                detail=f"计划{ch_type}操作 `{channel.name}`: {' / '.join(parts)}",
            )

    def _parse_time(self, value: str) -> datetime:
        """解析时间字符串为 UTC datetime"""
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    @tasks.loop(minutes=1)
    async def _check_schedules(self):
        """每分钟检查一次计划锁定"""
        now = datetime.now(timezone.utc)

        # 执行锁定
        for schedule in self.store.get_pending_locks(now):
            channel = self.client.get_channel(schedule.channel_id)
            if channel is None:
                try:
                    channel = await self.client.fetch_channel(schedule.channel_id)
                except Exception:
                    l.warning(
                        f"[lock] Cannot fetch channel {schedule.channel_id}, removing schedule"
                    )
                    self.store.remove(schedule.channel_id)
                    continue

            if not isinstance(
                channel,
                (discord.TextChannel, discord.VoiceChannel, discord.StageChannel),
            ):
                self.store.remove(schedule.channel_id)
                continue

            try:
                is_voice = isinstance(
                    channel, (discord.VoiceChannel, discord.StageChannel)
                )
                everyone = channel.guild.default_role

                overwrites = channel.overwrites_for(everyone)
                overwrites.send_messages = False
                overwrites.send_messages_in_threads = False
                if is_voice:
                    overwrites.connect = False

                await channel.set_permissions(
                    everyone, overwrite=overwrites, reason="Scheduled lock"
                )

                if is_voice:
                    msg = ":lock: **频道已锁定** :lock:\n> 语音/讲堂频道已被锁定，无法加入 (计划锁定)"
                else:
                    msg = ":lock: **频道已锁定** :lock:\n> 频道已被锁定，无法发送消息 (计划锁定)"

                await channel.send(msg)
                l.info(
                    f"[lock] Scheduled lock applied to channel {channel.name} ({channel.id})"
                )

                # 更新计划: lock_at 已执行，设为 None
                schedule.lock_at = None
                if schedule.unlock_at is None:
                    self.store.remove(schedule.channel_id)
                else:
                    self.store._save()

            except discord.Forbidden:
                l.warning(f"[lock] No permission to lock channel {channel.id}")
                self.store.remove(schedule.channel_id)
            except Exception as e:
                l.error(f"[lock] Failed to apply scheduled lock to {channel.id}: {e}")

        # 执行解锁
        for schedule in self.store.get_pending_unlocks(now):
            channel = self.client.get_channel(schedule.channel_id)
            if channel is None:
                try:
                    channel = await self.client.fetch_channel(schedule.channel_id)
                except Exception:
                    l.warning(
                        f"[lock] Cannot fetch channel {schedule.channel_id}, removing schedule"
                    )
                    self.store.remove(schedule.channel_id)
                    continue

            if not isinstance(
                channel,
                (discord.TextChannel, discord.VoiceChannel, discord.StageChannel),
            ):
                self.store.remove(schedule.channel_id)
                continue

            try:
                is_voice = isinstance(
                    channel, (discord.VoiceChannel, discord.StageChannel)
                )
                everyone = channel.guild.default_role

                overwrites = channel.overwrites_for(everyone)
                overwrites.send_messages = None
                overwrites.send_messages_in_threads = None
                if is_voice:
                    overwrites.connect = None

                await channel.set_permissions(
                    everyone, overwrite=overwrites, reason="Scheduled unlock"
                )

                if is_voice:
                    msg = ":unlock: **频道已解锁** :unlock:\n> 语音/讲堂频道已解锁，可以加入 (计划解锁)"
                else:
                    msg = ":unlock: **频道已解锁** :unlock:\n> 频道已解锁，可以发送消息 (计划解锁)"

                await channel.send(msg)
                l.info(
                    f"[lock] Scheduled unlock applied to channel {channel.name} ({channel.id})"
                )

                # 计划完成，移除
                self.store.remove(schedule.channel_id)

            except discord.Forbidden:
                l.warning(f"[lock] No permission to unlock channel {channel.id}")
                self.store.remove(schedule.channel_id)
            except Exception as e:
                l.error(f"[lock] Failed to apply scheduled unlock to {channel.id}: {e}")

    @_check_schedules.before_loop
    async def _before_check(self):
        await self.client.wait_until_ready()

    # ========== Permission Helpers ==========

    def _matches_identity(
        self, user: discord.User | discord.Member, values: list[int | str]
    ) -> bool:
        for value in values:
            if user.id == value or user.name == value:
                return True
            if isinstance(value, str) and value.isdigit() and user.id == int(value):
                return True
        return False

    def _is_mod(
        self, user: discord.User | discord.Member, guild: discord.Guild | None = None
    ) -> bool:
        if isinstance(user, discord.Member) and user.guild_permissions.administrator:
            return True
        if self._matches_identity(user, self.c.admins.users):
            return True
        if isinstance(user, discord.Member):
            if self._matches_identity(user, self.c.mods.users):
                return True
            if guild is not None:
                guild_users = self.c.mods.guilds.get(
                    guild.id, self.c.mods.guilds.get(str(guild.id), [])
                )
                return self._matches_identity(user, guild_users)
        return False

    def _can_use_lock(
        self, user: discord.User | discord.Member, guild: discord.Guild | None = None
    ) -> bool:
        return self._is_mod(user, guild)
