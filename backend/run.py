"""Unified backend entrypoint: backup DB + migrate + schema check + uvicorn."""

from __future__ import annotations

import argparse
import re
import shutil
from datetime import datetime
from pathlib import Path
import subprocess
import sys

import uvicorn


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start backend with migration checks")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", help="Enable uvicorn reload mode")
    return parser.parse_args()


def run_or_exit(cmd: list[str], cwd: Path, fail_message: str) -> None:
    result = subprocess.run(cmd, cwd=str(cwd))
    if result.returncode != 0:
        print(fail_message, file=sys.stderr, flush=True)
        sys.exit(result.returncode)


def backup_database(project_root: Path, keep: int = 7) -> None:
    """启动前自动备份 SQLite 数据库，保留最近 keep 份，超出部分按时间从旧到新删除。"""
    db_path = project_root / "data" / "eaglespower.db"
    if not db_path.exists():
        print("[run.py] No database found, skipping backup.", flush=True)
        return

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = project_root / "data" / f"eaglespower.db.bak-{timestamp}"
    shutil.copy2(db_path, backup_path)
    print(f"[run.py] Database backed up → {backup_path.name}", flush=True)

    # 轮转：删除最旧的备份，只保留最近 keep 份
    bak_pattern = re.compile(r"eaglespower\.db\.bak-\d{8}-\d{6}$")
    all_baks = sorted(
        [f for f in (project_root / "data").iterdir() if bak_pattern.match(f.name)],
        key=lambda f: f.name,  # 文件名含时间戳，字典序 = 时间序
    )
    for old_bak in all_baks[:-keep]:
        old_bak.unlink()
        print(f"[run.py] Rotated old backup: {old_bak.name}", flush=True)


def main() -> None:
    args = parse_args()
    project_root = Path(__file__).resolve().parent

    # 1. 启动前自动备份（保留最近 7 份）
    backup_database(project_root)

    # 2. Alembic 迁移
    print("[run.py] Running Alembic migrations...", flush=True)
    run_or_exit(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=project_root,
        fail_message="[run.py] Migration failed, aborting.",
    )

    # 3. Schema 兼容性检查
    print("[run.py] Verifying schema compatibility...", flush=True)
    run_or_exit(
        [sys.executable, "-m", "scripts.verify_schema_compatibility"],
        cwd=project_root,
        fail_message="[run.py] Schema compatibility check failed, aborting.",
    )

    print("[run.py] Migrations complete. Starting uvicorn...", flush=True)
    reload_dirs = [str(project_root / "app")] if args.reload else None
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=reload_dirs,
    )


if __name__ == "__main__":
    main()
