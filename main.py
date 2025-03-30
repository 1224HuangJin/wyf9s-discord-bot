# coding: utf-8

# Basic
import discord
from discord import app_commands
from discord.ext import commands
from enum import Enum
# Networking
import aiohttp
import requests
# Processing
import io
# Function
import random
from uuid import uuid4 as uuid
# ...
import config as c  # type: ignore
import utils as u

# 设置机器人需要的权限
intents = discord.Intents.default()
intents.message_content = True

# 创建带命令前缀的机器人实例（这里用 \ 作为前缀）
client = commands.Bot(
    command_prefix=c.COMMAND_PREFIX,
    intents=intents
)

# ------------- ### 斜杠命令 ### -------------

# ----- Random - 随机数 -----


@client.tree.command(
    name='random',
    description='生成自定义范围的随机数'
)
@app_commands.describe(
    min_num='最小值 (默认: 1)',
    max_num='最大值 (默认: 114514)'
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
            f':game_die: `{min_num}` - `{max_num}` 的随机数：**`{result}`**'
        )
    except ValueError:
        await interaction.response.send_message(
            ':x: 请输入有效的整数范围！',
            ephemeral=True
        )

# ----- UUID -----


@client.tree.command(
    name='uuid',
    description='生成一个 UUID'
)
async def slash_random(interaction: discord.Interaction):

    await interaction.response.send_message(
        f':lock: 随机生成 UUID: **`{uuid()}`**\n> 此条消息仅你可见, 且将在 <t:{u.utc_timestamp()+c.SECRET_MESSAGE_DELETE_SECOND}:R> 删除',
        ephemeral=True,
        delete_after=c.SECRET_MESSAGE_DELETE_SECOND
    )

# ========== Emoji ==========

# ----- Update -----

# rollback
Emoji: dict = {
    "utc_build_timestamp": 0,
    "utc_build_time": "1970-01-01 00:00:00.000000+00:00",
    "is_cf_pages": False,
    "commit_id": None,
    "commit_branch": None,
    "emojis": [
        "three_color_image.webp",
        "emm.webp"
    ]
}


async def update_emoji_list():
    global Emoji
    try:
        print('Updating emoji list...')
        resp = requests.get(f'{c.GHIMG_BASE}/emoji.json?disable-cache')
        Emoji = resp.json()
        if len(Emoji['emojis']) < 2:
            Emoji['emojis'] = [
                "three_color_image.webp",
                "emm.webp"
            ]
        await client.tree.sync()
        print('Emoji list Synced √')
    except Exception as e:
        return e
    else:
        return None


@client.tree.command(
    name='emoji_update',
    description='更新表情包库数据'
)

async def emoji_update(interaction: discord.Interaction):
    await interaction.response.defer()
    result = await update_emoji_list()
    if result:
        # Error
        await interaction.followup.send(
            f'**:x: Update Emoji Failed: {result}**'
        )
    else:
        # Success
        await interaction.followup.send(
            f'''**:white_check_mark: Update Emoji Success!**
> **Build Time**: <t:{Emoji["utc_build_timestamp"]}:f>
> **Commit**: `{Emoji["commit_id"]}`
> **Emojis**: `{len(Emoji["emojis"])}`'''
        )


@client.tree.command(
    name='emoji_info',
    description='查看表情包库相关信息'
)
async def emoji_info(interaction: discord.Interaction):
    await interaction.response.send_message(
        f'''**:information_source: Emojis Info**
> **Build Time**: <t:{Emoji["utc_build_timestamp"]}:f>
> **Build Time String**: `{Emoji["utc_build_time"]}`
> **Build on CF Pages**: {"Yes" if Emoji["is_cf_pages"] else "No"}
> **Commit ID**: `{Emoji["commit_id"]}`
> **Commit Branch**: `{Emoji["commit_branch"]}`
> **Emoji Count**: {len(Emoji["emojis"])}
> **Emoji Source**: `{c.GHIMG_BASE}/`'''
    )

# ----- Send ------


async def emoji_autocomplete(
    interaction: discord.Interaction,
    current: str  # 用户当前输入的内容
) -> list[app_commands.Choice[str]]:
    '''
    表情包获取自动生成下拉菜单
    '''
    # 根据输入内容过滤选项
    filtered = [
        app_commands.Choice(name=name, value=name)
        for name in Emoji['emojis']
        if current.lower() in name.lower()  # 不区分大小写搜索
    ][:20]  # 最多显示 30 个选项
    return filtered


@client.tree.command(
    name='emoji',
    description='使用库中的表情包'
)
@app_commands.describe(name="输入名称搜索表情包")
@app_commands.autocomplete(name=emoji_autocomplete)
async def emoji(
    interaction: discord.Interaction,
    name: str
):
    if name not in Emoji['emojis']:
        return await interaction.response.send_message(
            ":x: 无效的表情包名称，请使用 Tab 键从列表中选择",
            ephemeral=True
        )

    imgurl = f'{c.GHIMG_BASE}/{name}'
    try:
        async with aiohttp.ClientSession() as session:  # creates session
            async with session.get(imgurl) as resp:  # gets image from url
                img = await resp.read()  # reads image from response
                with io.BytesIO(img) as file:  # converts to file-like object
                    await interaction.response.send_message(
                        f'> *Emoji: [{name}]({imgurl})*',
                        file=discord.File(file, name)
                    )
    except Exception as error:
        await interaction.response.send_message(
            f'> *Emoji: [{name}]({imgurl})*\n> **ERROR: `{error}`**'
        )

# ========== Others ==========


@client.tree.command(
    name='sync',
    description='同步指令列表'
)
async def sync(interaction: discord.Interaction):
    await interaction.response.defer()
    await client.tree.sync()
    print('Command tree synced.')
    await interaction.followup.send(
        '**:white_check_mark: 斜杠指令列表已同步**'
    )
# ----------------- 前缀命令 -----------------


@client.command()
async def sync(ctx: commands.Context):
    await ctx.defer()
    await client.tree.sync()
    await ctx.send('**:white_check_mark: 斜杠指令列表已同步**')

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


# ------------------- 登录 -------------------


@client.event
async def on_ready():
    print(f'已登录为 {client.user}')
    # 同步斜杠命令到服务器（开发时建议在需要时手动调用）
    await update_emoji_list()
    await client.tree.sync()
    print('斜杠命令已同步')


client.run(c.TOKEN)
