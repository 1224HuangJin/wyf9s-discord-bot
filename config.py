from logging import getLogger
import typing as t

from pydantic import BaseModel, field_validator
from yaml import safe_load

import utils as u

l = getLogger(__name__)


class _LoggingConfigModel(BaseModel):
    '''
    日志配置 Model
    '''

    level: t.Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'] = 'INFO'
    '''
    日志等级
    - DEBUG
    - INFO
    - WARNING
    - ERROR
    - CRITICAL
    '''

    file: str | None = 'logs/{time:YYYY-MM-DD}.log'
    '''
    日志文件保存格式 (for Loguru)
    - 设置为 None 以禁用
    '''

    file_level: t.Literal['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', None] = 'INFO'
    '''
    单独设置日志文件中的日志等级, 如设置为 None 则使用 level 设置
    - DEBUG
    - INFO
    - WARNING
    - ERROR
    - CRITICAL
    '''

    rotation: str | int = '1 days'
    '''
    配置 Loguru 的 rotation (轮转周期) 设置
    '''

    retention: str | int = '3 days'
    '''
    配置 Loguru 的 retention (轮转保留) 设置
    '''

    @field_validator('level', 'file_level', mode='before')
    def normalize_level(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError(f'Invaild log level: {v}')
        upper = v.strip().upper()
        valid = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if upper not in valid:
            raise ValueError(f'Invaild log level: {v}')
        return upper


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


class _AutoRemoveMessageConfigModel(BaseModel):
    enabled: bool = False
    '''
    是否启用
    '''

    nicks: list[str] = []
    '''
    要自动删除的昵称列表
    - 比如 `[DC] @system`
    - 支持通配符
    '''


class ConfigModel(BaseModel):
    '''
    基础配置
    '''

    token: str
    '''Bot Token'''

    proxy: str | None = None
    '''代理地址'''

    command_prefix: str = '\\'
    '''命令前缀 (unused?)'''

    secret_message_delay: int = 600
    '''私密消息删除延迟 (秒)'''

    log: _LoggingConfigModel = _LoggingConfigModel()
    emoji: _EmojiConfigModel = _EmojiConfigModel()
    rmtodo: _AutoRemoveTodoConfigModel = _AutoRemoveTodoConfigModel()
    rmmsg: _AutoRemoveMessageConfigModel = _AutoRemoveMessageConfigModel()


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

        if self.config.log.level == 'DEBUG':
            l.debug(f'[config] init took {perf()}ms')
