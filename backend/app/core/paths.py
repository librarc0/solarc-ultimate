"""项目路径约定（集中管理，避免各处手写相对路径导致不一致）"""

from __future__ import annotations

import os


def get_backend_root_dir() -> str:
    """返回 backend/ 目录的绝对路径。"""
    # 本文件位于 backend/app/core/paths.py
    return os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def get_uploads_dir() -> str:
    """返回上传目录（头像/队徽等）的绝对路径，并确保目录存在。"""
    uploads_dir = os.path.join(get_backend_root_dir(), "data", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    return uploads_dir


def get_docs_dir() -> str:
    """返回项目 docs/doc 目录绝对路径。

    路径策略（三套环境优先级）：
    - Docker 部署（新镜像）：/app/docs/doc（Dockerfile: COPY docs/ /app/docs/）
    - NAS 旧镜像兼容：volume 挂载到 /docs/doc，下次重新构建镜像后此条可移除
    - 本地开发：backend_root = .../backend，向上一级到项目根
    """
    backend_root = get_backend_root_dir()
    # Docker 新镜像: /app/docs/doc
    docker_path = os.path.join(backend_root, "docs", "doc")
    if os.path.isdir(docker_path):
        return docker_path
    # NAS 旧镜像兼容路径：volume 挂载到 /docs/doc
    if os.path.isdir("/docs/doc"):
        return "/docs/doc"
    # 本地开发：backend_root = .../backend，向上一级到项目根
    project_root = os.path.dirname(backend_root)
    return os.path.join(project_root, "docs", "doc")

