# coding: utf-8
from logging import getLogger

import discord
from discord.ext import commands

from config import ConfigModel

l = getLogger(__name__)


class ManageModule:
    c: ConfigModel
    client: commands.Bot

    def __init__(self, config: ConfigModel, client: commands.Bot):
        self.c = config
        self.client = client

        @client.event
        async def on_message(message: discord.Message):
            if self.c.rmtodo.enabled:
                # 处理桥接加入消息
                if message.author.name == '[DC] @system':
                    await message.delete(
                        delay=2
                    )
                # 处理 To-Do List Bot 在 #sleepy-todo 的新消息
                elif (message.channel.id in self.c.rmtodo.todo_channels) and (message.author.id == self.c.rmtodo.author_id) and (not message.embeds):
                    await message.delete(
                        delay=self.c.rmtodo.remove_delay
                    )
