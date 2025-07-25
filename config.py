# coding: utf-8
# GHIMG_BASE = 'https://ghimg.siiway.top/emoji'
# SECRET_MESSAGE_DELETE_SECOND = 600
# COMMAND_PREFIX = '//'
# MAX_RESULTS = 25
# TODO_CHANNELS = [
#     1368199180991860746
# ]

from pydantic import BaseModel


class _EmojiConfigModel(BaseModel):
    '''
    Emoji 模块配置
    `emoji`
    '''
    enabled: bool = True

    base_url: str = 'https://ghimg.siiway.top/emoji'
    '''基础 url (末尾不加 `/`, 目录需包含 `emoji.json`)'''

    max_results: int = 25
    '''表情搜索的最大结果数 (设置过大可能导致调用失败)'''

class ConfigModel(BaseModel):
    '''
    基础配置
    '''

    token: str
    '''Bot Token'''

    command_prefix: str = '\\'
    '''命令前缀 (unused?)'''

    secret_message_delay: int = 600
    '''私密消息删除延迟 (秒)'''

    emoji: _EmojiConfigModel = _EmojiConfigModel()

class Config:
    '''
    配置系统
    '''

    config: ConfigModel