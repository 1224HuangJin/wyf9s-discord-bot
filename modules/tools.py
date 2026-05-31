# c!ding: utf-8
from uuid import uuid4 as uuid
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
import random
import re

from loguru import logger as l
import discord
from discord import app_commands
from discord.ext import commands

from config import ConfigModel


def _parse_time_or_id(value: str | None, label: str) -> tuple[discord.Object | None, datetime | None, str | None]:
    if not value or not value.strip():
        return None, None, None

    value = value.strip()

    if value.isdigit():
        return discord.Object(id=int(value)), None, None

    m = re.fullmatch(r'(\d+[dhm])+', value)
    if m:
        td = timedelta()
        for num, unit in re.findall(r'(\d+)([dhm])', value):
            n = int(num)
            if unit == 'd':
                td += timedelta(days=n)
            elif unit == 'h':
                td += timedelta(hours=n)
            elif unit == 'm':
                td += timedelta(minutes=n)
        return None, datetime.now(timezone.utc) - td, None

    try:
        cleaned = value.replace('Z', '+00:00')
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return None, dt, None
    except ValueError:
        pass

    return None, None, f'{label}: `{value}` 格式无效 (支持: 消息ID, 相对时间如 30m/2h/1d, ISO 时间)'


class ConfirmClearView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.confirmed: bool | None = None

    @discord.ui.button(label='确认删除', style=discord.ButtonStyle.danger)
    async def btn_confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        self.stop()
        await interaction.response.defer()
        await interaction.edit_original_response(content=':broom: **正在执行...**', view=None)

    @discord.ui.button(label='取消', style=discord.ButtonStyle.secondary)
    async def btn_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        self.stop()
        await interaction.response.defer()
        await interaction.edit_original_response(content=':x: **操作已取消**', view=None)

    async def on_timeout(self):
        self.confirmed = False


