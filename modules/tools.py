# c!ding: utf-8
from uuid import uuid4 as uuid
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
import random

from loguru import logger as l
import discord
from discord import app_commands
from discord.ext import commands

from config import ConfigModel


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
                    min_num, max_num = max_num, min_num  # 自动交换大小值

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
                f':lock: 随机生成 UUID: **```{uuid()}```**> 此条消息仅你可见, 且将在 <t:{now+delete_after}:R> 删除',
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
            if message_id:
                try:
                    message_id_int: int = int(message_id)
                    message = interaction.channel.get_partial_message(message_id_int)  # type: ignore
                    await message.delete()
                except discord.Forbidden:
                    await interaction.response.send_message(
                        f':x: **权限不足, 无法删除此消息** :x:',
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
            else:
                await interaction.response.send_message(
                    f':x: **未指定要删除的消息 (通过回复消息或指定消息 ID)** :x:',
                    ephemeral=True,
                    delete_after=10
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
            channel: discord.TextChannel | None = None
        ):
            await interaction.response.defer()

            message_limit = message_count if message_count is not None else 0
            minutes_limit = within_minutes if within_minutes is not None else 0

            if message_limit < 0:
                await interaction.followup.send(
                    ':x: **message_count 不能小于 0** :x:',
                    ephemeral=True
                )
                return

            if minutes_limit < 0:
                await interaction.followup.send(
                    ':x: **within_minutes 不能小于 0** :x:',
                    ephemeral=True
                )
                return

            if message_limit == 0 and minutes_limit == 0:
                await interaction.followup.send(
                    ':x: **message_count 和 within_minutes 不能同时不限制，请至少设置一个** :x:',
                    ephemeral=True
                )
                return

            match_inputs = {
                'user': '1' if user else '',
                'user_ids': user_ids.strip() if user_ids else '',
                'webhook_ids': webhook_ids.strip() if webhook_ids else '',
                'nick_pattern': nick_pattern.strip() if nick_pattern else '',
                'content_pattern': content_pattern.strip() if content_pattern else '',
            }
            active_match_types = [k for k, v in match_inputs.items() if v]
            if len(active_match_types) != 1:
                await interaction.followup.send(
                    ':x: **必须且只能提供一种匹配方式: user / user_ids / webhook_ids / nick_pattern / content_pattern** :x:',
                    ephemeral=True
                )
                return

            def parse_ids(raw_ids: str, label: str) -> tuple[set[int] | None, str]:
                parts = [
                    part.strip()
                    for part in raw_ids.replace('，', ',').split(',')
                    if part.strip()
                ]
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
            match_type = active_match_types[0]

            if match_type == 'user':
                target_user_ids = {user.id} if user else set()
            elif match_type == 'user_ids':
                parsed, err = parse_ids(match_inputs['user_ids'], 'user_ids')
                if not parsed:
                    await interaction.followup.send(
                        f':x: **{err}** :x:',
                        ephemeral=True
                    )
                    return
                target_user_ids = parsed
            elif match_type == 'webhook_ids':
                parsed, err = parse_ids(match_inputs['webhook_ids'], 'webhook_ids')
                if not parsed:
                    await interaction.followup.send(
                        f':x: **{err}** :x:',
                        ephemeral=True
                    )
                    return
                target_webhook_ids = parsed
            elif match_type == 'nick_pattern':
                nick_pattern = match_inputs['nick_pattern']
            else:
                content_pattern = match_inputs['content_pattern']

            # 验证 scope 参数
            scope = scope.lower().strip()
            if scope not in ['channel', 'server']:
                await interaction.followup.send(
                    f':x: **无效的 scope 参数: `{scope}`, 只支持 "channel" 或 "server"** :x:',
                    ephemeral=True
                )
                return

            # 确定目标频道列表
            target_channels: list[discord.TextChannel] = []

            if scope == 'channel':
                # 单个频道
                if channel:
                    target_channels.append(channel)
                else:
                    # 使用指令所在频道
                    target_channels.append(interaction.channel)  # type: ignore
            else:  # scope == 'server'
                # 整个服务器的所有文本频道
                target_channels = [ch for ch in interaction.guild.channels if isinstance(ch, discord.TextChannel)]  # type: ignore

            cutoff_time = None
            if minutes_limit > 0:
                cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=minutes_limit)

            # 收集要删除的消息
            checked_messages_by_channel: dict[int, list[discord.Message]] = {}
            checked_count = 0

            def message_matches(msg: discord.Message) -> bool:
                if cutoff_time is not None and msg.created_at < cutoff_time:
                    return False
                if match_type in ['user', 'user_ids']:
                    return msg.author.id in target_user_ids
                if match_type == 'webhook_ids':
                    return msg.webhook_id is not None and msg.webhook_id in target_webhook_ids
                if match_type == 'nick_pattern':
                    display_name = getattr(msg.author, 'display_name', msg.author.name)
                    return fnmatch(display_name, nick_pattern or '')
                return fnmatch(msg.content, content_pattern or '')

            for target_channel in target_channels:
                try:
                    async for msg in target_channel.history(limit=message_limit if message_limit > 0 else None):
                        if cutoff_time is not None and msg.created_at < cutoff_time:
                            break
                        if message_matches(msg):
                            if target_channel.id not in checked_messages_by_channel:
                                checked_messages_by_channel[target_channel.id] = []
                            checked_messages_by_channel[target_channel.id].append(msg)
                            checked_count += 1
                except discord.Forbidden:
                    # l.warning(f'无权限访问频道 {target_channel.name} ({target_channel.id})')
                    pass
                except Exception as e:
                    l.warning(f'获取频道 {target_channel.name} ({target_channel.id}) 消息时出错: {e}')

            if checked_count == 0:
                match_desc = {
                    'user': f'用户 **{user.mention if user else "[unknown]"}**',
                    'user_ids': f'用户 ID `{sorted(target_user_ids)}`',
                    'webhook_ids': f'Webhook ID `{sorted(target_webhook_ids)}`',
                    'nick_pattern': f'昵称通配符 `{nick_pattern}`',
                    'content_pattern': f'内容通配符 `{content_pattern}`'
                }[match_type]
                time_desc = f'且在最近 **{minutes_limit}** 分钟内' if minutes_limit > 0 else ''
                await interaction.followup.send(
                    f':broom: 未找到匹配 **{match_desc}** {time_desc}的消息'
                )
                return

            # 使用 bulk_delete API 删除消息 (Discord API 限制最多一次删除 100 条)
            success_count = 0
            failed_count = 0
            too_old_count = 0
            now = datetime.now(timezone.utc)
            channel_map = {ch.id: ch for ch in target_channels}

            # 按批次删除 (一次最多 100 条)
            for channel_id, messages in checked_messages_by_channel.items():
                target_channel = channel_map.get(channel_id)
                if target_channel is None:
                    failed_count += len(messages)
                    continue
                messages.sort(key=lambda m: m.created_at, reverse=True)
                for i in range(0, len(messages), 100):
                    batch = messages[i:i+100]
                    # 留 5 分钟余量，避免触发 14 天上限边界问题
                    valid_batch = [
                        msg for msg in batch
                        if (now - msg.created_at).total_seconds() < (14 * 86400 - 300)
                    ]
                    if not valid_batch:
                        too_old_count += len(batch)
                        continue
                    try:
                        # bulk_delete 至少 2 条，单条走 delete
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
                        if e.code == 50034:   # Messages older than 14 days
                            too_old_count += len(valid_batch)
                        elif e.code == 10008:  # Unknown message
                            pass
                        else:
                            l.error(f'批量删除消息时出错 (channel={target_channel.id}, batch={i}:{i+len(batch)}): {e}')
                            failed_count += len(valid_batch)
                    except Exception as e:
                        l.error(f'批量删除消息时出错 (channel={target_channel.id}): {e}')
                        failed_count += len(valid_batch)

            # 生成统计信息
            scope_text = '频道' if scope == 'channel' else '服务器'
            channel_name = getattr(interaction.channel, "name", "[DM Channel]")
            channel_info = f' (频道: {channel_name})' if scope == 'channel' else ''
            match_desc = {
                'user': f'用户 **{user.mention if user else "[unknown]"}**',
                'user_ids': f'用户 ID `{sorted(target_user_ids)}`',
                'webhook_ids': f'Webhook ID `{sorted(target_webhook_ids)}`',
                'nick_pattern': f'昵称通配符 `{nick_pattern}`',
                'content_pattern': f'内容通配符 `{content_pattern}`'
            }[match_type]

            await interaction.followup.send(
                f':broom: 批量清除消息完成 :broom:' +
                f'\n范围: **{scope_text}**{channel_info}' +
                f'\n匹配方式: **{match_desc}**' +
                f'\n时间范围: {"最近 **" + str(minutes_limit) + "** 分钟" if minutes_limit > 0 else "不限制"}' +
                f'\n每频道检查上限: **{message_limit if message_limit > 0 else "不限制"}** 条, 匹配消息 **{checked_count}** 条' +
                f'\n成功删除: **{success_count}** 条' +
                (f'\n因超过 14 天不可删: **{too_old_count}** 条' if too_old_count > 0 else '') +
                (f'\n其他原因失败: **{failed_count}** 条' if failed_count > 0 else '')
            )

        # ========== Others ==========

        @client.tree.command(
            name='sync',
            description='同步指令列表'
        )
        async def sync(interaction: discord.Interaction):
            await interaction.response.defer()
            await client.tree.sync()
            l.info('Command tree synced.')
            await interaction.followup.send(
                '**:white_check_mark: 斜杠指令列表已同步**'
            )

        # ----- Prefix Command -----

        @client.command()
        async def sync_commands(ctx: commands.Context):
            await ctx.defer()
            await client.tree.sync()
            await ctx.send('**:white_check_mark: 斜杠指令列表已同步**')
