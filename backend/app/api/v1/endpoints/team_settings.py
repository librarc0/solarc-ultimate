"""/team settings and rerate endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_active_player, get_effective_team_id, require_owner, require_superadmin
from app.core.database import AsyncSessionLocal, get_db
from app.models.match import TeamSettings
from app.models.player import Player, PlayerStatus
from app.models.team import Team
from app.services.audit_service import build_change_detail, snapshot_fields, write_audit
from app.services.rating_service import rerate_team_history
from app.services.rating_replay import rerate_team_history_stream
from app.api.v1.endpoints.team_membership import TeamInfoResponse

router = APIRouter()


class TeamSettingsRead(BaseModel):
    team_id: int
    team: TeamInfoResponse | None = None
    alpha: float
    beta: float
    gamma: float
    defense_weight: float
    composite_ts_weight: float
    composite_perf_weight: float
    composite_attendance_weight: float
    turnover_penalty: float
    turnover_sigma_factor: float
    break_bonus_per_goal: float
    winner_floor_factor: float
    external_impact_multiplier: float
    external_opp_mu_min: float
    external_opp_mu_max: float
    external_opp_sigma: float
    openskill_mu: float
    openskill_sigma: float
    openskill_beta: float
    openskill_tau: float
    openskill_kappa: float
    openskill_margin: float
    openskill_limit_sigma: bool
    openskill_balance: bool
    chemistry_win_weight: float
    chemistry_combo_weight: float
    chemistry_decay_constant: float
    sigma_bonus_factor: float
    weight_cap: float
    universal_point_bonus: float
    block_mu_bonus: float
    consecutive_turnover_threshold: int
    consecutive_turnover_multiplier: float
    # MIP 最佳进步球员评分参数
    mip_weight_mu_delta: float
    mip_weight_slope: float
    mip_weight_half: float
    mip_weight_sigma: float
    mip_slope_lambda: float
    mip_min_matches: int
    # 综合战力：表现分场次置信衰减
    perf_confidence_decay: float
    updated_at: datetime


class TeamSettingsUpdate(BaseModel):
    alpha: float | None = Field(default=None, ge=0.0, le=2.0)
    beta: float | None = Field(default=None, ge=0.0, le=2.0)
    gamma: float | None = Field(default=None, ge=0.0, le=2.0)
    defense_weight: float | None = Field(default=None, ge=0.0, le=2.0)
    composite_ts_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    composite_perf_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    composite_attendance_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    turnover_penalty: float | None = Field(default=None, ge=0.0, le=2.0)
    turnover_sigma_factor: float | None = Field(default=None, ge=0.0, le=2.0)
    break_bonus_per_goal: float | None = Field(default=None, ge=0.0, le=2.0)
    winner_floor_factor: float | None = Field(default=None, ge=0.0, le=1.0)
    external_impact_multiplier: float | None = Field(default=None, ge=0.0, le=3.0)
    external_opp_mu_min: float | None = Field(default=None, ge=1.0, le=50.0)
    external_opp_mu_max: float | None = Field(default=None, ge=1.0, le=100.0)
    external_opp_sigma: float | None = Field(default=None, ge=1.0, le=20.0)
    openskill_mu: float | None = Field(default=None, ge=1.0, le=60.0)
    openskill_sigma: float | None = Field(default=None, ge=0.5, le=20.0)
    openskill_beta: float | None = Field(default=None, ge=0.1, le=20.0)
    openskill_tau: float | None = Field(default=None, ge=0.0, le=5.0)
    openskill_kappa: float | None = Field(default=None, ge=0.0, le=0.1)
    openskill_margin: float | None = Field(default=None, ge=0.0, le=20.0)
    openskill_limit_sigma: bool | None = None
    openskill_balance: bool | None = None
    chemistry_win_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    chemistry_combo_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    chemistry_decay_constant: float | None = Field(default=None, ge=1.0, le=50.0)
    sigma_bonus_factor: float | None = Field(default=None, ge=0.0, le=1.0)
    weight_cap: float | None = Field(default=None, ge=1.0, le=5.0)
    universal_point_bonus: float | None = Field(default=None, ge=0.0, le=5.0)
    block_mu_bonus: float | None = Field(default=None, ge=0.0, le=2.0)
    consecutive_turnover_threshold: int | None = Field(default=None, ge=1, le=20)
    consecutive_turnover_multiplier: float | None = Field(default=None, ge=1.0, le=5.0)
    # MIP 最佳进步球员评分参数
    mip_weight_mu_delta: float | None = Field(default=None, ge=0.0, le=1.0, description="MIP µ绝对增幅权重（首→末场净增量）")
    mip_weight_slope:    float | None = Field(default=None, ge=0.0, le=1.0, description="MIP 加权趋势斜率权重（指数衰减回归）")
    mip_weight_half:     float | None = Field(default=None, ge=0.0, le=1.0, description="MIP 后半程 vs 前半程均值差权重")
    mip_weight_sigma:    float | None = Field(default=None, ge=0.0, le=1.0, description="MIP σ 降幅（稳定性增长）权重")
    mip_slope_lambda:    float | None = Field(default=None, ge=0.01, le=2.0, description="MIP 指数衰减系数（越大越强调近期）")
    mip_min_matches:     int   | None = Field(default=None, ge=1, le=50, description="参与进步榜最少场次门槛")
    # 综合战力：表现分场次置信衰减
    perf_confidence_decay: float | None = Field(default=None, ge=1.0, le=50.0, description="表现分场次置信折扣系数 N；perf=50+(1-exp(-matches/N))*(raw-50)，越大需更多场次才能充分体现表现")


TRACKED_FIELDS = [
    "alpha", "beta", "gamma", "defense_weight",
    "composite_ts_weight", "composite_perf_weight", "composite_attendance_weight",
    "turnover_penalty", "turnover_sigma_factor", "break_bonus_per_goal", "winner_floor_factor",
    "external_impact_multiplier", "external_opp_mu_min", "external_opp_mu_max", "external_opp_sigma",
    "openskill_mu", "openskill_sigma", "openskill_beta", "openskill_tau", "openskill_kappa", "openskill_margin",
    "openskill_limit_sigma", "openskill_balance",
    "chemistry_win_weight", "chemistry_combo_weight", "chemistry_decay_constant",
    "sigma_bonus_factor", "weight_cap", "universal_point_bonus", "block_mu_bonus",
    "consecutive_turnover_threshold", "consecutive_turnover_multiplier",
    "mip_weight_mu_delta", "mip_weight_slope", "mip_weight_half",
    "mip_weight_sigma", "mip_slope_lambda", "mip_min_matches",
    "perf_confidence_decay",
]


async def _build_team_settings_read(db: AsyncSession, ts: TeamSettings, current_player: Player) -> TeamSettingsRead:
    team = (await db.execute(select(Team).where(Team.id == ts.team_id))).scalar_one_or_none()
    member_count = 0
    if team:
        count_result = await db.execute(
            select(func.count()).select_from(Player).where(
                Player.team_id == team.id,
                Player.status == PlayerStatus.active,
            )
        )
        member_count = count_result.scalar() or 0

    return TeamSettingsRead(
        team_id=ts.team_id,
        team=(
            TeamInfoResponse(
                id=team.id,
                name=team.name,
                logo_url=team.logo_url,
                member_count=member_count,
                my_status=current_player.status.value,
            )
            if team
            else None
        ),
        alpha=ts.alpha,
        beta=ts.beta,
        gamma=ts.gamma,
        defense_weight=ts.defense_weight,
        composite_ts_weight=ts.composite_ts_weight,
        composite_perf_weight=ts.composite_perf_weight,
        composite_attendance_weight=ts.composite_attendance_weight,
        turnover_penalty=ts.turnover_penalty,
        turnover_sigma_factor=ts.turnover_sigma_factor,
        break_bonus_per_goal=ts.break_bonus_per_goal,
        winner_floor_factor=ts.winner_floor_factor,
        external_impact_multiplier=ts.external_impact_multiplier,
        external_opp_mu_min=ts.external_opp_mu_min,
        external_opp_mu_max=ts.external_opp_mu_max,
        external_opp_sigma=ts.external_opp_sigma,
        openskill_mu=ts.openskill_mu,
        openskill_sigma=ts.openskill_sigma,
        openskill_beta=ts.openskill_beta,
        openskill_tau=ts.openskill_tau,
        openskill_kappa=ts.openskill_kappa,
        openskill_margin=ts.openskill_margin,
        openskill_limit_sigma=ts.openskill_limit_sigma,
        openskill_balance=ts.openskill_balance,
        chemistry_win_weight=ts.chemistry_win_weight,
        chemistry_combo_weight=ts.chemistry_combo_weight,
        chemistry_decay_constant=ts.chemistry_decay_constant,
        sigma_bonus_factor=ts.sigma_bonus_factor,
        weight_cap=ts.weight_cap,
        universal_point_bonus=ts.universal_point_bonus,
        block_mu_bonus=ts.block_mu_bonus,
        consecutive_turnover_threshold=ts.consecutive_turnover_threshold,
        consecutive_turnover_multiplier=ts.consecutive_turnover_multiplier,
        mip_weight_mu_delta=ts.mip_weight_mu_delta,
        mip_weight_slope=ts.mip_weight_slope,
        mip_weight_half=ts.mip_weight_half,
        mip_weight_sigma=ts.mip_weight_sigma,
        mip_slope_lambda=ts.mip_slope_lambda,
        mip_min_matches=ts.mip_min_matches,
        perf_confidence_decay=ts.perf_confidence_decay,
        updated_at=ts.updated_at,
    )


@router.get("/settings", response_model=TeamSettingsRead)
async def get_team_settings(
    db: AsyncSession = Depends(get_db),
    effective_team_id: int = Depends(get_effective_team_id),
    current_player: Player = Depends(get_current_active_player),
):
    ts = (await db.execute(select(TeamSettings).where(TeamSettings.team_id == effective_team_id))).scalar_one_or_none()
    if not ts:
        ts = TeamSettings(team_id=effective_team_id, updated_by=current_player.id)
        db.add(ts)
        await db.commit()
        await db.refresh(ts)
    return await _build_team_settings_read(db, ts, current_player)


@router.put("/settings", response_model=TeamSettingsRead)
async def update_team_settings(
    body: TeamSettingsUpdate,
    db: AsyncSession = Depends(get_db),
    owner: Player = Depends(require_owner),
    effective_team_id: int = Depends(get_effective_team_id),
):
    ts = (await db.execute(select(TeamSettings).where(TeamSettings.team_id == effective_team_id))).scalar_one_or_none()
    if not ts:
        ts = TeamSettings(team_id=effective_team_id, updated_by=owner.id)
        db.add(ts)

    before_settings = snapshot_fields(ts, TRACKED_FIELDS)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(ts, field, value)

    ts.updated_by = owner.id
    ts.updated_at = datetime.now(timezone.utc)
    await write_audit(
        db,
        owner,
        "settings_updated",
        team_id=effective_team_id,
        target_type="team",
        target_id=effective_team_id,
        detail=build_change_detail(before=before_settings, after=snapshot_fields(ts, TRACKED_FIELDS)),
    )
    await db.commit()
    await db.refresh(ts)
    return await _build_team_settings_read(db, ts, owner)


@router.post("/settings/reset", response_model=TeamSettingsRead)
async def reset_team_settings(
    db: AsyncSession = Depends(get_db),
    owner: Player = Depends(require_owner),
    effective_team_id: int = Depends(get_effective_team_id),
):
    ts = (await db.execute(select(TeamSettings).where(TeamSettings.team_id == effective_team_id))).scalar_one_or_none()
    before_settings = snapshot_fields(ts, TRACKED_FIELDS) if ts else None
    if not ts:
        ts = TeamSettings(team_id=effective_team_id, updated_by=owner.id)
        db.add(ts)
    else:
        ts.alpha = 0.3
        ts.beta = 0.6
        ts.gamma = 0.4
        ts.defense_weight = 0.1
        ts.composite_ts_weight = 0.85
        ts.composite_perf_weight = 0.15
        ts.composite_attendance_weight = 0.0
        ts.turnover_penalty = 0.2
        ts.turnover_sigma_factor = 0.3
        ts.break_bonus_per_goal = 0.1
        ts.winner_floor_factor = 0.1
        ts.external_impact_multiplier = 1.0
        ts.external_opp_mu_min = 15.0
        ts.external_opp_mu_max = 50.0
        ts.external_opp_sigma = 6.0
        ts.openskill_mu = 25.0
        ts.openskill_sigma = 25.0 / 3.0
        ts.openskill_beta = 25.0 / 6.0
        ts.openskill_tau = 25.0 / 300.0
        ts.openskill_kappa = 0.0001
        ts.openskill_margin = 0.0
        ts.openskill_limit_sigma = False
        ts.openskill_balance = True
        ts.chemistry_win_weight = 0.7
        ts.chemistry_combo_weight = 0.3
        ts.chemistry_decay_constant = 8.0
        ts.sigma_bonus_factor = 0.15
        ts.weight_cap = 2.0
        ts.universal_point_bonus = 0.5
        ts.block_mu_bonus = 0.05
        ts.consecutive_turnover_threshold = 3
        ts.consecutive_turnover_multiplier = 1.5
        ts.mip_weight_mu_delta = 0.40
        ts.mip_weight_slope = 0.30
        ts.mip_weight_half = 0.20
        ts.mip_weight_sigma = 0.10
        ts.mip_slope_lambda = 0.15
        ts.mip_min_matches = 6
        ts.updated_by = owner.id
        ts.updated_at = datetime.now(timezone.utc)

    await write_audit(
        db,
        owner,
        "settings_reset",
        team_id=effective_team_id,
        target_type="team",
        target_id=effective_team_id,
        detail=build_change_detail(before=before_settings, after=snapshot_fields(ts, TRACKED_FIELDS)),
    )
    await db.commit()
    await db.refresh(ts)
    return await _build_team_settings_read(db, ts, owner)


@router.post("/{team_id}/rerate", status_code=200)
async def rerate_team(
    team_id: int,
    db: AsyncSession = Depends(get_db),
    sa: Player = Depends(require_superadmin),
):
    team = (await db.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="队伍不存在")
    if not team.is_active:
        raise HTTPException(status_code=400, detail="队伍已停用")

    result = await rerate_team_history(db, team_id=team_id, operated_by=sa.id)
    await write_audit(
        db,
        sa,
        "team_rerated",
        team_id=team_id,
        target_type="team",
        target_id=team_id,
        detail=result,
    )
    await db.commit()
    return {"message": "重算完成", **result}


@router.get("/{team_id}/rerate-stream")
async def rerate_team_stream(
    team_id: int,
    sa: Player = Depends(require_superadmin),
):
    """SSE 流式重算，实时推送进度百分比。"""
    sa_id = sa.id  # capture before dependency context closes

    async def event_generator():
        import json
        async with AsyncSessionLocal() as session:
            team = (await session.execute(select(Team).where(Team.id == team_id))).scalar_one_or_none()
            if not team:
                yield f"data: {json.dumps({'type': 'error', 'message': '队伍不存在'})}\n\n"
                return
            if not team.is_active:
                yield f"data: {json.dumps({'type': 'error', 'message': '队伍已停用'})}\n\n"
                return
            try:
                async for chunk in rerate_team_history_stream(session, team_id=team_id, operated_by=sa_id):
                    yield chunk
                # write audit after stream completes
                result_data = {}  # audit detail is minimal for streaming
                await write_audit(
                    session,
                    sa,
                    "team_rerated",
                    team_id=team_id,
                    target_type="team",
                    target_id=team_id,
                    detail=result_data,
                )
                await session.commit()
            except Exception as exc:
                yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
