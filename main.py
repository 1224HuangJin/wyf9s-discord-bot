import discord
from discord import app_commands
from discord.ext import commands
import random
import requests

import config as cfg  # type: ignore

# 设置机器人需要的权限
intents = discord.Intents.default()
intents.message_content = True

# 创建带命令前缀的机器人实例（这里用!作为前缀）
client = commands.Bot(
    # command_prefix='!',
    intents=intents
)

# ----------------- 基础事件 -----------------


@client.event
async def on_ready():
    print(f'已登录为 {client.user}')
    # 同步斜杠命令到服务器（开发时建议在需要时手动调用）
    await client.tree.sync()
    print("斜杠命令已同步")

# ----------------- 前缀命令 -----------------


# @client.command()
# async def randomnum(ctx: commands.Context):
#     """发送1到114514的随机数（使用!randomnum触发）"""
#     await ctx.send(f'1到114514的随机数：**{random.randint(1, 114514)}**')

# ------------- ### 斜杠命令 ### -------------

@client.tree.command(name="random", description="生成自定义范围的随机数")
@app_commands.describe(
    min_num="最小值（默认1）",
    max_num="最大值（默认114514）"
)
async def slash_random(
    interaction: discord.Interaction,
    min_num: int = 1,
    max_num: int = 114514
):
    try:
        if min_num > max_num:
            min_num, max_num = max_num, min_num  # 自动交换大小值

        result = random.randint(min_num, max_num)
        await interaction.response.send_message(
            f"🎲 {min_num}-{max_num} 的随机数：**{result}**"
        )
    except ValueError:
        await interaction.response.send_message(
            "请输入有效的整数范围！",
            ephemeral=True
        )

# ----------------- 原有消息处理（可选保留） -----------------


# @client.event
# async def on_message(message: discord.Message):
#     # 必须添加这行才能让前缀命令正常工作
#     await client.process_commands(message)

#     # 保留原有的随机数触发逻辑（可选）
#     if message.author == client.user:
#         return
#     if 'random' in message.content and not message.content.startswith('!'):
#         await message.channel.send(f'旧版触发：**{random.randint(1, 114514)}**')

client.run(cfg.TOKEN)
