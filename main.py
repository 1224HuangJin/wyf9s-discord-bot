# coding: utf-8

# region import

import io
import logging

import discord
from discord.ext import commands

from config import Config
import utils as u

from modules.emoji import EmojiModule
from modules.tools import ToolsModule
from modules.manage import ManageModule

# endregion import

# region init

# init logger
l = logging.getLogger(__name__)
l_dc = logging.getLogger('discord')

logging.basicConfig(level=logging.DEBUG)
root_logger = logging.getLogger()
l_dc.handlers.clear()
root_logger.handlers.clear()  # clear default handler
# set stream handler
shandler = logging.StreamHandler()
shandler.setFormatter(u.CustomFormatter(colorful=True))
root_logger.addHandler(shandler)
l_dc.addHandler(shandler)

# init config
c = Config().config

# continue init logger
root_logger.level = logging.DEBUG if c.debug else logging.INFO  # set log level
# reset stream handler
root_logger.handlers.clear()
l_dc.handlers.clear()
shandler = logging.StreamHandler()
shandler.setFormatter(u.CustomFormatter(colorful=True))
root_logger.addHandler(shandler)
l_dc.addHandler(shandler)
# set file handler
if c.log_file:
    log_file_path = u.get_path(c.log_file)
    l.info(f'Saving logs to {log_file_path}')
    fhandler = logging.FileHandler(log_file_path, encoding='utf-8', errors='ignore')
    fhandler.setFormatter(u.CustomFormatter(colorful=False))
    root_logger.addHandler(fhandler)
    l_dc.addHandler(fhandler)
# set discord.http handler
l_dchttp = logging.getLogger('discord.http')
l_dchttp.setLevel(logging.INFO)

# endregion init

# region setup

# set permission
intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(
    command_prefix=c.command_prefix,
    intents=intents,
    proxy=c.proxy
)
# endregion setup

# region modules
if c.emoji.enabled:
    emoji_module = EmojiModule(config=c, client=client)

tools_module = ToolsModule(config=c, client=client)
manage_module = ManageModule(config=c, client=client)

# endregion modules

# ------------------- 登录 -------------------

# region login

@client.event
async def on_ready():
    l.info(f'Logged in as {client.user} ({client.user.id if client.user else "unknown"})')
    await client.tree.sync()
    l.info('Slash commands synced.')
    if c.emoji.enabled:
        succ, err = await emoji_module.update_emoji_list()
        if succ:
            l.info('Emoji list synced.')
        else:
            l.warning(f'Emoji list sync failed: {err}')


client.run(c.token)

# endregion end
