# coding: utf-8
# GHIMG_BASE = 'https://ghimg.siiway.top/emoji'
# SECRET_MESSAGE_DELETE_SECOND = 600
# COMMAND_PREFIX = '//'
# MAX_RESULTS = 25
# TODO_CHANNELS = [
#     1368199180991860746
# ]
from pydantic import BaseModel
from yaml import safe_load
import os
from logging import getLogger

import utils as u

l = getLogger(__name__)


class _EmojiConfigModel(BaseModel):
    '''
    Emoji 模块配置
    `emoji`
    '''
    enabled: bool = True
    '''是否启用 Emoji 模块'''

    base_url: str = 'https://ghimg.siiway.top/emoji'
    '''基础 url (末尾不加 `/`, 目录需包含 `emoji.json`)'''

    max_results: int = 25
    '''表情搜索的最大结果数 (设置过大可能导致调用失败)'''


class _AutoRemoveTodoConfigModel(BaseModel):
    '''
    自动删除 todo bot 消息配置
    `rmtodo`
    '''

    enabled: bool = False
    '''是否启用 AutoRemoveTodo 模块'''

    todo_channels: list[int] = []
    '''todo 频道列表 (频道中 To-Do List Bot 发送的带 embeds 的消息会被自动删除)'''

    author_id: int = 782105629572464652
    '''todo bot 的用户 id'''

    remove_delay: int = 3
    '''移除前等待秒数'''

class ConfigModel(BaseModel):
    '''
    基础配置
    '''

    debug: bool = False
    '''是否开启调试模式 (更详细的输出)'''

    log_file: str | None = None
    '''日志文件 (为空禁用)'''

    token: str
    '''Bot Token'''

    proxy: str | None = None
    '''代理地址'''

    command_prefix: str = '\\'
    '''命令前缀 (unused?)'''

    secret_message_delay: int = 600
    '''私密消息删除延迟 (秒)'''

    emoji: _EmojiConfigModel = _EmojiConfigModel()

    rmtodo: _AutoRemoveTodoConfigModel = _AutoRemoveTodoConfigModel()


class Config:
    '''
    配置系统
    '''

    config: ConfigModel

    def __init__(self):
        perf = u.perf_counter()

        # prepare yaml
        try:
            with open(u.get_path('config.yaml'), 'r', encoding='utf-8') as f:
                raw_config: dict = safe_load(f)
        except FileNotFoundError:
            l.error('Config file config.yaml not found!')
            exit(1)
        except Exception as e:
            l.error(f'Error when loading config.yaml: {e}')

        # process config
        self.config = ConfigModel.model_validate(raw_config)

        if self.config.debug:
            l.debug(f'[config] init took {perf()}ms')
