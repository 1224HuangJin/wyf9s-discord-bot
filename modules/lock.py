# -*- coding: utf-8 -*-
from datetime import datetime, timezone, timedelta
from pathlib import Path
import re

from loguru import logger as l
from pydantic import BaseModel
import discord
from discord import app_commands
from discord.ext import commands, tasks
from yaml import safe_load, safe_dump

from config import ConfigModel
from modules.audit import AuditLogger
import utils as u


# ========== Data Models ==========


class ScheduledLock(BaseModel):
    """一条计划锁定记录"""

    channel_id: int
    """目标频道 ID"""

    lock_day: str | None = None
    """锁定日期: yyyy-mm-dd / mm-dd / dd"""

    lock_time: str | None = None
    """锁定时间: hh-mm"""

    unlock_day: str | None = None
    """解锁日期: yyyy-mm-dd / mm-dd / dd"""

    unlock_time: str | None = None
    """解锁时间: hh-mm"""

    cycle: str | None = None
    """循环: daily / mon,tue,... / 1,2,3 / 1-5"""

    cycle_start: str | None = None
    """循环开始日期"""

    cycle_end: str | None = None
    """循环结束日期"""

    created_by: int
    """创建者用户 ID"""

    created_at: datetime = datetime.now(timezone.utc)
    """创建时间"""

    @property
    def label(self) -> str:
        """用于显示的标签"""
        ch = f"<#{self.channel_id}>"
        parts = [ch]
        if self.lock_day or self.lock_time:
            lock_str = (self.lock_day or "?") + " " + (self.lock_time or "?")
            parts.append(f"锁定: {lock_str}")
        if self.unlock_day or self.unlock_time:
            unlock_str = (self.unlock_day or "?") + " " + (self.unlock_time or "?")
            parts.append(f"解锁: {unlock_str}")
        if self.cycle:
            parts.append(f"循环: {self.cycle}")
        return " | ".join(parts)


class ScheduleStore:
    """YAML 文件存储计划锁定"""

    def __init__(self, path: str = "schedules.yaml"):
        self._path = u.get_path(path)
        self.schedules: list[ScheduledLock] = []
        self._load()

    def _load(self):
        if Path(self._path).exists():
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

    def remove_by_channel(self, channel_id: int):
        self.schedules = [s for s in self.schedules if s.channel_id != channel_id]
        self._save()

    def remove_by_index(self, index: int):
        if 0 <= index < len(self.schedules):
            self.schedules.pop(index)
            self._save()


# ========== Date/Time Parsing ==========

_WEEKDAY_MAP = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
    "周一": 0,
    "周二": 1,
    "周三": 2,
    "周四": 3,
    "周五": 4,
    "周六": 5,
    "周日": 6,
}


def _parse_day(value: str, ref_year: int | None = None) -> tuple[int, int, int]:
    """
    解析日期 -> (year, month, day)
    支持: yyyy-mm-dd / mm-dd / dd
    """
    value = value.strip()
    now = datetime.now()
    year = ref_year or now.year

    # yyyy-mm-dd
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", value)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))

    # mm-dd
    m = re.fullmatch(r"(\d{1,2})-(\d{1,2})", value)
    if m:
        return year, int(m.group(1)), int(m.group(2))

    # dd
    m = re.fullmatch(r"(\d{1,2})", value)
    if m:
        return year, now.month, int(m.group(1))

    raise ValueError(f"无效日期格式: {value} (支持: yyyy-mm-dd / mm-dd / dd)")


def _parse_time(value: str) -> tuple[int, int]:
    """
    解析时间 -> (hour, minute)
    支持: hh-mm / hh:mm
    """
    value = value.strip()
    m = re.fullmatch(r"(\d{1,2})[-:](\d{2})", value)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return h, mi
    raise ValueError(f"无效时间格式: {value} (支持: hh-mm)")


def _parse_day_time(
    day_str: str | None, time_str: str | None, tz: timezone | None = None
) -> datetime | None:
    """解析日期+时间 -> UTC datetime"""
    if not day_str and not time_str:
        return None

    if not time_str:
        time_str = "00-00"
    if not day_str:
        now = datetime.now()
        day_str = f"{now.year}-{now.month}-{now.day}"

    y, mo, d = _parse_day(day_str)
    h, mi = _parse_time(time_str)

    local_dt = datetime(y, mo, d, h, mi, tzinfo=tz or timezone(timedelta(hours=8)))
    return local_dt.astimezone(timezone.utc)


