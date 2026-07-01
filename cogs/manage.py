from fnmatch import fnmatch

import discord
from discord.ext import commands


class ManageCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.c = bot.config  # ty:ignore[unresolved-attribute]

    @commands.Cog.listener("on_message")
    async def manage_on_message(self, message: discord.Message):
        if self.c.rmmsg.enabled:
            for nick in self.c.rmmsg.nicks:
                if fnmatch(message.author.name, nick):
                    await message.delete(delay=2)
                    break

        if (
            self.c.rmtodo.enabled
            and (message.channel.id in self.c.rmtodo.todo_channels)
            and (message.author.id == self.c.rmtodo.author_id)
            and (not message.embeds)
        ):
            await message.delete(delay=self.c.rmtodo.remove_delay)


async def setup(bot: commands.Bot):
    if bot.config.rmmsg.enabled or bot.config.rmtodo.enabled:  # ty:ignore[unresolved-attribute]
        await bot.add_cog(ManageCog(bot))
