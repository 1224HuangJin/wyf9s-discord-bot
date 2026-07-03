import discord
from discord import app_commands
from discord.ext import commands

from i18n import t as _t
from lang_store import LangStore
import utils as u


class LangCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.c = bot.config  # ty:ignore[unresolved-attribute]
        self.lang_store: LangStore = getattr(bot, "lang_store")

    @app_commands.command(name="lang", description=_t("lang.command_description", "en"))
    @app_commands.describe(
        lang=_t("lang.param_lang_description", "en"),
        scope=_t("lang.param_scope_description", "en"),
    )
    async def slash_lang(
        self,
        interaction: discord.Interaction,
        lang: str | None = None,
        scope: str = "user",
    ):
        lang_val = lang.strip().lower() if lang else None
        scope_val = scope.strip().lower()

        if lang_val is not None and lang_val not in ("zh", "en"):
            await interaction.response.send_message(
                ":x: **Invalid language. Use `zh` or `en`**",
                ephemeral=True,
            )
            return

        if scope_val not in ("user", "server"):
            await interaction.response.send_message(
                ":x: **Invalid scope. Use `user` or `server`**",
                ephemeral=True,
            )
            return

        resolved = self.lang_store.resolve(
            interaction.user.id,
            interaction.guild.id if interaction.guild else None,
        )

        if scope_val == "server":
            if interaction.guild is None:
                await interaction.response.send_message(
                    _t("lang.not_server", resolved),
                    ephemeral=True,
                )
                return
            if not (
                isinstance(interaction.user, discord.Member)
                and interaction.user.guild_permissions.manage_guild
            ) and not u.is_admin(interaction.user, self.c):
                await interaction.response.send_message(
                    _t("lang.server_no_permission", resolved),
                    ephemeral=True,
                )
                return
            if lang_val is None:
                current = self.lang_store.get_guild(interaction.guild.id)
                await interaction.response.send_message(
                    _t("lang.show_server", resolved, lang=current or "zh"),
                    ephemeral=True,
                )
                return
            self.lang_store.set_guild(interaction.guild.id, lang_val)
            await interaction.response.send_message(
                _t("lang.set_server", resolved, lang=lang_val),
                ephemeral=True,
            )
            return

        if lang_val is None:
            current = self.lang_store.get_user(interaction.user.id)
            await interaction.response.send_message(
                _t("lang.show_user", resolved, lang=current or "zh"),
                ephemeral=True,
            )
            return
        self.lang_store.set_user(interaction.user.id, lang_val)
        await interaction.response.send_message(
            _t("lang.set_user", resolved, lang=lang_val),
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(LangCog(bot))
