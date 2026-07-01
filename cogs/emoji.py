import io

from loguru import logger as l
from pydantic import BaseModel, ValidationError
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

from modules.audit import AuditLogger
import utils as u


class EmojiModel(BaseModel):
    utc_build_timestamp: int = 0
    is_cf_pages: bool = False
    commit_id: str | None = None
    commit_branch: str | None = None
    emojis: list[str] = []


class EmojiCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.c = bot.config  # ty:ignore[unresolved-attribute]
        self.audit: AuditLogger | None = getattr(bot, "audit", None)

    def cog_load(self):
        if not getattr(self.bot, "emoji_data", None):
            self.bot.emoji_data = EmojiModel()  # ty:ignore[unresolved-attribute]

    @property
    def emoji_data(self) -> EmojiModel:
        return self.bot.emoji_data  # ty:ignore[unresolved-attribute]

    # ========== Slash Group: /emoji ==========

    emoji_group = app_commands.Group(
        name="emoji", description="Emoji management commands"
    )

    @emoji_group.command(name="update", description="Update emoji list from source")
    @u.requires(u.Permission.ADMIN, perm_module="emoji")
    async def emoji_update(self, interaction: discord.Interaction):
        await interaction.response.defer()
        succ, err = await self.update_emoji_list()
        if succ:
            msg = (
                f"**:white_check_mark: Update Emoji Success!**\n"
                f"> **Build Time**: <t:{self.emoji_data.utc_build_timestamp}:f>\n"
                f"> **Commit**: [`{self.emoji_data.commit_id}`]"
                f"(https://github.com/siiway/ghimg/commit/{self.emoji_data.commit_id})\n"
                f"> **Emojis**: `{len(self.emoji_data.emojis)}`"
            )
            await interaction.followup.send(msg)
            if self.audit:
                await self.audit.log(
                    action="emoji-update",
                    user=interaction.user,
                    guild=interaction.guild,
                    channel=interaction.channel,
                    detail=f"Updated emoji list ({len(self.emoji_data.emojis)} total)",
                )
        else:
            await interaction.followup.send(
                f"**:x: Update Emoji Failed: {err}**", ephemeral=True
            )

    @emoji_group.command(name="info", description="Show emoji source info")
    async def emoji_info(self, interaction: discord.Interaction):
        if not await self._check_rate_limit(interaction, "emoji-info"):
            return
        ed = self.emoji_data
        msg = (
            f"**:information_source: Emojis Info**\n"
            f"> **Build Time**: <t:{ed.utc_build_timestamp}:f>\n"
            f"> **Build on CF Pages**: {'Yes' if ed.is_cf_pages else 'No'}\n"
            f"> **Commit ID**: [`{ed.commit_id}`]"
            f"(https://github.com/siiway/ghimg/commit/{ed.commit_id})\n"
            f"> **Commit Branch**: `{ed.commit_branch}`\n"
            f"> **Emoji Count**: {len(ed.emojis)}\n"
            f"> **Emoji Source**: [`emoji.json`]"
            f"({self.c.emoji.base_url}/emoji.json?disable-cache)"
        )
        await interaction.response.send_message(msg)

    # ========== Slash: /e (send emoji) ==========

    async def e_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        filtered = [
            app_commands.Choice(name=name, value=name)
            for name in self.emoji_data.emojis
            if current.lower() in name.lower()
        ][: self.c.emoji.max_results]
        return filtered

    @app_commands.command(name="e", description="Send an emoji from the library")
    @app_commands.describe(name="Search and select an emoji")
    @app_commands.autocomplete(name=e_autocomplete)
    async def e(self, interaction: discord.Interaction, name: str):
        if not await self._check_rate_limit(interaction, "e"):
            return
        if name not in self.emoji_data.emojis:
            await interaction.response.send_message(
                ":x: **Invalid emoji name, please select from list**",
                ephemeral=True,
                delete_after=10,
            )
            return

        imgurl = f"{self.c.emoji.base_url}/{name}"
        await interaction.response.defer()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(imgurl, proxy=self.c.proxy) as resp:
                    img = await resp.read()
                    with io.BytesIO(img) as file:
                        await interaction.followup.send(
                            file=discord.File(
                                fp=file,
                                filename=name,
                                description=f"Emoji (sticker): {name}",
                            )
                        )
        except Exception as err:
            await interaction.followup.send(
                f"> Fetch emoji [{name}]({imgurl}) **ERROR**: `{err}`",
                ephemeral=True,
            )

    # ========== Prefix Commands ==========

    @commands.group(name="emoji", invoke_without_command=True)
    async def prefix_emoji(self, ctx: commands.Context):
        await ctx.send("Use subcommands: `emoji update`, `emoji info`, or `e <name>`")

    @prefix_emoji.command(name="update")
    @u.requires(u.Permission.ADMIN, perm_module="emoji")
    async def prefix_emoji_update(self, ctx: commands.Context):
        await ctx.defer()
        succ, err = await self.update_emoji_list()
        if succ:
            msg = (
                f"**:white_check_mark: Update Emoji Success!**\n"
                f"> **Build Time**: <t:{self.emoji_data.utc_build_timestamp}:f>\n"
                f"> **Commit**: [`{self.emoji_data.commit_id}`]"
                f"(https://github.com/siiway/ghimg/commit/{self.emoji_data.commit_id})\n"
                f"> **Emojis**: `{len(self.emoji_data.emojis)}`"
            )
            await ctx.send(msg)
            if self.audit:
                await self.audit.log(
                    action="emoji-update",
                    user=ctx.author,
                    guild=ctx.guild,
                    channel=ctx.channel,  # ty:ignore[invalid-argument-type]
                    detail=f"Updated emoji list ({len(self.emoji_data.emojis)} total)",
                )
        else:
            await ctx.send(f"**:x: Update Emoji Failed: {err}**", delete_after=10)

    @prefix_emoji.command(name="info")
    async def prefix_emoji_info(self, ctx: commands.Context):
        if not await self._check_rate_limit(ctx, "emoji-info"):
            return
        ed = self.emoji_data
        msg = (
            f"**:information_source: Emojis Info**\n"
            f"> **Build Time**: <t:{ed.utc_build_timestamp}:f>\n"
            f"> **Build on CF Pages**: {'Yes' if ed.is_cf_pages else 'No'}\n"
            f"> **Commit ID**: [`{ed.commit_id}`]"
            f"(https://github.com/siiway/ghimg/commit/{ed.commit_id})\n"
            f"> **Commit Branch**: `{ed.commit_branch}`\n"
            f"> **Emoji Count**: {len(ed.emojis)}\n"
            f"> **Emoji Source**: [`emoji.json`]"
            f"({self.c.emoji.base_url}/emoji.json?disable-cache)"
        )
        await ctx.send(msg)

    @commands.command(name="e")
    async def prefix_e(self, ctx: commands.Context, *, name: str):
        if not await self._check_rate_limit(ctx, "e"):
            return
        if name not in self.emoji_data.emojis:
            await ctx.send(
                ":x: **Invalid emoji name, please select from list**", delete_after=10
            )
            return

        imgurl = f"{self.c.emoji.base_url}/{name}"
        await ctx.defer()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(imgurl, proxy=self.c.proxy) as resp:
                    img = await resp.read()
                    with io.BytesIO(img) as file:
                        await ctx.send(
                            file=discord.File(
                                fp=file,
                                filename=name,
                                description=f"Emoji (sticker): {name}",
                            )
                        )
        except Exception as err:
            await ctx.send(
                f"> Fetch emoji [{name}]({imgurl}) **ERROR**: `{err}`", delete_after=10
            )

    # ========== Shared Logic ==========

    async def _check_rate_limit(self, source, command: str) -> bool:
        rl = self.c.emoji.ratelimit
        if not rl.enabled:
            return True
        user = source.user if isinstance(source, discord.Interaction) else source.author
        if u.is_admin(user, self.c):
            return True
        base = rl.limit_for(command)
        if base is None:
            return True
        rate_limiter = getattr(self.bot, "rate_limiter", None)
        if not rate_limiter:
            return True
        guild = getattr(source, "guild", None)
        limit = base * rl.mod_multiplier if u.is_mod(user, self.c, guild) else base
        allowed, retry_after = rate_limiter.hit((command, user.id), limit, rl.window)
        if not allowed:
            await u.send_msg(
                source,
                f":hourglass_flowing_sand: **Rate limited, retry in `{retry_after:.0f}s`**",
                ephemeral=True,
                delete_after=10,
            )
            return False
        return True

    async def update_emoji_list(self) -> tuple[bool, str]:
        l.info("[emoji] Updating emoji list...")
        succ, resp, err = await u.get_json(
            f"{self.c.emoji.base_url}/emoji.json?disable-cache"
        )
        if succ:
            try:
                self.bot.emoji_data = EmojiModel.model_validate(resp)  # ty:ignore[unresolved-attribute]
            except ValidationError as e:
                l.warning(f"[emoji] Emoji list sync failed! \n{e}")
                return False, str(e)
            l.info(f"[emoji] Emoji list synced (count: {len(self.emoji_data.emojis)})")
            l.debug(f"[emoji] {self.emoji_data.emojis}")
            return True, ""
        else:
            l.warning(f"[emoji] Emoji list sync failed: {err}")
            return False, err


async def setup(bot: commands.Bot):
    if bot.config.emoji.enabled:  # ty:ignore[unresolved-attribute]
        await bot.add_cog(EmojiCog(bot))
        l.info("EmojiCog loaded.")