class ToolsModule:
    c: ConfigModel
    client: commands.Bot

    def __init__(self, config: ConfigModel, client: commands.Bot):
        self.c = config
        self.client = client

        # ========== Tools ==========

        # ----- Random - 随机数 -----

        @client.tree.command(
            name='random',
            description='生成自定义范围的随机数'
        )
        @app_commands.describe(
            min_num='最小值 (默认: 1)',
            max_num='最大值 (默认: 114514)'
        )
        async def slash_random_number(
            interaction: discord.Interaction,
            min_num: int = 1,
            max_num: int = 114514
        ):
            try:
                if min_num > max_num:
                    min_num, max_num = max_num, min_num

                result = random.randint(min_num, max_num)
                await interaction.response.send_message(
                    f':game_die: `{min_num}` - `{max_num}` 的随机数：**`{result}`**'
                )
            except ValueError:
                await interaction.response.send_message(
                    ':x: 请输入有效的整数范围！',
                    ephemeral=True,
                    delete_after=10
                )

        # ----- UUID -----

        @client.tree.command(
            name='uuid',
            description='生成一个 UUID'
        )
        @app_commands.describe(
            delete_after='在多久后删除 (s)'
        )
        async def slash_random_uuid(
            interaction: discord.Interaction,
            delete_after: int = self.c.secret_message_delay
        ):
            now = int(datetime.now().timestamp())
            await interaction.response.send_message(
                f':lock: 随机生成 UUID: **```{uuid()}```**> 此条消息仅你可见, 且将在 <t:{now + delete_after}:R> 删除',
                ephemeral=True,
                delete_after=delete_after
            )

        # ----- Delete Message - 删除消息 -----

        @client.tree.command(
            name='delete',
            description='删除消息'
        )
        @app_commands.describe(
            message_id='要删除的消息 ID',
            show_to_public='是否公开显示删除结果'
        )
        async def delete_message(
            interaction: discord.Interaction,
            message_id: str,
            show_to_public: bool = False
        ):
            if not self._can_use_delete(interaction.user):
                await self._deny(interaction, ':x: **你没有权限使用此指令** :x:')
                return

            if not message_id:
                await interaction.response.send_message(
                    ':x: **未指定要删除的消息 (通过回复消息或指定消息 ID)** :x:',
                    ephemeral=True,
                    delete_after=10
                )
                return

            try:
                message_id_int = int(message_id)
                message = interaction.channel.get_partial_message(message_id_int)  # type: ignore
                await message.delete()
            except discord.Forbidden:
                await interaction.response.send_message(
                    ':x: **权限不足, 无法删除此消息** :x:',
                    ephemeral=True,
                    delete_after=10
                )
            except discord.NotFound:
                await interaction.response.send_message(
                    f':x: **找不到 ID 为 `{message_id}` 的消息** :x:',
                    ephemeral=True,
                    delete_after=10
                )
            except ValueError:
                await interaction.response.send_message(
                    f':x: **消息 ID 不为整数: `{message_id}`** :x:',
                    ephemeral=True,
                    delete_after=10
                )
            except Exception as e:
                await interaction.response.send_message(
                    f':x: **删除消息 `{message_id}` 时出错: `{e}`** :x:',
                    ephemeral=True,
                    delete_after=10
                )
            else:
                await interaction.response.send_message(
                    f':white_check_mark: **删除消息 `{message_id}` 成功!** :white_check_mark:',
                    ephemeral=not show_to_public
                )

        # ----- Clear Message - 批量清除消息 -----

        @client.tree.command(
            name='clear-message',
            description='按条件批量清除消息'
        )
        @app_commands.describe(
            user='目标用户 (单个, 选择器)',
            user_ids='目标用户 ID 列表 (逗号分隔, 可填多个)',
            webhook_ids='目标 Webhook ID 列表 (逗号分隔, 可填多个)',
            nick_pattern='目标昵称通配符 (fnmatch, 例如 "*bot*")',
            content_pattern='消息内容通配符 (fnmatch, 例如 "*error*")',
            message_count='每个频道最多检查多少条消息 (不填/0 = 不限制但较慢)',
            within_minutes='仅清除最近几分钟内的消息 (不填/0 = 不限制)',
            scope='清除消息的范围: "channel" (单个频道, 默认) 或 "server" (整个服务器)',
            channel='指定频道 (仅在 scope=channel 时生效, 未设置则使用指令所在频道)',
            start='起始范围: 消息ID 或 相对/绝对时间 (例如 "1234567890" / "30m" / "2h" / "1d" / ISO时间)',
            end='结束范围: 消息ID 或 相对/绝对时间 (例如 "1234567890" / "30m" / "2h" / "1d" / ISO时间)',
        )
        async def clear_message(
            interaction: discord.Interaction,
            user: discord.User | None = None,
            user_ids: str | None = None,
            webhook_ids: str | None = None,
            nick_pattern: str | None = None,
            content_pattern: str | None = None,
            message_count: int | None = None,
            within_minutes: int | None = None,
            scope: str = 'channel',
            channel: discord.TextChannel | None = None,
            start: str | None = None,
            end: str | None = None,
        ):
            if not self._can_use_clear_message(interaction.user, interaction.guild):
                await self._deny(interaction, ':x: **你没有权限使用此指令** :x:')
                return

            await interaction.response.defer()

            message_limit = message_count if message_count is not None else 0
            minutes_limit = within_minutes if within_minutes is not None else 0

            if message_limit < 0:
                await interaction.followup.send(':x: **message_count 不能小于 0** :x:', ephemeral=True)
                return

            if minutes_limit < 0:
                await interaction.followup.send(':x: **within_minutes 不能小于 0** :x:', ephemeral=True)
                return

            has_time_range = bool(start or end)
            has_legacy_restriction = minutes_limit > 0 or message_limit > 0
            has_match_filter = bool(
                user or (user_ids and user_ids.strip())
                or (webhook_ids and webhook_ids.strip())
                or (nick_pattern and nick_pattern.strip())
                or (content_pattern and content_pattern.strip())
            )

            if has_time_range and has_legacy_restriction:
                await interaction.followup.send(
                    ':x: **start/end 不能与 within_minutes/message_count 同时使用** :x:',
                    ephemeral=True
                )
                return

            if not has_time_range and message_limit == 0 and minutes_limit == 0:
                await interaction.followup.send(':x: **message_count 和 within_minutes 不能同时不限制，请至少设置一个** :x:', ephemeral=True)
                return

            if not has_time_range and not has_legacy_restriction and not has_match_filter:
                await interaction.followup.send(
                    ':x: **必须指定至少一种过滤条件或范围限制 (user/user_ids/webhook_ids/nick_pattern/content_pattern/start/end/within_minutes/message_count)** :x:',
                    ephemeral=True
                )
                return

            def parse_ids(raw_ids: str, label: str) -> tuple[set[int] | None, str]:
                parts = [part.strip() for part in raw_ids.replace('，', ',').split(',') if part.strip()]
                if not parts:
                    return None, f'{label} 为空'
                values: set[int] = set()
                for part in parts:
                    if not part.isdigit():
                        return None, f'{label} 中包含非法 ID: `{part}`'
                    values.add(int(part))
                return values, ''

            target_user_ids: set[int] = set()
            target_webhook_ids: set[int] = set()
            nick_pattern_filter: str | None = None
            content_pattern_filter: str | None = None
            match_types: list[str] = []

            if user:
                target_user_ids = {user.id}
                match_types.append('user')
            if user_ids and user_ids.strip():
                parsed, err = parse_ids(user_ids.strip(), 'user_ids')
                if not parsed:
                    await interaction.followup.send(f':x: **{err}** :x:', ephemeral=True)
                    return
                target_user_ids |= parsed
                if 'user_ids' not in match_types:
                    match_types.append('user_ids')
            if webhook_ids and webhook_ids.strip():
                parsed, err = parse_ids(webhook_ids.strip(), 'webhook_ids')
                if not parsed:
                    await interaction.followup.send(f':x: **{err}** :x:', ephemeral=True)
                    return
                target_webhook_ids = parsed
                match_types.append('webhook_ids')
            if nick_pattern and nick_pattern.strip():
                nick_pattern_filter = nick_pattern.strip()
                match_types.append('nick_pattern')
            if content_pattern and content_pattern.strip():
                content_pattern_filter = content_pattern.strip()
                match_types.append('content_pattern')

            scope = scope.lower().strip()
            if scope not in ['channel', 'server']:
                await interaction.followup.send(
                    f':x: **无效的 scope 参数: `{scope}`, 只支持 "channel" 或 "server"** :x:',
                    ephemeral=True
                )
                return

            target_channels: list[discord.TextChannel] = []
            if scope == 'channel':
                if channel:
                    target_channels.append(channel)
                else:
                    target_channels.append(interaction.channel)  # type: ignore
            else:
                if not interaction.guild:
                    await interaction.followup.send(':x: **此指令只能在服务器内使用** :x:', ephemeral=True)
                    return
                target_channels = [ch for ch in interaction.guild.channels if isinstance(ch, discord.TextChannel)]

            start_obj: discord.Object | None = None
            start_dt: datetime | None = None
            end_obj: discord.Object | None = None
            end_dt: datetime | None = None
            if has_time_range:
                if start:
                    start_obj, start_dt, start_err = _parse_time_or_id(start, 'start')
                    if start_err:
                        await interaction.followup.send(f':x: **{start_err}** :x:', ephemeral=True)
                        return
                if end:
                    end_obj, end_dt, end_err = _parse_time_or_id(end, 'end')
                    if end_err:
                        await interaction.followup.send(f':x: **{end_err}** :x:', ephemeral=True)
                        return
                if start_dt and end_dt and start_dt > end_dt:
                    await interaction.followup.send(':x: **start 时间不能晚于 end 时间** :x:', ephemeral=True)
                    return

            cutoff_time = None
            start_time_bound: datetime | None = None
            end_time_bound: datetime | None = None
            if has_time_range:
                start_time_bound = start_dt
                end_time_bound = end_dt
            elif minutes_limit > 0:
                cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes_limit)

            now = datetime.now(timezone.utc)
            need_confirm = False
            confirm_reasons: list[str] = []

            if has_legacy_restriction and message_limit > 30:
                need_confirm = True
                confirm_reasons.append(f'message_count ({message_limit}) 超过 30')

            if has_time_range:
                if start_dt and (now - start_dt) > timedelta(days=1):
                    need_confirm = True
                    confirm_reasons.append('start 范围包含超过 1 天前的消息')
                elif end_dt and not start_dt and (now - end_dt) > timedelta(days=1):
                    need_confirm = True
                    confirm_reasons.append('end 范围包含超过 1 天前的消息')
            elif not has_time_range:
                if minutes_limit > 1440:
                    need_confirm = True
                    confirm_reasons.append(f'within_minutes ({minutes_limit}) 超过 1 天')
                elif minutes_limit == 0 and match_types:
                    need_confirm = True
                    confirm_reasons.append('未指定时间范围限制，可能包含超过 1 天前的消息')

            if need_confirm:
                view = ConfirmClearView()
                await interaction.followup.send(
                    ':warning: **确认操作**\n拟删除范围可能较大：\n' +
                    '\n'.join(f'• {r}' for r in confirm_reasons) +
                    '\n\n是否继续？',
                    view=view,
                    ephemeral=True
                )
                await view.wait()
                if not view.confirmed:
                    return

            checked_messages_by_channel: dict[int, list[discord.Message]] = {}
            checked_count = 0

            def message_matches(msg: discord.Message) -> bool:
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
                if target_webhook_ids and msg.webhook_id is not None and msg.webhook_id in target_webhook_ids:
                    return True
                if nick_pattern_filter:
                    display_name = getattr(msg.author, 'display_name', msg.author.name)
                    if fnmatch(display_name, nick_pattern_filter):
                        return True
                if content_pattern_filter:
                    if fnmatch(msg.content, content_pattern_filter):
                        return True
                return False

            history_kwargs: dict = {}
            if has_time_range:
                history_kwargs['limit'] = None
                if end_obj:
                    history_kwargs['before'] = end_obj
                elif end_dt:
                    history_kwargs['before'] = end_dt
                if start_obj:
                    history_kwargs['after'] = start_obj
                elif start_dt:
                    history_kwargs['after'] = start_dt
            else:
                history_kwargs['limit'] = message_limit if message_limit > 0 else None

            for target_channel in target_channels:
                try:
                    async for msg in target_channel.history(**history_kwargs):
                        if cutoff_time is not None and msg.created_at < cutoff_time:
                            break
                        if start_time_bound is not None and msg.created_at < start_time_bound:
                            break
                        if message_matches(msg):
                            checked_messages_by_channel.setdefault(target_channel.id, []).append(msg)
                            checked_count += 1
                except discord.Forbidden:
                    pass
                except Exception as e:
                    l.warning(f'获取频道 {target_channel.name} ({target_channel.id}) 消息时出错: {e}')

            if checked_count == 0:
                match_descs: list[str] = []
                if target_user_ids:
                    if len(target_user_ids) == 1 and match_types == ['user']:
                        match_descs.append(f'用户 {user.mention if user else "[unknown]"}')
                    else:
                        match_descs.append(f'用户 ID `{sorted(target_user_ids)}`')
                if target_webhook_ids:
                    match_descs.append(f'Webhook ID `{sorted(target_webhook_ids)}`')
                if nick_pattern_filter:
                    match_descs.append(f'昵称通配符 `{nick_pattern_filter}`')
                if content_pattern_filter:
                    match_descs.append(f'内容通配符 `{content_pattern_filter}`')
                match_desc = ' / '.join(match_descs) if match_descs else '无过滤条件'
                time_desc = ''
                if has_time_range:
                    parts = []
                    if start:
                        parts.append(f'起始 `{start}`')
                    if end:
                        parts.append(f'结束 `{end}`')
                    time_desc = ', '.join(parts)
                elif minutes_limit > 0:
                    time_desc = f'最近 **{minutes_limit}** 分钟内'
                await interaction.followup.send(f':broom: 未找到匹配 **{match_desc}** {(time_desc + " ") if time_desc else ""}的消息')
                return

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
                    batch = messages[i:i + 100]
                    valid_batch = [
                        msg for msg in batch
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
                        await interaction.followup.send(
                            f':x: **权限不足, 无法删除频道 `{target_channel.name}` 中的消息** :x:',
                            ephemeral=True
                        )
                        return
                    except discord.HTTPException as e:
                        if e.code == 50034:
                            too_old_count += len(valid_batch)
                        elif e.code == 10008:
                            pass
                        else:
                            l.error(f'批量删除消息时出错 (channel={target_channel.id}, batch={i}:{i + len(batch)}): {e}')
                            failed_count += len(valid_batch)
                    except Exception as e:
                        l.error(f'批量删除消息时出错 (channel={target_channel.id}): {e}')
                        failed_count += len(valid_batch)

            scope_text = '频道' if scope == 'channel' else '服务器'
            channel_name = getattr(interaction.channel, 'name', '[DM Channel]')
            channel_info = f' (频道: {channel_name})' if scope == 'channel' else ''
            match_descs_result: list[str] = []
            if target_user_ids:
                if len(target_user_ids) == 1 and set(match_types) == {'user'}:
                    match_descs_result.append(f'用户 {user.mention if user else "[unknown]"}')
                else:
                    match_descs_result.append(f'用户 ID `{sorted(target_user_ids)}`')
            if target_webhook_ids:
                match_descs_result.append(f'Webhook ID `{sorted(target_webhook_ids)}`')
            if nick_pattern_filter:
                match_descs_result.append(f'昵称通配符 `{nick_pattern_filter}`')
            if content_pattern_filter:
                match_descs_result.append(f'内容通配符 `{content_pattern_filter}`')
            match_desc_result = ' / '.join(match_descs_result) if match_descs_result else '无过滤条件'

            time_desc_result: str
            if has_time_range:
                parts = []
                if start:
                    parts.append(f'起始 `{start}`')
                if end:
                    parts.append(f'结束 `{end}`')
                time_desc_result = ', '.join(parts) if parts else '不限制'
            elif minutes_limit > 0:
                time_desc_result = f'最近 **{minutes_limit}** 分钟'
            else:
                time_desc_result = '不限制'

            await interaction.followup.send(
                f':broom: 批量清除消息完成 :broom:'
                f'\n范围: **{scope_text}**{channel_info}'
                f'\n匹配方式: **{match_desc_result}**'
                f'\n时间范围: {time_desc_result}'
                + (f'\n每频道检查上限: **{message_limit}** 条' if not has_time_range and message_limit > 0 else '')
                + f'\n匹配消息 **{checked_count}** 条'
                f'\n成功删除: **{success_count}** 条'
                + (f'\n因超过 14 天不可删: **{too_old_count}** 条' if too_old_count > 0 else '')
                + (f'\n其他原因失败: **{failed_count}** 条' if failed_count > 0 else '')
            )

        # ========== Others ==========

        @client.tree.command(
            name='move-channel',
            description='移动当前或指定频道到指定分类或频道的前/后'
        )
        @app_commands.describe(
            target_channel='要操作的频道 (可选，默认为当前频道)',
            category='目标分类 (可选)',
            before='在这个频道之前 (可选)',
            after='在这个频道之后 (可选)',
            sync_perm='是否同步目标分类的权限 (可选，默认为 True)'
        )
        async def move_channel(
            interaction: discord.Interaction,
            target_channel: discord.abc.GuildChannel | None = None,
            category: discord.CategoryChannel | None = None,
            before: discord.abc.GuildChannel | None = None,
            after: discord.abc.GuildChannel | None = None,
            sync_perm: bool = True
        ):
            if not category and not before and not after:
                await interaction.response.send_message(
                    ':x: **参数错误：请至少提供 `category`、`before` 或 `after` 中的一个参数**',
                    ephemeral=True
                )
                return

            if before and after:
                await interaction.response.send_message(
                    ':x: **参数错误：不能同时指定 `before` 和 `after`**',
                    ephemeral=True
                )
                return

            channel = target_channel or interaction.channel
            if not isinstance(channel, discord.abc.GuildChannel):
                await interaction.response.send_message(
                    ':x: **此指令只能对服务器频道使用**',
                    ephemeral=True
                )
                return

            kwargs = {}
            update_category = False
            target_category = None

            if category:
                target_category = category
                update_category = True

            if before:
                if not update_category:
                    target_category = getattr(before, 'category', None)
                    update_category = True
                kwargs['position'] = before.position
            elif after:
                if not update_category:
                    target_category = getattr(after, 'category', None)
                    update_category = True
                kwargs['position'] = after.position + 1

            if update_category:
                kwargs['category'] = target_category
                if sync_perm:
                    kwargs['sync_permissions'] = True

            try:
                await channel.edit(**kwargs)

                msg_parts = []
                if category:
                    msg_parts.append(f'分类 `{category.name}`')
                if before:
                    msg_parts.append(f'`{before.name}` 之前')
                elif after:
                    msg_parts.append(f'`{after.name}` 之后')

                await interaction.response.send_message(
                    f':white_check_mark: **已成功将 {channel.mention} 移动到 {" / ".join(msg_parts)}**'
                )
            except discord.Forbidden:
                await interaction.response.send_message(
                    ':x: **权限不足：我需要 `管理频道 (Manage Channels)` 权限才能执行此操作，或者我的角色层级不够**',
                    ephemeral=True
                )
            except discord.HTTPException as e:
                await interaction.response.send_message(
                    f':x: **移动失败：API 请求错误 ({e.status} - {e.text})**',
                    ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(
                    f':x: **移动失败：发生未知错误：`{e}`**',
                    ephemeral=True
                )

        @client.tree.command(
            name='sync',
            description='同步指令列表'
        )
        async def sync(interaction: discord.Interaction):
            if not self._is_config_admin(interaction.user):
                await self._deny(interaction, ':x: **你没有权限使用此指令** :x:')
                return

            await interaction.response.defer()
            await client.tree.sync()
            l.info('Command tree synced.')
            await interaction.followup.send('**:white_check_mark: 斜杠指令列表已同步**')

        # ----- Prefix Command -----

        @client.command(name='sync-commands')
        async def sync_commands(ctx: commands.Context):
            if not self._is_config_admin(ctx.author):
                await ctx.send('**:x: 你没有权限使用此指令**', delete_after=10)
                return

            await ctx.defer()
            await client.tree.sync()
            await ctx.send('**:white_check_mark: 斜杠指令列表已同步**')

    def _matches_identity(self, user: discord.User | discord.Member, values: list[int | str]) -> bool:
        for value in values:
            if user.id == value or user.name == value:
                return True
            if isinstance(value, str) and value.isdigit() and user.id == int(value):
                return True
        return False

    def _is_server_admin(self, user: discord.User | discord.Member) -> bool:
        return isinstance(user, discord.Member) and user.guild_permissions.administrator

    def _is_config_admin(self, user: discord.User | discord.Member) -> bool:
        return self._matches_identity(user, self.c.admins.users)

    def _is_mod(self, user: discord.User | discord.Member, guild: discord.Guild | None = None) -> bool:
        if self._is_server_admin(user) or self._is_config_admin(user):
            return True

        if isinstance(user, discord.Member):
            if self._matches_identity(user, self.c.mods.users):
                return True

            if guild is not None:
                guild_users = self.c.mods.guilds.get(guild.id, self.c.mods.guilds.get(str(guild.id), []))
                return self._matches_identity(user, guild_users)

        return False

    def _can_use_clear_message(self, user: discord.User | discord.Member, guild: discord.Guild | None = None) -> bool:
        return self._is_mod(user, guild)

    def _can_use_delete(self, user: discord.User | discord.Member) -> bool:
        return self._is_mod(user)

    async def _deny(self, interaction: discord.Interaction, message: str):
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
