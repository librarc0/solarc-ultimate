FROM python:3.11-slim

WORKDIR /app

# Use a CN mirror first for better reliability on mainland cloud hosts.
RUN pip install uv --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --default-timeout=120 --retries 5 \
 || pip install uv --no-cache-dir --default-timeout=120 --retries 5

# 注意：构建上下文为项目根目录（./），Dockerfile 位于 ./backend/Dockerfile
COPY backend/pyproject.toml /app/
RUN uv pip install --system --no-cache .

# 复制 backend 源码
COPY backend/ /app/
# 复制 docs 文档（帮助手册、规则手册等），供 /api/v1/help-docs 接口使用
COPY docs/ /app/docs/

# SQLite data directory (overridden by named volume in production)
RUN mkdir -p /app/data

# run.py: runs alembic upgrade head then uvicorn
ENTRYPOINT ["python", "run.py"]

