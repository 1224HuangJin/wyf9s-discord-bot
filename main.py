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
from perm import PermStore  # noqa: E402

# endregion import

# region init

# init config
c = Config().config

# reconfigure loggers now that we have config
l.remove()

l.add(
    stderr,
    level=c.log.level,
    format=log_format,
    backtrace=True,
    diagnose=True,
)

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


logging.getLogger().handlers.clear()
logging.getLogger("discord").handlers.clear()
logging.getLogger("discord.http").handlers.clear()
logging.getLogger("discord.gateway").handlers.clear()
logging.getLogger("discord.client").handlers.clear()

logging.root.handlers = [InterceptHandler()]
logging.root.setLevel(c.log.level)

discord_logger = logging.getLogger("discord")
discord_logger.handlers = [InterceptHandler()]
discord_logger.setLevel(c.log.level)

logging.getLogger("discord.http").setLevel(logging.WARNING)

# endregion init

# region setup

intents = discord.Intents.default()
intents.message_content = True

client = commands.Bot(command_prefix=c.command_prefix, intents=intents, proxy=c.proxy)

# Store config and shared state on bot instance
client.config = c  # ty:ignore[unresolved-attribute]

if c.audit.enabled:
    client.audit = AuditLogger(config=c, client=client)  # ty:ignore[unresolved-attribute]
else:
    client.audit = None  # ty:ignore[unresolved-attribute]

# Shared state that persists across cog reloads
client.rate_limiter = u.RateLimiter()  # ty:ignore[unresolved-attribute]
client.perm_store = PermStore()  # ty:ignore[unresolved-attribute]

# endregion setup

# region modules

COG_LIST = [
    "cogs.emoji",
    "cogs.tools",
    "cogs.lock",
    "cogs.voice",
    "cogs.antispam",
    "cogs.manage",
    "cogs.admin",
    "cogs.perm",
    "cogs.announce",
]


async def load_cogs():
    for ext in COG_LIST:
        try:
            await client.load_extension(ext)
            l.info(f"Loaded extension: {ext}")
        except commands.ExtensionError as e:
            l.error(f"Failed to load extension {ext}: {e}")
        except Exception as e:
            l.error(f"Unexpected error loading {ext}: {e}")


# endregion modules

# region login


@client.event
async def on_ready():
    l.info(
        f"Logged in as {client.user} ({client.user.id if client.user else 'unknown'})"
    )

    await client.tree.sync()
    l.info("Slash commands synced.")

    # Initialize emoji data on startup
    if c.emoji.enabled:
        from cogs.emoji import EmojiModel  # noqa: F811

        if not getattr(client, "emoji_data", None):
            client.emoji_data = EmojiModel()  # ty:ignore[unresolved-attribute]
        emoji_cog = client.get_cog("EmojiCog")
        if emoji_cog:
            succ, err = await emoji_cog.update_emoji_list()  # ty:ignore[unresolved-attribute]
            if succ:
                l.info("Emoji list synced.")
            else:
                l.warning(f"Emoji list sync failed: {err}")


async def main():
    async with client:
        await load_cogs()
        await client.start(c.token)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())

# endregion login
