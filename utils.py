import time
import enum
import functools
from pathlib import Path
from collections import defaultdict, deque
import os
import re
import typing as t

from loguru import logger as l
import discord
from discord.ext import commands
import aiohttp

if t.TYPE_CHECKING:
    from config import ConfigModel


def perf_counter():
    """
    获取一个性能计数器, 执行返回函数来结束计时, 并返回保留两位小数的毫秒值
    """
    start = time.perf_counter()
    return lambda: round((time.perf_counter() - start) * 1000, 2)


def get_path(path: str, create_dirs: bool = True, is_dir: bool = False) -> str:
    """
    相对路径 (基于主程序目录) -> 绝对路径

    :param path: 相对路径
    :param create_dirs: 是否自动创建目录（如果不存在）
    :param is_dir: 目标是否为目录
    :return: 绝对路径
    """
    full_path = str(Path(__file__).parent.joinpath(path))
    if create_dirs:
        # 自动创建目录
        if is_dir:
            os.makedirs(full_path, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
    return full_path


def relative_path(path: str) -> str:
    """
    绝对路径 -> 相对路径
    """
    return os.path.relpath(path)


async def get_json(url: str, **params) -> tuple[bool, dict, str]:
    """
    使用 aiohttp 异步请求 json 资源

    :param url: 请求的 url
    :param params: 其他传递给 `session.get` 的参数
    :return bool: success
    :return dict: response
    :return str: error
    """
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, **params) as resp:
                if resp.status == 200:
                    return True, await resp.json(), ""
                else:
                    raise Exception(f"Status code isn't 200: {resp.status}")
    except Exception as e:
        l.warning(f"[get_json] Request {url} error: {e}")
        return False, {}, str(e)


async def send_msg(
    source: discord.Interaction | commands.Context,
    content: str | None = None,
    *,
    ephemeral: bool = False,
    delete_after: float | None = None,
    **kwargs,
) -> discord.Message | None:
    """
    统一发送消息: 支持 Interaction (followup) 和 Context (reply to original message)

    prefix 模式下自动回复原消息, 失败则 fallback 到直接发送
    """
    if isinstance(source, discord.Interaction):
        if source.response.is_done():
            return await source.followup.send(content, ephemeral=ephemeral, **kwargs)  # type: ignore
        else:
            await source.response.send_message(
                content, ephemeral=ephemeral, delete_after=delete_after, **kwargs
            )
            return None
    else:
        try:
            return await source.send(
                content=content,
                reference=source.message,
                delete_after=delete_after,
                **kwargs,
            )  # ty:ignore[no-matching-overload]
        except (discord.HTTPException, discord.NotFound):
            return await source.send(
                content=content, delete_after=delete_after, **kwargs
            )  # ty:ignore[no-matching-overload]


# ========== Permission Helpers (shared) ==========


def matches_identity(
    user: discord.User | discord.Member, values: "list[int | str]"
) -> bool:
    """检查用户是否匹配 ID / 用户名列表中的任意一项"""
    for value in values:
        if user.id == value or user.name == value:
            return True
        if isinstance(value, str) and value.isdigit() and user.id == int(value):
            return True
    return False


def is_server_admin(user: discord.User | discord.Member) -> bool:
    """是否为服务器管理员 (拥有 administrator 权限)"""
    return isinstance(user, discord.Member) and user.guild_permissions.administrator


def is_config_admin(user: discord.User | discord.Member, config: "ConfigModel") -> bool:
    """是否在配置的 admins 名单中"""
    return matches_identity(user, config.admins.users)


def is_admin(user: discord.User | discord.Member, config: "ConfigModel") -> bool:
    """是否为管理员 (服务器管理员 或 配置 admin)"""
    return is_server_admin(user) or is_config_admin(user, config)


def is_mod(
    user: discord.User | discord.Member,
    config: "ConfigModel",
    guild: discord.Guild | None = None,
) -> bool:
    """是否为 mod (管理员 或 全局/服务器 mod 名单)"""
    if is_admin(user, config):
        return True
    if isinstance(user, discord.Member):
        if matches_identity(user, config.mods.users):
            return True
        if guild is not None:
            guild_users = config.mods.guilds.get(
                guild.id, config.mods.guilds.get(str(guild.id), [])
            )
            return matches_identity(user, guild_users)
    return False


# ========== Declarative Permission Control ==========


