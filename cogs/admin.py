import os
import time

from loguru import logger as l
import discord
from discord import app_commands
from discord.ext import commands

from modules.audit import AuditLogger
import utils as u


# Cooldown for /reload to prevent spam: per-user timestamps
_reload_cooldowns: dict[int, float] = {}
_RELOAD_COOLDOWN = 15  # seconds


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.c = bot.config  # ty:ignore[unresolved-attribute]
        self.audit: AuditLogger | None = getattr(bot, "audit", None)

    def _list_cogs(self) -> list[str]:
        cogs_dir = os.path.join(os.path.dirname(__file__))
        cogs = sorted(
            f[:-3]
            for f in os.listdir(cogs_dir)
            if f.endswith(".py") and not f.startswith("_")
        )
        return cogs

    # ========== /sync ==========

    @app_commands.command(name="sync", description="Sync slash command tree")
    async def slash_sync(self, interaction: discord.Interaction):
        if not u.is_config_admin(interaction.user, self.c):
            await interaction.response.send_message(
                ":x: **No permission** :x:", ephemeral=True
            )
            return
        await interaction.response.defer()
        await self.bot.tree.sync()
        l.info("Command tree synced.")
        await interaction.followup.send("**:white_check_mark: Slash commands synced**")
        if self.audit:
            await self.audit.log(
                action="sync",
                user=interaction.user,
                guild=interaction.guild,
                channel=interaction.channel,
                detail="Synced slash command tree",
            )

    @commands.command(name="sync")
    async def prefix_sync(self, ctx: commands.Context):
        if not u.is_config_admin(ctx.author, self.c):
            await ctx.send("**:x: No permission**", delete_after=10)
            return
        await ctx.defer()
        await self.bot.tree.sync()
        await ctx.send("**:white_check_mark: Slash commands synced**")
        if self.audit:
            await self.audit.log(
                action="sync",
                user=ctx.author,
                guild=ctx.guild,
                channel=ctx.channel,  # ty:ignore[invalid-argument-type]
                detail="Synced slash command tree",
            )

    @commands.command(name="sync-commands")
    async def prefix_sync_commands(self, ctx: commands.Context):
        if not u.is_config_admin(ctx.author, self.c):
            await ctx.send("**:x: No permission**", delete_after=10)
            return
        await ctx.defer()
        await self.bot.tree.sync()
        await ctx.send("**:white_check_mark: Slash commands synced**")
        if self.audit:
            await self.audit.log(
                action="sync-commands",
                user=ctx.author,
                guild=ctx.guild,
                channel=ctx.channel,  # ty:ignore[invalid-argument-type]
                detail="Synced slash command tree",
            )

    # ========== /reload ==========

    @app_commands.command(name="reload", description="Reload a cog module (admin only)")
    @app_commands.describe(module="Cog name to reload (empty to list)")
    async def slash_reload(
        self, interaction: discord.Interaction, module: str | None = None
    ):
        if not u.is_admin(interaction.user, self.c):
            await interaction.response.send_message(
                ":x: **No permission** :x:", ephemeral=True
            )
            return

        now = time.monotonic()
        uid = interaction.user.id
        if uid in _reload_cooldowns:
            elapsed = now - _reload_cooldowns[uid]
            if elapsed < _RELOAD_COOLDOWN:
                remaining = _RELOAD_COOLDOWN - elapsed
                await interaction.response.send_message(
                    f":hourglass: **Cooldown: wait `{remaining:.0f}s` before reloading again**",
                    ephemeral=True,
                )
                return
        _reload_cooldowns[uid] = now

        await self._handle_reload(interaction, module)

    @commands.command(name="reload")
    async def prefix_reload(self, ctx: commands.Context, *, module: str | None = None):
        if not u.is_admin(ctx.author, self.c):
            await ctx.send("**:x: No permission**", delete_after=10)
            return

        now = time.monotonic()
        uid = ctx.author.id
        if uid in _reload_cooldowns:
            elapsed = now - _reload_cooldowns[uid]
            if elapsed < _RELOAD_COOLDOWN:
                remaining = _RELOAD_COOLDOWN - elapsed
                await ctx.send(
                    f":hourglass: **Cooldown: wait `{remaining:.0f}s`**",
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
            lines = [f"**Available cogs** (`{len(available)}`):"]
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
            msg = f":x: **Cog `{module}` not found**"
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

            msg = f":white_check_mark: **Reloaded `{module}`**"
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
            msg = f":x: **Failed to reload `{module}`**: `{e}`"
            l.error(f"Failed to reload cog {module}: {e}")
            if is_interaction:
                await source.followup.send(msg, ephemeral=True)
            else:
                await source.send(msg, delete_after=10)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
    l.info("AdminCog loaded.")
