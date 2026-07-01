import io

from loguru import logger as l
from pydantic import BaseModel, ValidationError
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

from config import ConfigModel
from modules.audit import AuditLogger
import utils as u


class EmojiModel(BaseModel):
    utc_build_timestamp: int = 0
    is_cf_pages: bool = False
    commit_id: str | None = None
    commit_branch: str | None = None
    emojis: list[str] = []


class EmojiModule:
    emoji: EmojiModel = EmojiModel()
    c: ConfigModel
    client: commands.Bot
    audit: AuditLogger | None

    def __init__(
        self, config: ConfigModel, client: commands.Bot, audit: AuditLogger | None
    ):
        self.c = config
        self.client = client
        self.audit = audit

        if self.c.emoji.slash:
            self._register_slash_commands(client)

        if self.c.emoji.prefix:
            self._register_prefix_commands(client)

    def _register_slash_commands(self, client: commands.Bot):
        @client.tree.command(name="emoji-update", description="更新表情包库数据")
        async def emoji_update(interaction: discord.Interaction):
            await self._handle_emoji_update(interaction)

        @client.tree.command(name="emoji-info", description="查看表情包库相关信息")
        async def emoji_info(interaction: discord.Interaction):
            await self._handle_emoji_info(interaction)

        # ----- Send ------

        async def emoji_autocomplete(
            interaction: discord.Interaction, current: str
        ) -> list[app_commands.Choice[str]]:
            filtered = [
                app_commands.Choice(name=name, value=name)
                for name in self.emoji.emojis
                if current.lower() in name.lower()
            ][: self.c.emoji.max_results]
            return filtered

        @client.tree.command(name="emoji", description="使用库中的表情包")
        @app_commands.describe(name="输入名称搜索表情包")
        @app_commands.autocomplete(name=emoji_autocomplete)
        async def emoji(interaction: discord.Interaction, name: str):
            await self._handle_emoji(interaction, name)

    def _register_prefix_commands(self, client: commands.Bot):
        @client.command(name="emoji-update")
        async def prefix_emoji_update(ctx: commands.Context):
            await self._handle_emoji_update(ctx)

        @client.command(name="emoji-info")
        async def prefix_emoji_info(ctx: commands.Context):
            await self._handle_emoji_info(ctx)

        @client.command(name="emoji")
        async def prefix_emoji(ctx: commands.Context, *, name: str):
            await self._handle_emoji(ctx, name)

    # ========== Shared Logic ==========

    @u.requires(u.Permission.ADMIN)
    async def _handle_emoji_update(self, source):
        user = source.user if isinstance(source, discord.Interaction) else source.author

        if isinstance(source, discord.Interaction):
            await source.response.defer()
        else:
            await source.defer()

        succ, err = await self.update_emoji_list()
        if succ:
            msg = (
                f"**:white_check_mark: Update Emoji Success!**\n"
                f"> **Build Time**: <t:{self.emoji.utc_build_timestamp}:f>\n"
                f"> **Commit**: [`{self.emoji.commit_id}`](https://github.com/siiway/ghimg/commit/{self.emoji.commit_id})\n"
                f"> **Emojis**: `{len(self.emoji.emojis)}`"
            )
            await u.send_msg(source, msg)
            if self.audit:
                await self.audit.log(
                    action="emoji-update",
                    user=user,
                    guild=source.guild,
                    channel=source.channel,
                    detail=f"更新表情包库 (共 {len(self.emoji.emojis)} 个)",
                )
        else:
            await u.send_msg(
                source, f"**:x: Update Emoji Failed: {err}**", ephemeral=True
            )

    async def _handle_emoji_info(self, source):
        msg = (
            f"**:information_source: Emojis Info**\n"
            f"> **Build Time**: <t:{self.emoji.utc_build_timestamp}:f>\n"
            f"> **Build on CF Pages**: {'Yes' if self.emoji.is_cf_pages else 'No'}\n"
            f"> **Commit ID**: [`{self.emoji.commit_id}`](https://github.com/siiway/ghimg/commit/{self.emoji.commit_id})\n"
            f"> **Commit Branch**: `{self.emoji.commit_branch}`\n"
            f"> **Emoji Count**: {len(self.emoji.emojis)}\n"
            f"> **Emoji Source**: [`emoji.json`]({self.c.emoji.base_url}/emoji.json?disable-cache)"
        )
        await u.send_msg(source, msg)

    async def _handle_emoji(self, source, name: str):
        if name not in self.emoji.emojis:
            await u.send_msg(
                source,
                ":x: **无效的表情包名称，请从列表中选择**",
                ephemeral=True,
                delete_after=10,
            )
            return

        imgurl = f"{self.c.emoji.base_url}/{name}"
        if isinstance(source, discord.Interaction):
            await source.response.defer()
        else:
            await source.defer()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(imgurl, proxy=self.c.proxy) as resp:
                    img = await resp.read()
                    with io.BytesIO(img) as file:
                        await u.send_msg(
                            source,
                            "",
                            file=discord.File(
                                fp=file,
                                filename=name,
                                description=f"Emoji (sticker): {name}",
                            ),
                        )
        except Exception as error:
            await u.send_msg(
                source,
                f"> Fetch emoji [{name}]({imgurl}) **ERROR**: `{error}`",
                ephemeral=True,
            )

    async def update_emoji_list(self) -> tuple[bool, str]:
        l.info("[emoji] Updating emoji list...")
        succ, resp, err = await u.get_json(
            f"{self.c.emoji.base_url}/emoji.json?disable-cache"
        )
        if succ:
            try:
                self.emoji = EmojiModel.model_validate(resp)
            except ValidationError as e:
                l.warning(f"[emoji] Emoji list sync failed! \n{e}")
                return False, str(e)
            l.info(f"[emoji] Emoji list Synced √ (count: {len(self.emoji.emojis)})")
            l.debug(f"[emoji] {self.emoji.emojis}")
            return True, ""
        else:
            l.warning(f"[emoji] Emoji list sync failed: {err}")
            return False, err
