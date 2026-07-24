from __future__ import annotations

import asyncio
import contextlib
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.match import Match, MatchStatus
from app.services.audit_service import write_audit

logger = logging.getLogger(__name__)
CLEANUP_INTERVAL_SECONDS = 600


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def cleanup_expired_drafts_once() -> int:
    now = utcnow()
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Match).where(
                Match.status == MatchStatus.draft,
                Match.deleted_at.is_(None),
                Match.expires_at.is_not(None),
                Match.expires_at < now,
            )
        )
        expired_matches = result.scalars().all()
        if not expired_matches:
            return 0

        for match in expired_matches:
            match.deleted_at = now
            await write_audit(
                db,
                None,
                "match_draft_expired_deleted",
                team_id=match.team_id,
                actor_username="system",
                target_type="match",
                target_id=match.id,
                detail={
                    "expires_at": match.expires_at.isoformat() if match.expires_at else None,
                    "cleaned_at": now.isoformat(),
                },
            )

        await db.commit()
        logger.info("cleaned_up_expired_match_drafts count=%s", len(expired_matches))
        return len(expired_matches)


async def run_live_draft_cleanup_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await cleanup_expired_drafts_once()
        except Exception:
            logger.exception("live_draft_cleanup_failed")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=CLEANUP_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue


async def stop_cleanup_task(task: asyncio.Task | None, stop_event: asyncio.Event | None) -> None:
    if stop_event is not None:
        stop_event.set()
    if task is not None:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
