# region import

import logging
from sys import stderr

# Initialize loguru BEFORE importing any modules that use logging
from loguru import logger as l

# Initialize loguru handler immediately
l.remove()  # remove default handler


def log_format(record):
    """Custom log format for Discord bot"""
    return (
        '<green>{time:YYYY-MM-DD HH:mm:ss}</green> | '
        '<level>{level}</level> | '
        '<cyan>{name}</cyan>:<cyan>{line}</cyan> | '
        '<level>{message}</level>\n'
    )


# Create a temporary stderr handler for config loading
l.add(
    stderr,
    level='DEBUG',
    format=log_format,
    backtrace=True,
    diagnose=True,
)

# Intercept standard logging to loguru - MUST be done before importing config
class InterceptHandler(logging.Handler):
    """Intercept standard logging and forward to loguru"""

    def emit(self, record):
        # get loguru logger at correct depth
        logger_opt = l.opt(depth=6, exception=record.exc_info)
        logger_opt.log(record.levelname, record.getMessage())


# Set InterceptHandler for all loggers immediately
logging.root.handlers = [InterceptHandler()]
logging.root.setLevel('DEBUG')

# Now import modules that use logging
import discord
from discord.ext import commands

from config import Config
import utils as u

from modules.emoji import EmojiModule
from modules.tools import ToolsModule
from modules.manage import ManageModule

# endregion import

# region init

# init config
c = Config().config

# reconfigure loggers now that we have config
# remove the temporary stderr handler and add proper ones
l.remove()

# add stderr handler with configured level
l.add(
    stderr,
    level=c.log.level,
    format=log_format,
    backtrace=True,
    diagnose=True,
)

# add file handler if configured
if c.log.file:
    log_file_path = u.get_path(c.log.file)
    l.add(
        log_file_path,
        level=c.log.file_level or c.log.level,
        format=log_format,
        colorize=False,
        rotation=c.log.rotation,
        retention=c.log.retention,
        enqueue=True,
    )
    l.info(f'Saving logs to {log_file_path}')


# clear and configure discord.py loggers
logging.getLogger().handlers.clear()
logging.getLogger('discord').handlers.clear()
logging.getLogger('discord.http').handlers.clear()
logging.getLogger('discord.gateway').handlers.clear()
logging.getLogger('discord.client').handlers.clear()

# update root logger level based on config
logging.root.handlers = [InterceptHandler()]
logging.root.setLevel(c.log.level)

# set discord loggers to use InterceptHandler
discord_logger = logging.getLogger('discord')
discord_logger.handlers = [InterceptHandler()]
discord_logger.setLevel(c.log.level)

# reduce discord.http verbosity
logging.getLogger('discord.http').setLevel(logging.WARNING)

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

# endregion login
