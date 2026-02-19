# c!ding: utf-8
from logging import getLogger
from uuid import uuid4 as uuid
from datetime import datetime
import random

import discord
from discord import app_commands
from discord.ext import commands

from config import ConfigModel

l = getLogger(__name__)


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
                f':lock: 随机生成 UUID: **```{uuid()}```**\n> 此条消息仅你可见, 且将在 <t:{now+delete_after}:R> 删除',
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
            user_id='用户 (机器人) ID',
            message_count='拉取最近消息的数量',
        )
        async def clear_message(
            interaction: discord.Interaction,
            user_id: str,
            message_count: int,
        ):
            await interaction.response.defer()
            # 获取目标用户 id
            try:
                user_id_int: int = int(user_id)
            except:
                await interaction.followup.send(
                    f':x: **用户 ID 不为整数: `{user_id}`** :x:',
                    ephemeral=True
                )
            # 获取消息列表
            message_list = [msg async for msg in interaction.channel.history(limit=message_count)]  # type: ignore
            checked_messages: list[discord.Message] = []
            checked_count = 0
            success_count = 0
            for i in message_list:
                if i.author.id == user_id_int:
                    checked_messages.append(i)
            checked_count = len(checked_messages)
            # 删除消息 (普通删除)
            for i in checked_messages:
                try:
                    await i.delete()
                except:
                    pass
                else:
                    success_count += 1
            await interaction.followup.send(
                f':broom: 清除用户 ID 为 **{user_id_int}** 的消息 :broom:' +
                f'\n抓取最近消息 **{message_count}** 条, 其中此用户发送 **{checked_count}** 条, 成功删除 **{success_count}** 条'
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
