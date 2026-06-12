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
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>\n"
    )


# Create a temporary stderr handler for config loading
l.add(
    stderr,
    level="DEBUG",
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
logging.root.setLevel("DEBUG")

# Now import modules that use logging
import discord  # noqa: E402
from discord.ext import commands  # noqa: E402

from config import Config  # noqa: E402
import utils as u  # noqa: E402

from modules.audit import AuditLogger  # noqa: E402
from modules.emoji import EmojiModule  # noqa: E402
from modules.tools import ToolsModule  # noqa: E402
from modules.lock import LockModule  # noqa: E402
from modules.antispam import AntiSpamModule  # noqa: E402
from modules.manage import ManageModule  # noqa: E402
from modules.voice import VoiceChannelModule  # noqa: E402

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
    l.info(f"Saving logs to {log_file_path}")


# clear and configure discord.py loggers
logging.getLogger().handlers.clear()
logging.getLogger("discord").handlers.clear()
logging.getLogger("discord.http").handlers.clear()
logging.getLogger("discord.gateway").handlers.clear()
logging.getLogger("discord.client").handlers.clear()

# update root logger level based on config
logging.root.handlers = [InterceptHandler()]
logging.root.setLevel(c.log.level)

# set discord loggers to use InterceptHandler
discord_logger = logging.getLogger("discord")
discord_logger.handlers = [InterceptHandler()]
discord_logger.setLevel(c.log.level)

# reduce discord.http verbosity
logging.getLogger("discord.http").setLevel(logging.WARNING)

# endregion init

# region setup

# set permission
intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix=c.command_prefix, intents=intents, proxy=c.proxy)

# endregion setup

# region modules

# audit logger (shared by all modules)
has_slash_commands = False

if c.audit.enabled:
    audit = AuditLogger(config=c, client=client)
else:
    audit = None

tools_module: ToolsModule | None = None

if c.emoji.enabled:
    emoji_module = EmojiModule(config=c, client=client, audit=audit)
    if c.emoji.slash:
        has_slash_commands = True
    l.info("Emoji module enabled.")

if c.tools.enabled:
    tools_module = ToolsModule(config=c, client=client, audit=audit)
    if c.tools.slash:
        has_slash_commands = True
    l.info("Tools module enabled.")

if c.lock.enabled:
    lock_module = LockModule(config=c, client=client, audit=audit)
    if c.lock.slash:
        has_slash_commands = True
    l.info("Lock module enabled.")

if c.rmmsg.enabled or c.rmtodo.enabled:
    manage_module = ManageModule(config=c, client=client)
    if c.rmmsg.enabled:
        l.info("Auto-remove message enabled.")
    if c.rmtodo.enabled:
        l.info("Auto-remove todo enabled.")

if c.voicechannel.enabled:
    voice_channel_module = VoiceChannelModule(config=c, client=client, audit=audit)
    if c.voicechannel.slash:
        has_slash_commands = True
    l.info("Voice channel module enabled.")

if c.antispam.enabled:
    antispam_module = AntiSpamModule(
        config=c,
        client=client,
        audit=audit,
    )
    l.info("Antispam module enabled.")

# endregion modules

# ------------------- 登录 -------------------

# region login


@client.event
async def on_ready():
    l.info(
        f"Logged in as {client.user} ({client.user.id if client.user else 'unknown'})"
    )

    if has_slash_commands:
        await client.tree.sync()
        l.info("Slash commands synced.")
    else:
        l.info("No slash commands registered, skipping sync.")

    if c.emoji.enabled:
        succ, err = await emoji_module.update_emoji_list()
        if succ:
            l.info("Emoji list synced.")
        else:
            l.warning(f"Emoji list sync failed: {err}")

    if c.lock.enabled:
        await lock_module.start_scheduler()
        l.info("Lock scheduler started.")


client.run(c.token)

# endregion login
