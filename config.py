import typing as t

from loguru import logger as l
from pydantic import BaseModel, ConfigDict, Field, field_validator
from yaml import safe_load

import utils as u


class _LoggingConfigModel(BaseModel):
    """
    日志配置 Model
    """

    level: t.Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    """
    日志等级
    - DEBUG
    - INFO
    - WARNING
    - ERROR
    - CRITICAL
    """

    file: str | None = "logs/{time:YYYY-MM-DD}.log"
    """
    日志文件保存格式 (for Loguru)
    - 设置为 None 以禁用
    """

    file_level: t.Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", None] = (
        "INFO"
    )
    """
    单独设置日志文件中的日志等级, 如设置为 None 则使用 level 设置
    - DEBUG
    - INFO
    - WARNING
    - ERROR
    - CRITICAL
    """

    rotation: str | int = "1 days"
    """
    配置 Loguru 的 rotation (轮转周期) 设置
    """

    retention: str | int = "3 days"
    """
    配置 Loguru 的 retention (轮转保留) 设置
    """

    @field_validator("level", "file_level", mode="before")
    def normalize_level(cls, v):
        if v is None:
            return v
        if not isinstance(v, str):
            raise ValueError(f"Invaild log level: {v}")
        upper = v.strip().upper()
        valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if upper not in valid:
            raise ValueError(f"Invaild log level: {v}")
        return upper


class _EmojiConfigModel(BaseModel):
    """
    Emoji 模块配置
    指令: emoji, emoji-info, emoji-update
    """

    enabled: bool = False
    """是否启用 Emoji 模块"""

    slash: bool = True
    """是否注册斜杠指令"""

    prefix: bool = True
    """是否注册前缀指令"""

    base_url: str = "https://ghimg.siiway.top/emoji"
    """基础 url (末尾不加 `/`, 目录需包含 `emoji.json`)"""

    max_results: int = 25
    """表情搜索的最大结果数 (设置过大可能导致调用失败)"""


class _AutoRemoveTodoConfigModel(BaseModel):
    """
    自动删除 todo bot 消息配置
    `rmtodo` (无指令, 基于事件)
    """

    enabled: bool = False
    """是否启用 AutoRemoveTodo 模块"""

    todo_channels: list[int] = []
    """todo 频道列表 (频道中 To-Do List Bot 发送的带 embeds 的消息会被自动删除)"""

    author_id: int = 782105629572464652
    """todo bot 的用户 id"""

    remove_delay: int = 3
    """移除前等待秒数"""


class _AutoRemoveMessageConfigModel(BaseModel):
    """
    自动删除消息配置
    `rmmsg` (无指令, 基于事件)
    """

    enabled: bool = False
    """是否启用"""

    nicks: list[str] = []
    """
    要自动删除的昵称列表
    - 比如 `[DC] @system`
    - 支持通配符
    """


class _VoiceChannelConfigModel(BaseModel):
    """
    语音频道控制模块配置
    指令: joinvc, leavevc
    """

    enabled: bool = False
    """是否启用语音频道控制模块"""

    slash: bool = True
    """是否注册斜杠指令"""

    prefix: bool = True
    """是否注册前缀指令"""

    allowed_user_ids: list[int | str] = []
    """
    允许使用 join/leave vc 命令的用户 ID 列表
    - 留空则所有人可用
    """


class _AuditLogConfigModel(BaseModel):
    """
    管理员操作执行日志配置
    `audit` (无指令, 服务模块)
    """

    enabled: bool = False
    """是否启用执行日志"""

    global_channel: int | None = None
    """
    全局日志频道 ID
    - 所有服务器的管理操作都会发送到这里
    - 设置为 None 以禁用全局日志
    """

    guilds: dict[int | str, int] = {}
    """
    按服务器单独配置的日志频道
    - key 为 guild id (可写数字或字符串), value 为目标频道 id
    - 与全局日志互不影响: 若两者都配置, 则两个频道都会收到日志
    """


class _PermissionListConfigModel(BaseModel):
    """
    通用权限名单配置
    """

    users: list[int | str] = []
    """
    允许的用户 ID / 用户名列表
    """


class _ScopedPermissionListConfigModel(BaseModel):
    """
    支持全局和按服务器配置的权限名单
    """

    users: list[int | str] = []
    """全局允许的用户 ID / 用户名列表"""

    guilds: dict[int | str, list[int | str]] = {}
    """按服务器配置的允许列表，key 为 guild id，可写数字或字符串"""


