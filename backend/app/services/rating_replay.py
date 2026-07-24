"""Historical rerating replay orchestration."""
from __future__ import annotations

import json
from typing import AsyncGenerator

from sqlalchemy import delete as sa_delete
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match, MatchPlayer, MatchStatus, PlayerChemistry, RatingHistory
from app.models.player import Player
from app.rating_engine.engine import CONSERVATIVE_BASELINE, DEFAULT_MU, DEFAULT_SIGMA
from app.services.rating_apply import apply_ratings


async def rerate_team_history(
    db: AsyncSession,
    team_id: int,
    operated_by: int,
) -> dict:
    """
    按当前 TeamSettings 对某队所有已审批比赛进行历史重算。
    """
    match_rows = list(
        (await db.execute(select(Match.id).where(Match.team_id == team_id))).scalars()
    )
    match_ids = [int(mid) for mid in match_rows]

    if match_ids:
        await db.execute(sa_delete(RatingHistory).where(RatingHistory.match_id.in_(match_ids)))

    await db.execute(sa_delete(PlayerChemistry).where(PlayerChemistry.team_id == team_id))

    await db.execute(
        update(Player)
        .where(Player.team_id == team_id)
        .values(
            mu=DEFAULT_MU,
            sigma=DEFAULT_SIGMA,
            conservative_rating=CONSERVATIVE_BASELINE,
            total_goals=0,
            total_assists=0,
            total_defenses=0,
            total_plus_minus=0,
            total_turnovers=0,
            total_matches=0,
            total_wins=0,
        )
    )

    replay_q = select(Match).where(
        Match.team_id == team_id,
        Match.status == MatchStatus.approved,
    ).order_by(Match.match_date.asc(), Match.id.asc())
    matches = list((await db.execute(replay_q)).scalars())

    replayed = 0
    affected_players: set[int] = set()

    for m in matches:
        mp_result = await db.execute(select(MatchPlayer).where(MatchPlayer.match_id == m.id))
        participants = list(mp_result.scalars())
        if not participants:
            continue

        pids = [mp.player_id for mp in participants]
        players_result = await db.execute(select(Player).where(Player.id.in_(pids)))
        player_map = {p.id: p for p in players_result.scalars()}

        for mp in participants:
            p = player_map.get(mp.player_id)
            if not p:
                continue
            mp.mu_before = p.mu
            mp.sigma_before = p.sigma
            mp.mu_after = None
            mp.sigma_after = None
            mp.is_winner = None

        await db.flush()

        await apply_ratings(db, m, operated_by=operated_by, participants=participants, reason="rerate")
        replayed += 1
        affected_players.update(pids)

    await db.commit()
    return {
        "team_id": team_id,
        "matches_total": len(match_ids),
        "matches_replayed": replayed,
        "players_reset": len(
            list((await db.execute(select(Player.id).where(Player.team_id == team_id))).scalars())
        ),
        "players_affected": len(affected_players),
    }


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def rerate_team_history_stream(
    db: AsyncSession,
    team_id: int,
    operated_by: int,
) -> AsyncGenerator[str, None]:
    """流式历史重算，通过 SSE 事件发送进度。"""
    yield _sse({"type": "start", "message": "正在重置球员数据…", "progress": 0})

    match_rows = list(
        (await db.execute(select(Match.id).where(Match.team_id == team_id))).scalars()
    )
    match_ids = [int(mid) for mid in match_rows]

    if match_ids:
        await db.execute(sa_delete(RatingHistory).where(RatingHistory.match_id.in_(match_ids)))

    await db.execute(sa_delete(PlayerChemistry).where(PlayerChemistry.team_id == team_id))

    await db.execute(
        update(Player)
        .where(Player.team_id == team_id)
        .values(
            mu=DEFAULT_MU,
            sigma=DEFAULT_SIGMA,
            conservative_rating=CONSERVATIVE_BASELINE,
            total_goals=0,
            total_assists=0,
            total_defenses=0,
            total_plus_minus=0,
            total_turnovers=0,
            total_matches=0,
            total_wins=0,
        )
    )

    replay_q = select(Match).where(
        Match.team_id == team_id,
        Match.status == MatchStatus.approved,
    ).order_by(Match.match_date.asc(), Match.id.asc())
    matches = list((await db.execute(replay_q)).scalars())
    total = len(matches)

    yield _sse({"type": "progress", "message": f"共 {total} 场已审批比赛，开始重放…", "progress": 2, "total": total, "done": 0})

    replayed = 0
    affected_players: set[int] = set()

    for idx, m in enumerate(matches):
        mp_result = await db.execute(select(MatchPlayer).where(MatchPlayer.match_id == m.id))
        participants = list(mp_result.scalars())
        if not participants:
            continue

        pids = [mp.player_id for mp in participants]
        players_result = await db.execute(select(Player).where(Player.id.in_(pids)))
        player_map = {p.id: p for p in players_result.scalars()}

        for mp in participants:
            p = player_map.get(mp.player_id)
            if not p:
                continue
            mp.mu_before = p.mu
            mp.sigma_before = p.sigma
            mp.mu_after = None
            mp.sigma_after = None
            mp.is_winner = None

        await db.flush()
        await apply_ratings(db, m, operated_by=operated_by, participants=participants, reason="rerate")
        replayed += 1
        affected_players.update(pids)

        progress = 2 + int(95 * (idx + 1) / max(total, 1))
        yield _sse({
            "type": "progress",
            "message": f"重放第 {idx + 1}/{total} 场",
            "progress": progress,
            "total": total,
            "done": replayed,
        })

    await db.commit()

    players_reset = len(
        list((await db.execute(select(Player.id).where(Player.team_id == team_id))).scalars())
    )
    result = {
        "team_id": team_id,
        "matches_total": len(match_ids),
        "matches_replayed": replayed,
        "players_reset": players_reset,
        "players_affected": len(affected_players),
    }
    yield _sse({"type": "done", "message": f"重算完成：重放 {replayed} 场比赛", "progress": 100, **result})
