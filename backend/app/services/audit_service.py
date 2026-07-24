"""审计日志辅助函数：在任意 async 上下文中快速写入一条操作记录"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.player import Player


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize_value(item) for item in value]
    return value


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[:1] + "***"
    else:
        masked_local = local[:1] + "***" + local[-1:]
    return f"{masked_local}@{domain}"


def snapshot_fields(obj: Any, fields: list[str]) -> dict[str, Any]:
    return {field: _serialize_value(getattr(obj, field)) for field in fields}


def build_change_detail(
    *,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    detail: dict[str, Any] = {}
    if before is not None:
        detail["before"] = _serialize_value(before)
    if after is not None:
        detail["after"] = _serialize_value(after)
    if extra:
        detail.update(_serialize_value(extra))
    return detail or None


async def write_audit(
    db: AsyncSession,
    actor: Player | None,
    action: str,
    *,
    actor_username: str | None = None,
    team_id: int | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """
    写入一条审计日志，不抛出异常（静默失败，不影响主流程）。

    Usage::

        await write_audit(db, admin, "match_approved",
                         team_id=match.team_id, target_type="match", target_id=match.id,
                         detail={"score": f"{match.team_a_score}-{match.team_b_score}"})
    """
    try:
        log = AuditLog(
            team_id=team_id,
            actor_id=actor.id if actor else None,
            actor_username=actor_username or (actor.display_name or actor.username if actor else "system"),
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=json.dumps(_serialize_value(detail), ensure_ascii=False) if detail else None,
        )
        db.add(log)
        # 不单独 commit，依赖调用方的 commit，以保持事务一致性
    except Exception:
        pass  # 日志写入失败不能影响主业务
