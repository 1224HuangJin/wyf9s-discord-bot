import time
from pathlib import Path
import os
import re

from loguru import logger as l
import discord
from discord.ext import commands
import aiohttp


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
