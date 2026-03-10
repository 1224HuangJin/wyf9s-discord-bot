import time
from pathlib import Path
import os

from loguru import logger as l
import aiohttp

def perf_counter():
    '''
    获取一个性能计数器, 执行返回函数来结束计时, 并返回保留两位小数的毫秒值
    '''
    start = time.perf_counter()
    return lambda: round((time.perf_counter() - start)*1000, 2)


def get_path(path: str, create_dirs: bool = True, is_dir: bool = False) -> str:
    '''
    相对路径 (基于主程序目录) -> 绝对路径

    :param path: 相对路径
    :param create_dirs: 是否自动创建目录（如果不存在）
    :param is_dir: 目标是否为目录
    :return: 绝对路径
    '''
    full_path = str(Path(__file__).parent.joinpath(path))
    if create_dirs:
        # 自动创建目录
        if is_dir:
            os.makedirs(full_path, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
    return full_path


def relative_path(path: str) -> str:
    '''
    绝对路径 -> 相对路径
    '''
    return os.path.relpath(path)


async def get_json(url: str, **params) -> tuple[bool, dict, str]:
    '''
    使用 aiohttp 异步请求 json 资源

    :param url: 请求的 url
    :param params: 其他传递给 `session.get` 的参数
    :return bool: success
    :return dict: response
    :return str: error
    '''
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(url, **params) as resp:
                if resp.status == 200:
                    return True, await resp.json(), ''
                else:
                    raise Exception(f'Status code isn\'t 200: {resp.status}')
    except Exception as e:
        l.warning(f'[get_json] Request {url} error: {e}')
        return False, {}, str(e)