def _cycle_matches_today(cycle: str, now: datetime) -> bool:
    """检查今天是否匹配循环规则"""
    cycle = cycle.strip().lower()

    if cycle == "daily":
        return True

    # weekday: mon,tue,wed,thu,fri,sat,sun
    parts = [p.strip() for p in cycle.split(",")]
    if all(p in _WEEKDAY_MAP for p in parts):
        today_weekday = now.weekday()
        return today_weekday in [_WEEKDAY_MAP[p] for p in parts]

    # day of month: 1,2,3 or 1-5
    days: set[int] = set()
    for part in parts:
        if "-" in part:
            a, b = part.split("-", 1)
            days.update(range(int(a), int(b) + 1))
        else:
            days.add(int(part))
    return now.day in days


# ========== Module ==========


class LockModule:
    """
    频道锁定模块
    指令: lock, unlock, plan-lock, unplan-lock
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

    # ========== Command Registration ==========

    def _register_slash_commands(self, client: commands.Bot):
        store = self.store  # 捕获引用

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
            channel="目标频道 (可选, 默认当前频道)",
            lock_day="锁定日期 (yyyy-mm-dd / mm-dd / dd)",
            lock_time="锁定时间 (hh-mm)",
            unlock_day="解锁日期 (yyyy-mm-dd / mm-dd / dd)",
            unlock_time="解锁时间 (hh-mm)",
            cycle="循环 (daily / mon,tue,... / 1,2,3 / 1-5)",
            cycle_start="循环开始日期 (yyyy-mm-dd)",
            cycle_end="循环结束日期 (yyyy-mm-dd)",
        )
        async def slash_plan_lock(
            interaction: discord.Interaction,
            channel: discord.TextChannel
            | discord.VoiceChannel
            | discord.StageChannel
            | None = None,
            lock_day: str | None = None,
            lock_time: str | None = None,
            unlock_day: str | None = None,
            unlock_time: str | None = None,
            cycle: str | None = None,
            cycle_start: str | None = None,
            cycle_end: str | None = None,
        ):
            await self._handle_plan_lock(
                interaction,
                channel,
                lock_day,
                lock_time,
                unlock_day,
                unlock_time,
                cycle,
                cycle_start,
                cycle_end,
            )

        async def unplan_autocomplete(
            interaction: discord.Interaction, current: str
        ) -> list[app_commands.Choice[int]]:
            choices = []
            for i, s in enumerate(store.schedules):
                label = s.label
                if current.lower() in label.lower():
                    choices.append(app_commands.Choice(name=label[:100], value=i))
            return choices[:25]

        @client.tree.command(
            name="unplan-lock",
            description="取消计划锁定",
        )
        @app_commands.describe(index="要取消的计划编号")
        @app_commands.autocomplete(index=unplan_autocomplete)
        async def slash_unplan_lock(interaction: discord.Interaction, index: int):
            await self._handle_unplan_lock(interaction, index)

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
        async def prefix_plan_lock(ctx: commands.Context):
            flags = u.parse_flags(ctx.message.content)
            channel = None
            if "channel" in flags:
                ch_str = flags["channel"]
                m = re.match(r"<#(\d+)>", ch_str)
                if m:
                    channel = client.get_channel(int(m.group(1)))
                elif ch_str.isdigit():
                    channel = client.get_channel(int(ch_str))

            await self._handle_plan_lock(
                ctx,
                channel,
                lock_day=flags.get("lock-day") or flags.get("lock_day"),
                lock_time=flags.get("lock-time") or flags.get("lock_time"),
                unlock_day=flags.get("unlock-day") or flags.get("unlock_day"),
                unlock_time=flags.get("unlock-time") or flags.get("unlock_time"),
                cycle=flags.get("cycle"),
                cycle_start=flags.get("cycle-start") or flags.get("cycle_start"),
                cycle_end=flags.get("cycle-end") or flags.get("cycle_end"),
            )

        @client.command(name="unplan-lock")
        async def prefix_unplan_lock(ctx: commands.Context, index: int = -1):
            await self._handle_unplan_lock(ctx, index)

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

            # 先发送消息，再锁定
            if is_voice:
                await u.send_msg(
                    source,
                    ":lock: 频道已锁定 / Channel locked.\n> 语音/讲堂频道已锁定，无法加入",
                )
            else:
                await u.send_msg(source, ":lock: 频道已锁定 / Channel locked.")

            overwrites = target.overwrites_for(everyone)
            overwrites.send_messages = False
            overwrites.send_messages_in_threads = False
            if is_voice:
                overwrites.connect = False

            await target.set_permissions(
                everyone, overwrite=overwrites, reason=f"频道锁定 by {user}"
            )

            if self.audit:
                await self.audit.log(
                    action="lock",
                    user=user,
                    guild=source.guild,
                    channel=target,
                    detail=f"锁定频道 `{target.name}`",
                )

            self.store.remove_by_channel(target.id)

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

            # 解锁后发送消息
            if is_voice:
                await u.send_msg(
                    source,
                    ":unlock: 频道已解锁 / Channel unlocked.\n> 语音/讲堂频道已解锁，可以加入",
                )
            else:
                await u.send_msg(source, ":unlock: 频道已解锁 / Channel unlocked.")

            if self.audit:
                await self.audit.log(
                    action="unlock",
                    user=user,
                    guild=source.guild,
                    channel=target,
                    detail=f"解锁频道 `{target.name}`",
                )

            self.store.remove_by_channel(target.id)

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
        self,
        source,
        channel,
        lock_day: str | None,
        lock_time: str | None,
        unlock_day: str | None,
        unlock_time: str | None,
        cycle: str | None,
        cycle_start: str | None,
        cycle_end: str | None,
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

        target = channel or source.channel
        if not isinstance(
            target, (discord.TextChannel, discord.VoiceChannel, discord.StageChannel)
        ):
            await u.send_msg(
                source,
                ":x: **此频道类型不支持计划锁定** :x:",
                ephemeral=True,
                delete_after=10,
            )
            return

        if not lock_day and not lock_time and not unlock_day and not unlock_time:
            await u.send_msg(
                source,
                ":x: **请至少指定锁定或解锁的时间** :x:",
                ephemeral=True,
                delete_after=10,
            )
            return

        # 验证循环参数
        if cycle:
            cycle = cycle.strip().lower()
            if cycle != "daily":
                parts = [p.strip() for p in cycle.split(",")]
                is_weekday = all(p in _WEEKDAY_MAP for p in parts)
                is_day_of_month = all(re.fullmatch(r"\d+(-\d+)?", p) for p in parts)
                if not is_weekday and not is_day_of_month:
                    await u.send_msg(
                        source,
                        ":x: **cycle 格式错误: daily / mon,tue,... / 1,2,3 / 1-5** :x:",
                        ephemeral=True,
                        delete_after=10,
                    )
                    return

        # 移除该频道的旧计划
        self.store.remove_by_channel(target.id)

        schedule = ScheduledLock(
            channel_id=target.id,
            lock_day=lock_day,
            lock_time=lock_time,
            unlock_day=unlock_day,
            unlock_time=unlock_time,
            cycle=cycle,
            cycle_start=cycle_start,
            cycle_end=cycle_end,
            created_by=user.id,
        )
        self.store.add(schedule)

        parts = []
        if lock_day or lock_time:
            parts.append(f"锁定: {lock_day or '?'} {lock_time or '?'}")
        if unlock_day or unlock_time:
            parts.append(f"解锁: {unlock_day or '?'} {unlock_time or '?'}")
        if cycle:
            parts.append(f"循环: {cycle}")

        await u.send_msg(
            source,
            f":clock3: **已计划频道操作** :clock3:\n"
            f"> 频道: {target.mention}\n"
            f"> {' / '.join(parts)}",
        )

        if self.audit:
            await self.audit.log(
                action="plan-lock",
                user=user,
                guild=source.guild,
                channel=target,
                detail=f"计划操作: {' / '.join(parts)}",
            )

    async def _handle_unplan_lock(self, source, index: int):
        user = source.user if isinstance(source, discord.Interaction) else source.author

        if not self._can_use_lock(user, source.guild):
            await u.send_msg(
                source,
                ":x: **你没有权限使用此指令** :x:",
                ephemeral=True,
                delete_after=10,
            )
            return

        if not self.store.schedules:
            await u.send_msg(
                source, ":x: **当前没有计划锁定** :x:", ephemeral=True, delete_after=10
            )
            return

        if index < 0 or index >= len(self.store.schedules):
            items = "\n".join(
                f"`{i}` - {s.label}" for i, s in enumerate(self.store.schedules)
            )
            await u.send_msg(
                source,
                f":x: **无效的编号，请选择:** :x:\n{items}",
                ephemeral=True,
                delete_after=15,
            )
            return

        removed = self.store.schedules[index]
        self.store.remove_by_index(index)

        await u.send_msg(source, f":white_check_mark: **已取消计划:** {removed.label}")

        if self.audit:
            await self.audit.log(
                action="unplan-lock",
                user=user,
                guild=source.guild,
                channel=source.channel,
                detail=f"取消计划: {removed.label}",
            )

    # ========== Schedule Checker ==========

    @tasks.loop(minutes=1)
    async def _check_schedules(self):
        """每分钟检查一次计划锁定"""
        now = datetime.now(timezone.utc)
        now_local = datetime.now()  # 本地时间用于日期匹配

        to_remove: list[int] = []

        for idx, schedule in enumerate(self.store.schedules):
            channel = self.client.get_channel(schedule.channel_id)
            if channel is None:
                try:
                    channel = await self.client.fetch_channel(schedule.channel_id)
                except Exception:
                    l.warning(
                        f"[lock] Cannot fetch channel {schedule.channel_id}, removing"
                    )
                    to_remove.append(idx)
                    continue

            if not isinstance(
                channel,
                (discord.TextChannel, discord.VoiceChannel, discord.StageChannel),
            ):
                to_remove.append(idx)
                continue

            # 检查循环范围
            if schedule.cycle:
                if schedule.cycle_start:
                    try:
                        cy, cm, cd = _parse_day(schedule.cycle_start)
                        if now_local.date() < datetime(cy, cm, cd).date():
                            continue
                    except ValueError:
                        pass
                if schedule.cycle_end:
                    try:
                        cy, cm, cd = _parse_day(schedule.cycle_end)
                        if now_local.date() > datetime(cy, cm, cd).date():
                            to_remove.append(idx)
                            continue
                    except ValueError:
                        pass

            # 检查是否匹配今天
            if schedule.cycle and not _cycle_matches_today(schedule.cycle, now_local):
                continue

            is_voice = isinstance(channel, (discord.VoiceChannel, discord.StageChannel))
            everyone = channel.guild.default_role

            # 检查锁定时间
            if schedule.lock_day or schedule.lock_time:
                lock_dt = _parse_day_time(schedule.lock_day, schedule.lock_time)
                if lock_dt and lock_dt <= now:
                    try:
                        if is_voice:
                            await channel.send(
                                ":lock: 频道已锁定 / Channel locked.\n> 语音/讲堂频道已锁定，无法加入 (计划锁定)"
                            )
                        else:
                            await channel.send(
                                ":lock: 频道已锁定 / Channel locked. (计划锁定)"
                            )

                        overwrites = channel.overwrites_for(everyone)
                        overwrites.send_messages = False
                        overwrites.send_messages_in_threads = False
                        if is_voice:
                            overwrites.connect = False
                        await channel.set_permissions(
                            everyone, overwrite=overwrites, reason="Scheduled lock"
                        )

                        l.info(f"[lock] Scheduled lock: {channel.name} ({channel.id})")

                        if not schedule.cycle:
                            schedule.lock_day = None
                            schedule.lock_time = None
                        elif not schedule.unlock_day and not schedule.unlock_time:
                            pass  # 循环锁定，保留

                    except discord.Forbidden:
                        l.warning(f"[lock] No permission to lock {channel.id}")
                        if not schedule.cycle:
                            to_remove.append(idx)
                    except Exception as e:
                        l.error(f"[lock] Failed to lock {channel.id}: {e}")

            # 检查解锁时间
            if schedule.unlock_day or schedule.unlock_time:
                unlock_dt = _parse_day_time(schedule.unlock_day, schedule.unlock_time)
                if unlock_dt and unlock_dt <= now:
                    try:
                        overwrites = channel.overwrites_for(everyone)
                        overwrites.send_messages = None
                        overwrites.send_messages_in_threads = None
                        if is_voice:
                            overwrites.connect = None
                        await channel.set_permissions(
                            everyone, overwrite=overwrites, reason="Scheduled unlock"
                        )

                        if is_voice:
                            await channel.send(
                                ":unlock: 频道已解锁 / Channel unlocked.\n> 语音/讲堂频道已解锁，可以加入 (计划解锁)"
                            )
                        else:
                            await channel.send(
                                ":unlock: 频道已解锁 / Channel unlocked. (计划解锁)"
                            )

                        l.info(
                            f"[lock] Scheduled unlock: {channel.name} ({channel.id})"
                        )

                        if not schedule.cycle:
                            schedule.unlock_day = None
                            schedule.unlock_time = None

                    except discord.Forbidden:
                        l.warning(f"[lock] No permission to unlock {channel.id}")
                        if not schedule.cycle:
                            to_remove.append(idx)
                    except Exception as e:
                        l.error(f"[lock] Failed to unlock {channel.id}: {e}")

            # 非循环且无剩余操作，移除
            if not schedule.cycle:
                if (
                    not schedule.lock_day
                    and not schedule.lock_time
                    and not schedule.unlock_day
                    and not schedule.unlock_time
                ):
                    to_remove.append(idx)

        # 批量移除（从后往前）
        for idx in sorted(set(to_remove), reverse=True):
            self.store.remove_by_index(idx)

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