class _ToolsConfigModel(BaseModel):
    """
    工具/管理指令模块配置
    指令: random, uuid, delete, clear-message, move-channel, sync
    """

    enabled: bool = False
    """是否启用工具模块"""

    slash: bool = True
    """是否注册斜杠指令"""

    prefix: bool = True
    """是否注册前缀指令"""


class _LockConfigModel(BaseModel):
    """
    频道锁定模块配置
    指令: lock, unlock, plan-lock
    """

    enabled: bool = False
    """是否启用锁定模块"""

    slash: bool = True
    """是否注册斜杠指令"""

    prefix: bool = True
    """是否注册前缀指令"""


class _SpamCatcherRuleConfigModel(BaseModel):
    """spam-catcher 单频道规则"""

    model_config = ConfigDict(populate_by_name=True)

    spammer: t.Literal["kick", "ban"] = "ban"
    """陌生账号处理方式"""

    hacked: t.Literal["kick", "ban", "mute"] | int = "mute"
    """正常账号疑似被盗处理方式: kick/ban/mute/分钟数"""

    clear_message: int | None = Field(default=3, alias="clear-message")
    """清理消息窗口 (分钟), null/false 表示禁用"""

    public_log: bool = Field(default=True, alias="public-log")
    """是否在频道公开通知处理结果"""

    stranger_roles: list[int | str] = Field(
        default_factory=list, alias="stranger-roles"
    )
    """被视为陌生账号的角色列表 (支持身份组 ID 或名称)"""

    @field_validator("clear_message", mode="before")
    def normalize_clear_message(cls, v):
        if v in (None, False):
            return None
        if isinstance(v, bool):
            raise ValueError("clear-message must be int or null/false")
        return v

    @field_validator("hacked", mode="before")
    def normalize_hacked(cls, v):
        if isinstance(v, bool):
            raise ValueError("hacked must be kick/ban/mute or minutes")
        return v


class _AntiSpamConfigModel(BaseModel):
    """
    反垃圾消息模块配置
    无指令 (基于事件)
    """

    model_config = ConfigDict(populate_by_name=True)

    enabled: bool = False
    """是否启用反垃圾消息模块"""

    spam_catcher: dict[int | str, _SpamCatcherRuleConfigModel] = Field(
        default_factory=dict, alias="spam-catcher"
    )
    """按频道配置的捕获规则"""


class ConfigModel(BaseModel):
    """
    基础配置
    """

    token: str
    """Bot Token"""

    proxy: str | None = None
    """代理地址"""

    command_prefix: str = "\\"
    """命令前缀 (unused?)"""

    secret_message_delay: int = 600
    """私密消息删除延迟 (秒)"""

    log: _LoggingConfigModel = _LoggingConfigModel()
    audit: _AuditLogConfigModel = _AuditLogConfigModel()
    emoji: _EmojiConfigModel = _EmojiConfigModel()
    tools: _ToolsConfigModel = _ToolsConfigModel()
    lock: _LockConfigModel = _LockConfigModel()
    antispam: _AntiSpamConfigModel = _AntiSpamConfigModel()
    rmtodo: _AutoRemoveTodoConfigModel = _AutoRemoveTodoConfigModel()
    rmmsg: _AutoRemoveMessageConfigModel = _AutoRemoveMessageConfigModel()
    voicechannel: _VoiceChannelConfigModel = _VoiceChannelConfigModel()
    admins: _PermissionListConfigModel = _PermissionListConfigModel()
    mods: _ScopedPermissionListConfigModel = _ScopedPermissionListConfigModel()


class Config:
    """
    配置系统
    """

    config: ConfigModel

    def __init__(self):
        perf = u.perf_counter()

        # prepare yaml
        try:
            with open(u.get_path("config.yaml"), "r", encoding="utf-8") as f:
                raw_config: dict = safe_load(f)
        except FileNotFoundError:
            l.error("Config file config.yaml not found!")
            exit(1)
        except Exception as e:
            l.error(f"Error when loading config.yaml: {e}")

        # process config
        self.config = ConfigModel.model_validate(raw_config)

        if self.config.log.level == "DEBUG":
            l.debug(f"[config] init took {perf()}ms")
