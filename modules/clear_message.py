from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
import re

from loguru import logger as l
import discord

from config import ConfigModel
from modules.audit import AuditLogger


CLEAR_MESSAGE_MARKER = "[clear-message]"


def _parse_time_or_id(
    value: str | None, label: str
) -> tuple[discord.Object | None, datetime | None, str | None]:
    if not value or not value.strip():
        return None, None, None

    value = value.strip()

    if value.isdigit():
        return discord.Object(id=int(value)), None, None

    m = re.fullmatch(r"(\d+[dhm])+", value)
    if m:
        td = timedelta()
        for num, unit in re.findall(r"(\d+)([dhm])", value):
            n = int(num)
            if unit == "d":
                td += timedelta(days=n)
            elif unit == "h":
                td += timedelta(hours=n)
            elif unit == "m":
                td += timedelta(minutes=n)
        return None, datetime.now(timezone.utc) - td, None

    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return None, dt, None
    except ValueError:
        pass

    return (
        None,
        None,
        f"{label}: `{value}` 格式无效 (支持: 消息ID, 相对时间如 30m/2h/1d, ISO 时间)",
    )


class ClearMessageService:
    def __init__(
        self,
        config: ConfigModel,
        client: discord.Client,
        audit: AuditLogger | None,
    ):
        self.c = config
        self.client = client
        self.audit = audit

    async def do_clear_message(
        self,
        author: discord.User | discord.Member,
        guild: discord.Guild | None,
        channel: discord.abc.GuildChannel
        | discord.abc.PrivateChannel
        | discord.Thread
        | None,
        user: discord.User | None = None,
        user_ids: str | None = None,
        webhook_ids: str | None = None,
        nick_pattern: str | None = None,
        content_pattern: str | None = None,
        message_count: int | None = None,
        within_minutes: int | None = None,
        scope: str = "channel",
        channel_target: discord.abc.GuildChannel | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> str:
        message_limit = message_count if message_count is not None else 0
        minutes_limit = within_minutes if within_minutes is not None else 0

        if message_limit < 0:
            return ":x: **message_count 不能小于 0** :x:"

        if minutes_limit < 0:
            return ":x: **within_minutes 不能小于 0** :x:"

        has_time_range = bool(start or end)
        has_legacy_restriction = minutes_limit > 0 or message_limit > 0
        has_match_filter = bool(
            user
            or (user_ids and user_ids.strip())
            or (webhook_ids and webhook_ids.strip())
            or (nick_pattern and nick_pattern.strip())
            or (content_pattern and content_pattern.strip())
        )

        if has_time_range and has_legacy_restriction:
            return ":x: **start/end 不能与 within_minutes/message_count 同时使用** :x:"

        if not has_time_range and message_limit == 0 and minutes_limit == 0:
            return ":x: **message_count 和 within_minutes 不能同时不限制，请至少设置一个** :x:"

        if not has_time_range and not has_legacy_restriction and not has_match_filter:
            return ":x: **必须指定至少一种过滤条件或范围限制** :x:"

        def parse_ids(raw_ids: str, label: str) -> tuple[set[int] | None, str]:
            parts = [
                part.strip()
                for part in raw_ids.replace("，", ",").split(",")
                if part.strip()
            ]
            if not parts:
                return None, f"{label} 为空"
            values: set[int] = set()
            for part in parts:
                if not part.isdigit():
                    return None, f"{label} 中包含非法 ID: `{part}`"
                values.add(int(part))
            return values, ""

        target_user_ids: set[int] = set()
        target_webhook_ids: set[int] = set()
        nick_pattern_filter: str | None = None
        content_pattern_filter: str | None = None
        match_types: list[str] = []

        if user:
            target_user_ids = {user.id}
            match_types.append("user")
        if user_ids and user_ids.strip():
            parsed, err = parse_ids(user_ids.strip(), "user_ids")
            if not parsed:
                return f":x: **{err}** :x:"
            target_user_ids |= parsed
            if "user_ids" not in match_types:
                match_types.append("user_ids")
        if webhook_ids and webhook_ids.strip():
            parsed, err = parse_ids(webhook_ids.strip(), "webhook_ids")
            if not parsed:
                return f":x: **{err}** :x:"
            target_webhook_ids = parsed
            match_types.append("webhook_ids")
        if nick_pattern and nick_pattern.strip():
            nick_pattern_filter = nick_pattern.strip()
            match_types.append("nick_pattern")
        if content_pattern and content_pattern.strip():
            content_pattern_filter = content_pattern.strip()
            match_types.append("content_pattern")

        scope = scope.lower().strip()
        if scope not in ["channel", "server"]:
            return f':x: **无效的 scope 参数: `{scope}`, 只支持 "channel" 或 "server"** :x:'

        target_channels: list[
            discord.TextChannel | discord.VoiceChannel | discord.StageChannel
        ] = []
        if scope == "channel":
            if channel_target:
                target_channels.append(channel_target)  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
            else:
                target_channels.append(channel)  # type: ignore[arg-type]  # ty:ignore[invalid-argument-type]
        else:
            if not guild:
                return ":x: **此指令只能在服务器内使用** :x:"
            target_channels = [
                ch
                for ch in guild.channels
                if isinstance(
                    ch,
                    (discord.TextChannel, discord.VoiceChannel, discord.StageChannel),
                )
            ]

        start_obj: discord.Object | None = None
        start_dt: datetime | None = None
        end_obj: discord.Object | None = None
        end_dt: datetime | None = None
        if has_time_range:
            if start:
                start_obj, start_dt, start_err = _parse_time_or_id(start, "start")
                if start_err:
                    return f":x: **{start_err}** :x:"
            if end:
                end_obj, end_dt, end_err = _parse_time_or_id(end, "end")
                if end_err:
                    return f":x: **{end_err}** :x:"
            if start_dt and end_dt and start_dt > end_dt:
                return ":x: **start 时间不能晚于 end 时间** :x:"

        # 如果 start 和 end 都是消息 ID，验证顺序并获取消息
        start_msg: discord.Message | None = None
        end_msg: discord.Message | None = None
        if start_obj and end_obj:
            # 需要确定频道来获取消息
            # 当 scope 为 "channel" 时，使用 target_channels[0]
            # 当 scope 为 "server" 时，我们无法确定频道，因此跳过验证
            if scope == "channel" and target_channels:
                channel_for_fetch = target_channels[0]
                try:
                    start_msg = await channel_for_fetch.fetch_message(start_obj.id)
                except discord.NotFound:
                    return f":x: **找不到 ID 为 `{start_obj.id}` 的 start 消息** :x:"
                except discord.HTTPException as e:
                    return f":x: **获取 start 消息时出错: {e}** :x:"
                try:
                    end_msg = await channel_for_fetch.fetch_message(end_obj.id)
                except discord.NotFound:
                    return f":x: **找不到 ID 为 `{end_obj.id}` 的 end 消息** :x:"
                except discord.HTTPException as e:
                    return f":x: **获取 end 消息时出错: {e}** :x:"
                if start_msg.created_at > end_msg.created_at:
                    return ":x: **start 消息不能晚于 end 消息** :x:"

        cutoff_time = None
        start_time_bound: datetime | None = None
        end_time_bound: datetime | None = None
        if has_time_range:
            start_time_bound = start_dt
            end_time_bound = end_dt
        elif minutes_limit > 0:
            cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes_limit)

        now = datetime.now(timezone.utc)

        checked_messages_by_channel: dict[int, list[discord.Message]] = {}
        checked_count = 0

        def message_matches(msg: discord.Message) -> bool:
            bot_user = self.client.user
            if (
                bot_user is not None
                and msg.author.id == bot_user.id
                and CLEAR_MESSAGE_MARKER in msg.content
            ):
                return False
            if cutoff_time is not None and msg.created_at < cutoff_time:
                return False
            if start_time_bound is not None and msg.created_at < start_time_bound:
                return False
            if end_time_bound is not None and msg.created_at > end_time_bound:
                return False
            if not match_types:
                return True
            if target_user_ids and msg.author.id in target_user_ids:
                return True
            if (
                target_webhook_ids
                and msg.webhook_id is not None
                and msg.webhook_id in target_webhook_ids
            ):
                return True
            if nick_pattern_filter:
                display_name = getattr(msg.author, "display_name", msg.author.name)
                if fnmatch(display_name, nick_pattern_filter):
                    return True
            if content_pattern_filter and fnmatch(msg.content, content_pattern_filter):
                return True
            return False

        history_kwargs: dict = {}
        if has_time_range:
            history_kwargs["limit"] = None
            if end_obj:
                history_kwargs["before"] = end_obj
            elif end_dt:
                history_kwargs["before"] = end_dt
            if start_obj:
                history_kwargs["after"] = start_obj
            elif start_dt:
                history_kwargs["after"] = start_dt
        else:
            history_kwargs["limit"] = message_limit if message_limit > 0 else None

        for target_channel in target_channels:
            try:
                async for msg in target_channel.history(**history_kwargs):
                    if cutoff_time is not None and msg.created_at < cutoff_time:
                        break
                    if (
                        start_time_bound is not None
                        and msg.created_at < start_time_bound
                    ):
                        break
                    if message_matches(msg):
                        checked_messages_by_channel.setdefault(
                            target_channel.id, []
                        ).append(msg)
                        checked_count += 1
            except discord.Forbidden:
                pass
            except Exception as e:
                l.warning(
                    f"获取频道 {target_channel.name} ({target_channel.id}) 消息时出错: {e}"
                )

        # 将 start_msg 和 end_msg 添加到结果中（如果它们符合过滤条件且尚未包含）
        if start_msg and end_msg and scope == "channel" and target_channels:
            channel_id = target_channels[0].id
            existing_messages = checked_messages_by_channel.get(channel_id, [])
            if start_msg not in existing_messages and message_matches(start_msg):
                checked_messages_by_channel.setdefault(channel_id, []).append(start_msg)
                checked_count += 1
            if end_msg not in existing_messages and message_matches(end_msg):
                checked_messages_by_channel.setdefault(channel_id, []).append(end_msg)
                checked_count += 1

        if checked_count == 0:
            match_descs: list[str] = []
            if target_user_ids:
                if len(target_user_ids) == 1 and match_types == ["user"]:
                    match_descs.append(f"用户 {user.mention if user else '[unknown]'}")
                else:
                    match_descs.append(f"用户 ID `{sorted(target_user_ids)}`")
            if target_webhook_ids:
                match_descs.append(f"Webhook ID `{sorted(target_webhook_ids)}`")
            if nick_pattern_filter:
                match_descs.append(f"昵称通配符 `{nick_pattern_filter}`")
            if content_pattern_filter:
                match_descs.append(f"内容通配符 `{content_pattern_filter}`")
            match_desc = " / ".join(match_descs) if match_descs else "无过滤条件"
            time_desc = ""
            if has_time_range:
                parts = []
                if start:
                    parts.append(f"起始 `{start}`")
                if end:
                    parts.append(f"结束 `{end}`")
                time_desc = ", ".join(parts)
            elif minutes_limit > 0:
                time_desc = f"最近 **{minutes_limit}** 分钟内"
            return f":broom: 未找到匹配 **{match_desc}** {(time_desc + ' ') if time_desc else ''}的消息"

        success_count = 0
        failed_count = 0
        too_old_count = 0
        channel_map = {ch.id: ch for ch in target_channels}

        for channel_id, messages in checked_messages_by_channel.items():
            target_channel = channel_map.get(channel_id)
            if target_channel is None:
                failed_count += len(messages)
                continue
            messages.sort(key=lambda m: m.created_at, reverse=True)
            for i in range(0, len(messages), 100):
                batch = messages[i : i + 100]
                valid_batch = [
                    msg
                    for msg in batch
                    if (now - msg.created_at).total_seconds() < (14 * 86400 - 300)
                ]
                if not valid_batch:
                    too_old_count += len(batch)
                    continue
                try:
                    if len(valid_batch) == 1:
                        await valid_batch[0].delete()
                        success_count += 1
                    else:
                        await target_channel.delete_messages(valid_batch)
                        success_count += len(valid_batch)
                except discord.Forbidden:
                    return f":x: **权限不足, 无法删除频道 `{target_channel.name}` 中的消息** :x:"
                except discord.HTTPException as e:
                    if e.code == 50034:
                        too_old_count += len(valid_batch)
                    elif e.code == 10008:
                        pass
                    else:
                        l.error(
                            f"批量删除消息时出错 (channel={target_channel.id}, batch={i}:{i + len(batch)}): {e}"
                        )
                        failed_count += len(valid_batch)
                except Exception as e:
                    l.error(f"批量删除消息时出错 (channel={target_channel.id}): {e}")
                    failed_count += len(valid_batch)

        scope_text = "频道" if scope == "channel" else "服务器"
        channel_name = getattr(channel, "name", "[DM Channel]")
        channel_info = f" (频道: {channel_name})" if scope == "channel" else ""
        match_descs_result: list[str] = []
        if target_user_ids:
            if len(target_user_ids) == 1 and set(match_types) == {"user"}:
                match_descs_result.append(
                    f"**用户 {user.mention if user else '[unknown]'}**"
                )
            else:
                match_descs_result.append(f"**用户 ID `{sorted(target_user_ids)}`**")
        if target_webhook_ids:
            match_descs_result.append(f"**Webhook ID `{sorted(target_webhook_ids)}`**")
        if nick_pattern_filter:
            match_descs_result.append(f"**昵称通配符 `{nick_pattern_filter}`**")
        if content_pattern_filter:
            match_descs_result.append(f"**内容通配符 `{content_pattern_filter}`**")
        match_desc_result = (
            " / ".join(match_descs_result) if match_descs_result else "**无过滤条件**"
        )

        time_desc_result: str
        if has_time_range:
            parts = []
            if start:
                parts.append(f"起始 `{start}`")
            if end:
                parts.append(f"结束 `{end}`")
            time_desc_result = ", ".join(parts) if parts else "不限制"
        elif minutes_limit > 0:
            time_desc_result = f"最近 **{minutes_limit}** 分钟"
        else:
            time_desc_result = "不限制"

        result_msg = (
            f":broom: 批量清除消息完成 :broom:"
            f"\n范围: **{scope_text}**{channel_info}"
            f"\n匹配方式: {match_desc_result}"
            f"\n时间范围: {time_desc_result}"
            + (
                f"\n每频道检查上限: **{message_limit}** 条"
                if not has_time_range and message_limit > 0
                else ""
            )
            + f"\n匹配消息 **{checked_count}** 条"
            f"\n成功删除: **{success_count}** 条"
            + (
                f"\n因超过 14 天不可删: **{too_old_count}** 条"
                if too_old_count > 0
                else ""
            )
            + (f"\n其他原因失败: **{failed_count}** 条" if failed_count > 0 else "")
            + f"\n-# {CLEAR_MESSAGE_MARKER}"
        )

        if self.audit:
            await self.audit.log(
                action="clear-message",
                user=author,
                guild=guild,
                channel=channel,
                detail=(
                    f"范围: {scope_text}{channel_info}"
                    f"\n匹配方式: {match_desc_result}"
                    f"\n时间范围: {time_desc_result}"
                    f"\n匹配 {checked_count} 条, 成功删除 {success_count} 条"
                    + (f", 超期 {too_old_count} 条" if too_old_count > 0 else "")
                    + (f", 失败 {failed_count} 条" if failed_count > 0 else "")
                ),
                success=failed_count == 0,
            )

        return result_msg
