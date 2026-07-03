import os
import time

from loguru import logger as l
import discord
from discord import app_commands
from discord.ext import commands

from modules.audit import AuditLogger
from i18n import t as _t, lang_of, ls
import utils as u


# Cooldown for /reload to prevent spam: per-user timestamps
_reload_cooldowns: dict[int, float] = {}
_RELOAD_COOLDOWN = 15  # seconds


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.c = bot.config  # ty:ignore[unresolved-attribute]
        self.audit: AuditLogger | None = getattr(bot, "audit", None)
        self.lang_store = getattr(bot, "lang_store", None)

    def _tr(self, source, key: str, **kwargs) -> str:
        return _t(key, lang_of(source, self.lang_store), **kwargs)

    def _list_cogs(self) -> list[str]:
        cogs_dir = os.path.join(os.path.dirname(__file__))
        cogs = sorted(
            f[:-3]
            for f in os.listdir(cogs_dir)
            if f.endswith(".py") and not f.startswith("_")
        )
        return cogs

    # ========== /sync ==========

    @app_commands.command(name="sync", description=ls("admin.cmd_sync_desc"))
    @u.requires(u.Permission.ADMIN)
    async def slash_sync(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await self.bot.tree.sync()
        l.info("Command tree synced.")
        await interaction.followup.send(self._tr(interaction, "admin.synced"))
        if self.audit:
            await self.audit.log(
                action="sync",
                user=interaction.user,
                guild=interaction.guild,
                channel=interaction.channel,
                detail="Synced slash command tree",
            )

    @commands.command(name="sync")
    @u.requires(u.Permission.ADMIN)
    async def prefix_sync(self, ctx: commands.Context):
        await ctx.defer()
        await self.bot.tree.sync()
        await ctx.send(self._tr(ctx, "admin.synced"))
        if self.audit:
            await self.audit.log(
                action="sync",
                user=ctx.author,
                guild=ctx.guild,
                channel=ctx.channel,  # ty:ignore[invalid-argument-type]
                detail="Synced slash command tree",
            )

    @commands.command(name="sync-commands")
    @u.requires(u.Permission.ADMIN)
    async def prefix_sync_commands(self, ctx: commands.Context):
        await ctx.defer()
        await self.bot.tree.sync()
        await ctx.send(self._tr(ctx, "admin.synced"))
        if self.audit:
            await self.audit.log(
                action="sync-commands",
                user=ctx.author,
                guild=ctx.guild,
                channel=ctx.channel,  # ty:ignore[invalid-argument-type]
                detail="Synced slash command tree",
            )

    # ========== /reload ==========

    @app_commands.command(name="reload", description=ls("admin.cmd_reload_desc"))
    @app_commands.describe(module=ls("admin.param_reload_module"))
    @u.requires(u.Permission.ADMIN)
    async def slash_reload(
        self, interaction: discord.Interaction, module: str | None = None
    ):
        now = time.monotonic()
        uid = interaction.user.id
        if uid in _reload_cooldowns:
            elapsed = now - _reload_cooldowns[uid]
            if elapsed < _RELOAD_COOLDOWN:
                remaining = _RELOAD_COOLDOWN - elapsed
                await interaction.response.send_message(
                    self._tr(
                        interaction,
                        "admin.reload_cooldown",
                        remaining=f"{remaining:.0f}",
                    ),
                    ephemeral=True,
                )
                return
        _reload_cooldowns[uid] = now

        await self._handle_reload(interaction, module)

    @commands.command(name="reload")
    @u.requires(u.Permission.ADMIN)
    async def prefix_reload(self, ctx: commands.Context, *, module: str | None = None):
        now = time.monotonic()
        uid = ctx.author.id
        if uid in _reload_cooldowns:
            elapsed = now - _reload_cooldowns[uid]
            if elapsed < _RELOAD_COOLDOWN:
                remaining = _RELOAD_COOLDOWN - elapsed
                await ctx.send(
                    self._tr(
                        ctx, "admin.reload_cooldown_short", remaining=f"{remaining:.0f}"
                    ),
                    delete_after=10,
                )
                return
        _reload_cooldowns[uid] = now

        await self._handle_reload(ctx, module)

    async def _handle_reload(self, source, module: str | None):
        is_interaction = isinstance(source, discord.Interaction)

        if is_interaction:
            await source.response.defer()

        available = self._list_cogs()

        if module is None:
            lines = [self._tr(source, "admin.available_cogs", count=len(available))]
            for name in available:
                is_loaded = f"cogs.{name}" in self.bot.extensions
                marker = ":green_circle:" if is_loaded else ":black_circle:"
                lines.append(f"  {marker} `{name}`")
            msg = "\n".join(lines)
            if is_interaction:
                await source.followup.send(msg)
            else:
                await source.send(msg)
            return

        module = module.lower().strip()
        ext_name = f"cogs.{module}"

        if ext_name not in self.bot.extensions and module not in available:
            msg = self._tr(source, "admin.cog_not_found", module=module)
            if is_interaction:
                await source.followup.send(msg, ephemeral=True)
            else:
                await source.send(msg, delete_after=10)
            return

        try:
            if ext_name in self.bot.extensions:
                await self.bot.reload_extension(ext_name)
            else:
                await self.bot.load_extension(ext_name)

            # Also reload perm store if perm cog was reloaded
            if module == "perm":
                perm_store = getattr(self.bot, "perm_store", None)
                if perm_store:
                    perm_store._load()

            msg = self._tr(source, "admin.reloaded", module=module)
            l.info(f"Reloaded cog: {module}")
            if is_interaction:
                await source.followup.send(msg)
            else:
                await source.send(msg)

            if self.audit:
                user = source.user if is_interaction else source.author
                await self.audit.log(
                    action="reload",
                    user=user,
                    guild=source.guild,
                    channel=source.channel,
                    detail=f"Reloaded cog: {module}",
                )
        except Exception as e:
            msg = self._tr(source, "admin.reload_failed", module=module, error=e)
            l.error(f"Failed to reload cog {module}: {e}")
            if is_interaction:
                await source.followup.send(msg, ephemeral=True)
            else:
                await source.send(msg, delete_after=10)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
    l.info("AdminCog loaded.")
