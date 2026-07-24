"""T032: /matches 路由聚合入口。"""

from datetime import datetime, timezone

from app.api.v1.endpoints.matches_core import router as core_router
from app.api.v1.endpoints.matches_drafts import LOCK_LEASE_SECONDS, router as drafts_router
from app.api.v1.endpoints.matches_predict import router as predict_router

router = core_router
__all__ = ["LOCK_LEASE_SECONDS", "_utcnow", "router"]


def _utcnow() -> datetime:
	"""Compatibility hook used by tests to monkeypatch match time."""
	return datetime.now(timezone.utc)


router.include_router(drafts_router)
router.include_router(predict_router)


