"""审计日志查询端点（仅超级管理员）"""
from __future__ import annotations

from datetime import date as date_cls, datetime, time, timedelta, timezone
import json
import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import require_superadmin
from app.core.database import get_db
from app.models.audit import AuditLog
from app.models.player import Player

router = APIRouter()


@router.get("")
async def list_audit_logs(
    team_id: int | None = Query(None),
    action: str | None = Query(None),
    log_date: str | None = Query(None, description="按北京时间日期筛选，格式 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: Player = Depends(require_superadmin),
):
    """
    查询操作审计日志（仅超级管理员可访问）。

    - team_id：按队伍筛选；不传则返回全部
    - action：精确匹配操作类型，如 match_approved、settings_updated
    - 按时间倒序返回，支持分页
    - 返回格式: { items: [...], total: int, total_pages: int, page: int }
    """
    base_q = select(AuditLog)
    if team_id is not None:
        base_q = base_q.where(AuditLog.team_id == team_id)
    if action:
        base_q = base_q.where(AuditLog.action == action)
    if log_date:
        try:
            day = date_cls.fromisoformat(log_date)
        except ValueError:
            return {"items": [], "total": 0, "total_pages": 1, "page": page}

        beijing_tz = timezone(timedelta(hours=8))
        start_beijing = datetime.combine(day, time.min, tzinfo=beijing_tz)
        end_beijing = start_beijing + timedelta(days=1)
        start_utc = start_beijing.astimezone(timezone.utc)
        end_utc = end_beijing.astimezone(timezone.utc)
        base_q = base_q.where(AuditLog.created_at >= start_utc, AuditLog.created_at < end_utc)

    # 计算总数
    count_result = await db.execute(select(func.count()).select_from(base_q.subquery()))
    total = count_result.scalar_one()
    total_pages = max(1, math.ceil(total / page_size))

    q = base_q.order_by(AuditLog.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(q)
    logs = result.scalars().all()
    items = [
        {
            "id": log.id,
            "team_id": log.team_id,
            "actor_username": log.actor_username,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "detail": json.loads(log.detail) if log.detail else None,
            "created_at": log.created_at.isoformat(),
        }
        for log in logs
    ]
    return {"items": items, "total": total, "total_pages": total_pages, "page": page}
