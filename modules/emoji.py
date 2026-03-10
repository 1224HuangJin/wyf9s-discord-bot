import io

from loguru import logger as l
from pydantic import BaseModel, ValidationError
import discord
from discord import app_commands
from discord.ext import commands
import aiohttp

from config import ConfigModel
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

    def __init__(self, config: ConfigModel, client: commands.Bot):
        self.c = config
        self.client = client

        @client.tree.command(
            name='emoji_update',
            description='更新表情包库数据'
        )
        async def emoji_update(interaction: discord.Interaction):
            await interaction.response.defer()
            succ, err = await self.update_emoji_list()
            if succ:
                # Success
                await interaction.followup.send(
                    f'''**:white_check_mark: Update Emoji Success!**
> **Build Time**: <t:{self.emoji.utc_build_timestamp}:f>
> **Commit**: [`{self.emoji.commit_id}`](https://github.com/siiway/ghimg/commit/{self.emoji.commit_id})
> **Emojis**: `{len(self.emoji.emojis)}`'''
                )
            else:
                # Error
                await interaction.followup.send(
                    f'**:x: Update Emoji Failed: {err}**',
                    ephemeral=True
                )

        @client.tree.command(
            name='emoji_info',
            description='查看表情包库相关信息'
        )
        async def emoji_info(interaction: discord.Interaction):
            await interaction.response.send_message(
                f'''**:information_source: Emojis Info**
        > **Build Time**: <t:{self.emoji.utc_build_timestamp}:f>
        > **Build on CF Pages**: {"Yes" if self.emoji.is_cf_pages else "No"}
        > **Commit ID**: [`{self.emoji.commit_id}`](https://github.com/siiway/ghimg/commit/{self.emoji.commit_id})
        > **Commit Branch**: `{self.emoji.commit_branch}`
        > **Emoji Count**: {len(self.emoji.emojis)}
        > **Emoji Source**: [`emoji.json`]({self.c.emoji.base_url}/emoji.json?disable-cache)'''
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
                for name in self.emoji.emojis
                if current.lower() in name.lower()  # 不区分大小写搜索
            ][:self.c.emoji.max_results]  # 最多显示 ?? 个选项
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
            if name not in self.emoji.emojis:
                return await interaction.response.send_message(
                    ":x: **无效的表情包名称，请从列表中选择**",
                    ephemeral=True,
                    delete_after=10
                )

            imgurl = f'{self.c.emoji.base_url}/{name}'
            await interaction.response.defer()
            try:
                async with aiohttp.ClientSession() as session:  # creates session
                    async with session.get(imgurl, proxy=self.c.proxy) as resp:  # gets image from url
                        img = await resp.read()  # reads image from response
                        with io.BytesIO(img) as file:  # converts to file-like object
                            await interaction.followup.send(
                                '',
                                file=discord.File(
                                    fp=file,
                                    filename=name,
                                    description=f'Emoji (sticker): {name}'
                                )
                            )
            except Exception as error:
                await interaction.followup.send(
                    f'> Fetch emoji [{name}]({imgurl}) **ERROR**: `{error}`',
                    ephemeral=True
                )

    async def update_emoji_list(self) -> tuple[bool, str]:
        l.info('[emoji] Updating emoji list...')
        succ, resp, err = await u.get_json(f'{self.c.emoji.base_url}/emoji.json?disable-cache')
        if succ:
            try:
                self.emoji = EmojiModel.model_validate(resp)
            except ValidationError as e:
                l.warning(f'[emoji] Emoji list sync failed! \n{e}')
                return False, str(e)
            l.info(f'[emoji] Emoji list Synced √ (count: {len(self.emoji.emojis)})')
            l.debug(f'[emoji] {self.emoji.emojis}')
            return True, ''
        else:
            l.warning(f'[emoji] Emoji list sync failed: {err}')
            return False, err
