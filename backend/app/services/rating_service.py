"""评分服务兼容层。

对外保留既有导出路径，内部实现已拆分到独立模块。
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match, MatchPlayer, TeamSettings
from app.rating_engine.engine import EngineSettings
from app.services.rating_apply import apply_ratings as apply_ratings
from app.services.rating_replay import rerate_team_history as rerate_team_history
from app.services.rating_settings import build_engine_settings


def _build_settings(ts: TeamSettings | None) -> EngineSettings:
    """兼容旧调用点（含测试与预测接口）。"""
    return build_engine_settings(ts)


__all__ = [
    "apply_ratings",
    "rerate_team_history",
    "_build_settings",
    "AsyncSession",
    "Match",
    "MatchPlayer",
]

