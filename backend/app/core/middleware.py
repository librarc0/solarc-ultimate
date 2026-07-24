"""T087: 结构化日志中间件 — 注入 request_id，错误使用英文格式"""
import logging
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("eaglespower")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        response = await call_next(request)

        if response.status_code >= 500:
            logger.error(
                "[ERROR] [Middleware::RequestLogging] %s %s → %d (request_id=%s)",
                request.method,
                request.url.path,
                response.status_code,
                request_id,
            )
        elif response.status_code == 429:
            logger.warning(
                "[RATELIMIT] [Middleware::RequestLogging] %s %s \u2192 429 (request_id=%s, ip=%s)",
                request.method,
                request.url.path,
                request_id,
                request.client.host if request.client else "unknown",
            )
        elif response.status_code >= 400:
            logger.warning(
                "[WARN]  [Middleware::RequestLogging] %s %s → %d (request_id=%s)",
                request.method,
                request.url.path,
                response.status_code,
                request_id,
            )
        else:
            logger.info(
                "[INFO]  [Middleware::RequestLogging] %s %s → %d (request_id=%s)",
                request.method,
                request.url.path,
                response.status_code,
                request_id,
            )

        response.headers["X-Request-Id"] = request_id
        return response
