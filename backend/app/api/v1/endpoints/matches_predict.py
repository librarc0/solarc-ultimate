"""Matches predict and auto-group endpoints."""
from __future__ import annotations

import itertools
import random
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_effective_team_id
from app.core.database import get_db
from app.models.match import TeamSettings
from app.models.player import Player
from app.rating_engine.engine import RatingEngine
from app.services.rating_service import _build_settings


class PredictRequest(BaseModel):
    team_a_ids: List[int]
    team_b_ids: List[int]


class PredictResponse(BaseModel):
    win_prob_a: float
    win_prob_b: float
    match_quality: float


class AutoGroupRequest(BaseModel):
    player_ids: List[int]


class AutoGroupResponse(BaseModel):
    team_a_ids: list[int]
    team_b_ids: list[int]
    match_quality: float
    win_prob_a: float


router = APIRouter()


async def _get_engine_for_team(db: AsyncSession, team_id: int) -> RatingEngine:
    """Load team settings and construct rating engine for prediction endpoints."""
    ts_result = await db.execute(
        select(TeamSettings)
        .where(TeamSettings.team_id == team_id)
        .order_by(TeamSettings.id.desc())
        .limit(1)
    )
    ts = ts_result.scalar_one_or_none()
    return RatingEngine(_build_settings(ts))


@router.post("/predict", response_model=PredictResponse)
async def predict_match(
    body: PredictRequest,
    db: AsyncSession = Depends(get_db),
    team_id: int = Depends(get_effective_team_id),
):
    """Estimate win probabilities and match quality for two candidate teams."""
    all_ids = list(set(body.team_a_ids) | set(body.team_b_ids))
    if not all_ids:
        raise HTTPException(status_code=400, detail="球员列表不能为空")

    players_result = await db.execute(select(Player).where(Player.id.in_(all_ids)))
    player_map: dict[int, Player] = {p.id: p for p in players_result.scalars().all()}

    engine = await _get_engine_for_team(db, team_id)
    model = engine._model

    def _ratings(ids: list[int]):
        return [
            model.rating(mu=player_map[pid].mu, sigma=player_map[pid].sigma)
            for pid in ids
            if pid in player_map
        ]

    ra = _ratings(body.team_a_ids)
    rb = _ratings(body.team_b_ids)
    if not ra or not rb:
        raise HTTPException(status_code=400, detail="球员数据不足，无法预测")

    win_probs: list[float] = model.predict_win([ra, rb])
    match_quality: float = float(model.predict_draw([ra, rb]))

    return PredictResponse(
        win_prob_a=round(win_probs[0], 4),
        win_prob_b=round(win_probs[1], 4),
        match_quality=round(match_quality, 4),
    )


@router.post("/auto_group", response_model=AutoGroupResponse)
async def auto_group(
    body: AutoGroupRequest,
    db: AsyncSession = Depends(get_db),
    team_id: int = Depends(get_effective_team_id),
):
    """Build two balanced teams with win-rate and gender-balance objectives."""
    if len(body.player_ids) < 2:
        raise HTTPException(status_code=400, detail="至少需要 2 名球员")

    players_result = await db.execute(select(Player).where(Player.id.in_(body.player_ids)))
    players: list[Player] = list(players_result.scalars().all())
    if not players:
        raise HTTPException(status_code=404, detail="未找到球员")

    engine = await _get_engine_for_team(db, team_id)
    model = engine._model
    players_by_id = {p.id: p for p in players}

    def _gender_gap(a_ids: list[int], b_ids: list[int]) -> int:
        a_m = sum(1 for pid in a_ids if players_by_id[pid].gender == "M")
        b_m = sum(1 for pid in b_ids if players_by_id[pid].gender == "M")
        a_f = sum(1 for pid in a_ids if players_by_id[pid].gender == "F")
        b_f = sum(1 for pid in b_ids if players_by_id[pid].gender == "F")
        return abs(a_m - b_m) + abs(a_f - b_f)

    def _predict(a_ids: list[int], b_ids: list[int]) -> tuple[float, float]:
        ra = [model.rating(mu=players_by_id[pid].mu, sigma=players_by_id[pid].sigma) for pid in a_ids]
        rb = [model.rating(mu=players_by_id[pid].mu, sigma=players_by_id[pid].sigma) for pid in b_ids]
        if not ra or not rb:
            return 0.5, 0.5
        win_probs = model.predict_win([ra, rb])
        quality = float(model.predict_draw([ra, rb]))
        return float(win_probs[0]), quality

    all_ids = [p.id for p in players]
    n = len(all_ids)
    size_a = (n + 1) // 2
    best_a: list[int] | None = None
    best_b: list[int] | None = None
    best_obj: tuple[float, float, float] | None = None

    if n <= 16:
        for combo in itertools.combinations(all_ids, size_a):
            a_ids = list(combo)
            combo_set = set(combo)
            b_ids = [pid for pid in all_ids if pid not in combo_set]
            win_a, quality = _predict(a_ids, b_ids)
            obj = (abs(win_a - 0.5), -quality, float(_gender_gap(a_ids, b_ids)))
            if best_obj is None or obj < best_obj:
                best_obj = obj
                best_a = a_ids
                best_b = b_ids
    else:
        shuffled = all_ids[:]
        random.shuffle(shuffled)
        best_a = shuffled[:size_a]
        best_b = shuffled[size_a:]
        win_a, quality = _predict(best_a, best_b)
        best_obj = (abs(win_a - 0.5), -quality, float(_gender_gap(best_a, best_b)))
        for _ in range(500):
            random.shuffle(shuffled)
            a_ids = shuffled[:size_a]
            b_ids = shuffled[size_a:]
            win_a, quality = _predict(a_ids, b_ids)
            obj = (abs(win_a - 0.5), -quality, float(_gender_gap(a_ids, b_ids)))
            if obj < best_obj:
                best_obj = obj
                best_a = a_ids[:]
                best_b = b_ids[:]

    if not best_a or not best_b:
        raise HTTPException(status_code=400, detail="智能分组失败，请重试")

    win_prob_a, match_quality = _predict(best_a, best_b)
    return AutoGroupResponse(
        team_a_ids=best_a,
        team_b_ids=best_b,
        match_quality=round(match_quality, 4),
        win_prob_a=round(win_prob_a, 4),
    )
