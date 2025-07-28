# coding: utf-8

# region import

import io
import random
from uuid import uuid4 as uuid
from datetime import datetime
import logging

import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

from config import Config
import utils as u

# endregion import

# region init

# init logger
l = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)
root_logger = logging.getLogger()
root_logger.handlers.clear()  # clear default handler
# set stream handler
shandler = logging.StreamHandler()
shandler.setFormatter(u.CustomFormatter(colorful=True))
root_logger.addHandler(shandler)

# init config
c = Config().config

# continue init logger
root_logger.level = logging.DEBUG if c.debug else logging.INFO  # set log level
# reset stream handler
root_logger.handlers.clear()
shandler = logging.StreamHandler()
shandler.setFormatter(u.CustomFormatter(colorful=True))
root_logger.addHandler(shandler)
# set file handler
if c.log_file:
    log_file_path = u.get_path(c.log_file)
    l.info(f'Saving logs to {log_file_path}')
    fhandler = logging.FileHandler(log_file_path, encoding='utf-8', errors='ignore')
    fhandler.setFormatter(u.CustomFormatter(colorful=False))
    root_logger.addHandler(fhandler)

# endregion init

# region setup

# set permission
intents = discord.Intents.default()
intents.message_content = True

if c.proxy:
    client = commands.Bot(
        command_prefix=c.command_prefix,
        intents=intents,
        proxy=c.proxy
    )
else:
    client = commands.Bot(
        command_prefix=c.command_prefix,
        intents=intents
    )
# endregion setup

# ------------- ### 斜杠命令 ### -------------

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
async def slash_random_uuid(interaction: discord.Interaction):
    now = int(datetime.now().timestamp())
    await interaction.response.send_message(
        f':lock: 随机生成 UUID: **`{uuid()}`**\n> 此条消息仅你可见, 且将在 <t:{now+c.secret_message_delay}:R> 删除',
        ephemeral=True,
        delete_after=c.secret_message_delay
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
    # 1. 删除回复的消息
    # if interaction.message and interaction.message.reference:
    #     msgid = interaction.message.reference.message_id
    #     try:
    #         await message = interaction.channel.get_partial_message(message_id).delete()
    #     except discord.Forbidden:
    #         await interaction.response.send_message(
    #             f':x: **权限不足, 无法删除此消息** :x:',
    #             ephemeral=not show_to_public
    #         )
    #     except discord.NotFound:
    #         await interaction.response.send_message(
    #             f':x: **找不到 ID 为 `{msgid}` 的消息** :x:',
    #             ephemeral=not show_to_public
    #         )
    #     except Exception as e:
    #         await interaction.response.send_message(
    #             f':x: **删除消息 `{msgid}` 时出错: `{e}`** :x:',
    #             ephemeral=not show_to_public
    #         )
    # 2. 删除指定 id 的消息
    # elif message_id:
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
    # use_bulk_delete='是否使用批量删除 (无法删除 14 天前的消息)'
)
async def clear_message(
    interaction: discord.Interaction,
    user_id: str,
    message_count: int,
    # use_bulk_delete: bool
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
            # checked_messages.append(i.id if use_bulk_delete else i)
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

# ========== Emoji ==========

# ----- Update -----

# rollback
Emoji: dict = {
    "utc_build_timestamp": 0,
    "is_cf_pages": False,
    "commit_id": None,
    "commit_branch": None,
    "emojis": []
}


async def update_emoji_list() -> bool:
    global Emoji
    l.info('[emoji] Updating emoji list...')
    resp = await u.get_json(f'{c.emoji.base_url}/emoji.json?disable-cache')
    if resp:
        Emoji = resp
        await client.tree.sync()
        l.info(f'[emoji] Emoji list Synced √ (count: {len(Emoji["emojis"])})')
        l.debug(f'[emoji] {Emoji["emojis"]}')
        return True
    else:
        l.warning('[emoji] Emoji list sync failed!')
        return False


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
            f'**:x: Update Emoji Failed: {result}**',
            ephemeral=True
        )
    else:
        # Success
        await interaction.followup.send(
            f'''**:white_check_mark: Update Emoji Success!**
> **Build Time**: <t:{Emoji["utc_build_timestamp"]}:f>
> **Commit**: [`{Emoji["commit_id"]}`](https://github.com/siiway/ghimg/commit/{Emoji["commit_id"]})
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
> **Build on CF Pages**: {"Yes" if Emoji["is_cf_pages"] else "No"}
> **Commit ID**: [`{Emoji["commit_id"]}`](https://github.com/siiway/ghimg/commit/{Emoji["commit_id"]})
> **Commit Branch**: `{Emoji["commit_branch"]}`
> **Emoji Count**: {len(Emoji["emojis"])}
> **Emoji Source**: [`emoji.json`]({c.emoji.base_url}/emoji.json?disable-cache)'''
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
    ][:c.emoji.max_results]  # 最多显示 ?? 个选项
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
            ":x: **无效的表情包名称，请从列表中选择**",
            ephemeral=True,
            delete_after=10
        )

    imgurl = f'{c.emoji.base_url}/{name}'
    try:
        async with aiohttp.ClientSession() as session:  # creates session
            async with session.get(imgurl) as resp:  # gets image from url
                img = await resp.read()  # reads image from response
                with io.BytesIO(img) as file:  # converts to file-like object
                    await interaction.response.send_message(
                        '',
                        file=discord.File(
                            fp=file,
                            filename=name,
                            description=f'Emoji (sticker): {name}'
                        )
                    )
    except Exception as error:
        await interaction.response.send_message(
            f'> Fetch emoji [{name}]({imgurl}) **ERROR**: `{error}`',
            ephemeral=True,
            delete_after=10
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


@client.command(name='sync')
async def sync_ctx(ctx: commands.Context):
    await ctx.defer()
    await client.tree.sync()
    await ctx.send('**:white_check_mark: 斜杠指令列表已同步**')

# ----------------- 消息处理 -----------------


@client.event
async def on_message(message: discord.Message):
    # 处理桥接加入消息
    if message.author.name == '[DC] @system':
        await message.delete(
            delay=2
        )
    # 处理 To-Do List Bot 在 #sleepy-todo 的新消息
    elif (message.channel.id in c.rmtodo.todo_channels) and (message.author.id == c.rmtodo.author_id) and (not message.embeds):
        await message.delete(
            delay=c.rmtodo.remove_delay
        )

    # 必须添加这行才能让前缀命令正常工作
    # await client.process_commands(message)

    # 保留原有的随机数触发逻辑（可选）
    # if message.author == client.user:
    #     return
    # if 'random' in message.content and not message.content.startswith('!'):
    #     await message.channel.send(f'旧版触发：**{random.randint(1, 114514)}**')


# ------------------- 登录 -------------------


@client.event
async def on_ready():
    l.info(f'Logged in as {client.user} ({client.user.id if client.user else "unknown"})')
    await client.tree.sync()
    l.info('Slash commands synced.')
    if c.emoji.enabled:
        await update_emoji_list()
        l.info('Emoji list synced.')


client.run(c.token)
