"""应用层限流备用器（SlowAPI，内存存储）

Nginx 层已处理主要限流策略；此处 default_limits 设为空列表，
仅作为备用：可在特定接口上用 @limiter.limit() 单独配置。
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
)
