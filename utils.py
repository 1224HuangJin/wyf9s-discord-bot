# coding: utf-8
import datetime


def utc_timestamp() -> int:
    '''
    返回以秒记的 UTC 时间戳
    '''
    return int(datetime.datetime.now(datetime.timezone.utc).timestamp())
