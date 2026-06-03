from fnmatch import fnmatch

import discord
from discord.ext import commands

from config import ConfigModel


class ManageModule:
    c: ConfigModel
    client: commands.Bot

    def __init__(self, config: ConfigModel, client: commands.Bot):
        self.c = config
        self.client = client

        @client.event
        async def on_message(message: discord.Message):
            # 处理自动删除消息
            if self.c.rmmsg.enabled:
                for nick in self.c.rmmsg.nicks:
                    if fnmatch(message.author.name, nick):
                        await message.delete(delay=2)
                        break

            # 处理 To-Do List Bot 在 todo 频道的新消息
            if (
                self.c.rmtodo.enabled
                and (message.channel.id in self.c.rmtodo.todo_channels)
                and (message.author.id == self.c.rmtodo.author_id)
                and (not message.embeds)
            ):
                await message.delete(delay=self.c.rmtodo.remove_delay)