class Permission(enum.Enum):
    """指令所需的权限等级 (声明式)"""

    EVERYONE = "everyone"
    """所有人可用"""

    MOD = "mod"
    """需要 mod (含 admin)"""

    ADMIN = "admin"
    """需要 admin (服务器管理员 / 配置 admin)"""


# 自定义权限判定: (module, user, guild) -> bool
PermissionCheck = t.Callable[
    [t.Any, "discord.User | discord.Member", "discord.Guild | None"], bool
]

DEFAULT_DENY_MESSAGE = ":x: **你没有权限使用此指令** :x:"


def has_permission(
    perm: "Permission | PermissionCheck",
    module: t.Any,
    user: discord.User | discord.Member,
    guild: discord.Guild | None,
) -> bool:
    """
    统一权限判定

    :param perm: Permission 等级 或 自定义判定函数
    :param module: 指令所属模块实例 (需含 `.c` 配置)
    :param user: 触发用户
    :param guild: 触发所在服务器
    """
    if callable(perm):
        return perm(module, user, guild)
    config = module.c
    if perm is Permission.EVERYONE:
        return True
    if perm is Permission.MOD:
        return is_mod(user, config, guild)
    if perm is Permission.ADMIN:
        return is_admin(user, config)
    return False


def requires(
    perm: "Permission | PermissionCheck",
    *,
    deny: "str | t.Callable[[discord.User | discord.Member], str]" = DEFAULT_DENY_MESSAGE,
    perm_module: str | None = None,
    perm_command: str | None = None,
):
    """
    声明式权限控制装饰器, 用于模块的 `_handle_*` 方法

    - 自动从 `source` (Interaction / Context) 解析用户与服务器
    - 统一走 `has_permission` 判定, 不通过则回复拒绝消息并中止
    - 若 config 权限未通过, 回退到 perm.yaml 动态权限检查

    用法::

        @u.requires(u.Permission.MOD)
        async def _handle_xxx(self, source, ...):
            ...
    """

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, source, *args, **kwargs):
            user = (
                source.user
                if isinstance(source, discord.Interaction)
                else source.author
            )
            guild = getattr(source, "guild", None)

            if has_permission(perm, self, user, guild):
                return await func(self, source, *args, **kwargs)

            # Fallback: check perm.yaml dynamic permissions
            bot = getattr(self, "bot", None)
            perm_store = getattr(bot, "perm_store", None) if bot else None
            if perm_store:
                mod_name = perm_module
                cmd_name = perm_command
                if mod_name is None and cmd_name is None:
                    cmd_name = func.__name__.removeprefix("_handle_")
                if perm_store.check(
                    str(user.id),
                    guild.id if guild else None,
                    module=mod_name,
                    command=cmd_name,
                ):
                    return await func(self, source, *args, **kwargs)

            deny_msg = deny if isinstance(deny, str) else deny(user)
            await send_msg(source, deny_msg, ephemeral=True, delete_after=10)
            return None

        return wrapper

    return decorator


# ========== Rate Limiter ==========


class RateLimiter:
    """
    基于滑动窗口的简单限速器

    以 (指令, 用户) 为 key 记录调用时间戳, 判断是否超出窗口内的次数上限
    """

    def __init__(self):
        self._hits: dict[t.Hashable, deque[float]] = defaultdict(deque)

    def hit(self, key: t.Hashable, limit: int, window: float) -> tuple[bool, float]:
        """
        记录一次调用并判断是否允许

        :param key: 限速 key (通常为 (command, user_id))
        :param limit: 窗口内允许的最大次数
        :param window: 窗口时长 (秒)
        :return: (是否允许, 若被限则需等待的秒数)
        """
        now = time.monotonic()
        dq = self._hits[key]
        # 清理过期记录
        while dq and dq[0] <= now - window:
            dq.popleft()
        if len(dq) >= limit:
            retry_after = window - (now - dq[0])
            return False, max(retry_after, 0.0)
        dq.append(now)
        return True, 0.0


def parse_flags(content: str) -> dict[str, str]:
    """
    从消息内容中解析 --key=value 格式的标志
    """
    flags: dict[str, str] = {}
    for match in re.finditer(r'--([\w-]+)=(?:"([^"]*)"|(\S+))', content):
        key = match.group(1)
        value = match.group(2) if match.group(2) is not None else match.group(3)
        flags[key] = value
    return flags
