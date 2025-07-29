# coding: utf-8
from logging import getLogger

from pydantic import BaseModel
import discord

import utils as u

class EmojiModel(BaseModel):
    utc_build_timestamp: int = 0
    is_cf_pages: bool = False
    commit_id: str | None = None
    commit_branch: str | None = None
    emojis: list[str] = []

class EmojiModule:
    emoji: EmojiModel = EmojiModel()

    def __init__(self, client: discord.Client):
        