# c!ding: utf-8
from uuid import uuid4 as uuid
from datetime import datetime
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

        # ----- Clear Message - 清除 (某人) 的消息 -----

        @client.tree.command(
            name='clear-message',
            description='清除 (某人) 的消息'
        )
        @app_commands.describe(
            user='要清除消息的用户',
            message_count='拉取最近消息的数量 (每个频道)',
            scope='清除消息的范围: "channel" (单个频道, 默认) 或 "server" (整个服务器)',
            channel='指定频道 (仅在 scope=channel 时生效, 未设置则使用指令所在频道)',
        )
        async def clear_message(
            interaction: discord.Interaction,
            user: discord.User,
            message_count: int,
            scope: str = 'channel',
            channel: discord.TextChannel | None = None
        ):
            await interaction.response.defer()

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

            # 收集要删除的消息
            checked_messages: list[discord.Message] = []

            for channel in target_channels:
                try:
                    message_list = [msg async for msg in channel.history(limit=message_count)]
                    for msg in message_list:
                        if msg.author.id == user.id:
                            checked_messages.append(msg)
                except discord.Forbidden:
                    # l.warning(f'无权限访问频道 {channel.name} ({channel.id})')
                    pass
                except Exception as e:
                    l.warning(f'获取频道 {channel.name} ({channel.id}) 消息时出错: {e}')

            checked_count = len(checked_messages)

            if checked_count == 0:
                await interaction.followup.send(
                    f':broom: 未找到用户 **{user.mention}** 的消息'
                )
                return

            # 使用 bulk_delete API 删除消息 (Discord API 限制最多一次删除 100 条)
            success_count = 0
            failed_count = 0

            # 按批次删除 (一次最多 100 条)
            for i in range(0, len(checked_messages), 100):
                batch = checked_messages[i:i+100]
                try:
                    await interaction.channel.delete_messages(batch)  # type: ignore
                    success_count += len(batch)
                except discord.Forbidden:
                    await interaction.followup.send(
                        f':x: **权限不足, 无法删除消息** :x:',
                        ephemeral=True
                    )
                    return
                except Exception as e:
                    l.error(f'批量删除消息时出错: {e}')
                    failed_count += len(batch)

            # 生成统计信息
            scope_text = '频道' if scope == 'channel' else '服务器'
            channel_info = f' (频道: {getattr(interaction.channel, 'name', '[DM Channel]')})' if scope == 'channel' else ''

            await interaction.followup.send(
                f':broom: 清除用户 **{user.mention}** 的消息 :broom:' +
                f'\n范围: **{scope_text}**{channel_info}' +
                f'\n查询消息数: **{message_count} x {len(target_channels)}** 条, 匹配用户消息 **{checked_count}** 条' +
                f'\n成功删除: **{success_count}** 条' +
                (f', 失败: **{failed_count}** 条' if failed_count > 0 else '')
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
