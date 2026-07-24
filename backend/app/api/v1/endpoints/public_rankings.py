"""公开排行榜接口（无需认证）"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.models.team_ranking import ExternalTeam, RankingSeason
from app.models.player import Player
from app.schemas.team_ranking import (
    ExternalTeamListItem,
    ExternalTeamDetail,
    ExternalTeamForMatch,
    SeasonOut,
)
from app.services.ranking_service import map_score_to_strength, get_latest_season_id, calibrate_opponent

router = APIRouter()


# ────────────────────────────────────────
# 赛季列表（公开）
# ────────────────────────────────────────

@router.get("/seasons", response_model=list[SeasonOut])
async def list_seasons(response: Response, db: AsyncSession = Depends(get_db)):
    """获取所有赛季列表（按年份 + 创建时间倒序）"""
    response.headers["Cache-Control"] = "no-store"  # 赛季列表变更后必须立即可见
    result = await db.execute(
        select(RankingSeason).order_by(
            RankingSeason.year.desc(),
            RankingSeason.created_at.desc(),
        )
    )
    return [SeasonOut.model_validate(s) for s in result.scalars().all()]


# ────────────────────────────────────────
# 队伍榜单（指定赛季）
# ────────────────────────────────────────

@router.get("/team-rankings", response_model=dict)
async def list_team_rankings(
    season_id: Optional[int] = Query(None, description="赛季 ID，默认最新赛季"),
    search: Optional[str] = Query(None, max_length=50, description="队伍名搜索"),
    sort_by: str = Query("total_score", description="排序字段: total_score | avg_score | tournament_count | win_rate"),
    order: str = Query("desc", description="排序方向: asc | desc"),
    province_filter: Optional[str] = Query(None, max_length=30, description="省份/地区 ISO 3166-2 代码过滤，e.g. CN-SH"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    response: Response = None,
):
    """获取队伍排行榜列表"""
    if season_id is None:
        season_id = await get_latest_season_id(db)
    if season_id is None:
        return {"total": 0, "page": page, "page_size": page_size, "items": [], "season_id": None}
    if response is not None:
        response.headers["Cache-Control"] = "private, no-cache"  # 导入后立即刷新

    allowed_sorts = {"total_score", "avg_score", "tournament_count", "win_rate"}
    if sort_by not in allowed_sorts:
        sort_by = "total_score"

    sort_col = getattr(ExternalTeam, sort_by)
    sort_expr = sort_col.desc() if order != "asc" else sort_col.asc()

    query = select(ExternalTeam).where(ExternalTeam.season_id == season_id)
    if search:
        query = query.where(ExternalTeam.name.ilike(f"%{search}%"))
    if province_filter:
        # 支持省级匹配：province_filter=CN-GD 同时匹配 province=CN-GD 和 city=CN-GD-GZ 等
        query = query.where(
            (ExternalTeam.province == province_filter) |
            ExternalTeam.city.like(f"{province_filter}%")
        )
    query = query.order_by(sort_expr)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar_one()

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    teams = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "season_id": season_id,
        "items": [ExternalTeamListItem.model_validate(t) for t in teams],
    }


@router.get("/team-rankings/for-match", response_model=list[ExternalTeamForMatch])
async def get_teams_for_match(
    season_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """外战录入专用：精简列表（name + total_score + rank）"""
    if season_id is None:
        season_id = await get_latest_season_id(db)
    if season_id is None:
        return []

    query = select(ExternalTeam).where(ExternalTeam.season_id == season_id).order_by(ExternalTeam.rank.asc())
    if search:
        query = query.where(ExternalTeam.name.ilike(f"%{search}%"))
    result = await db.execute(query)
    return [ExternalTeamForMatch.model_validate(t) for t in result.scalars().all()]


@router.get("/team-rankings/compare", response_model=list[ExternalTeamDetail])
async def compare_teams(
    teams: str = Query(..., description="逗号分隔的队伍名，最多2支"),
    season_ids: Optional[str] = Query(None, description="逗号分隔的赛季ID，与 teams 一一对应；不传则均使用最新赛季"),
    db: AsyncSession = Depends(get_db),
):
    """对比两支队伍（可跨赛季）。season_ids 可以不同以实现跨赛季对比。"""
    team_names = [n.strip() for n in teams.split(",") if n.strip()][:2]
    if not team_names:
        raise HTTPException(status_code=400, detail="请提供至少一支队伍名")

    # 解析 season_ids
    latest = await get_latest_season_id(db)
    if season_ids:
        raw = [s.strip() for s in season_ids.split(",")]
        sid_list: list[int] = []
        for r in raw[:2]:
            try:
                sid_list.append(int(r))
            except ValueError:
                sid_list.append(latest or 0)
        while len(sid_list) < len(team_names):
            sid_list.append(latest or 0)
    else:
        sid_list = [latest or 0] * len(team_names)

    found: list[ExternalTeamDetail] = []
    for name, sid in zip(team_names, sid_list):
        result = await db.execute(
            select(ExternalTeam)
            .where(ExternalTeam.name == name, ExternalTeam.season_id == sid)
            .options(selectinload(ExternalTeam.tournament_records))
        )
        team = result.scalar_one_or_none()
        if team:
            found.append(ExternalTeamDetail.model_validate(team))
    return found


@router.get("/team-rankings/{team_name}", response_model=ExternalTeamDetail)
async def get_team_detail(
    team_name: str,
    season_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取单支队伍详情（含赛事历史，按 month 倒序）"""
    if season_id is None:
        season_id = await get_latest_season_id(db)

    result = await db.execute(
        select(ExternalTeam)
        .where(ExternalTeam.name == team_name, ExternalTeam.season_id == season_id)
        .options(selectinload(ExternalTeam.tournament_records))
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="队伍不存在")

    team.tournament_records.sort(key=lambda r: r.month, reverse=True)
    return ExternalTeamDetail.model_validate(team)


@router.get("/team-rankings-strength/{team_name}", response_model=dict)
async def get_team_strength(
    team_name: str,
    season_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """获取队伍在排行榜中映射的对手强度（1.0-10.0）"""
    if season_id is None:
        season_id = await get_latest_season_id(db)

    stats = await db.execute(
        select(func.min(ExternalTeam.total_score), func.max(ExternalTeam.total_score))
        .where(ExternalTeam.season_id == season_id)
    )
    min_score, max_score = stats.one()

    result = await db.execute(
        select(ExternalTeam).where(
            ExternalTeam.name == team_name,
            ExternalTeam.season_id == season_id,
        )
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="队伍不存在")

    strength = map_score_to_strength(team.total_score, min_score or 0, max_score or 0)
    return {
        "name": team_name,
        "total_score": team.total_score,
        "strength": strength,
        "rank": team.rank,
        "season_id": season_id,
    }


@router.get("/team-rankings-strength-v2/{team_name}", response_model=dict)
async def get_team_strength_v2(
    team_name: str,
    team_id: int = Query(..., description="本队 team_id，用于计算队内平均 mu"),
    season_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    v2 自适应校准：基于本队平均 mu 和对手排名百分位，
    返回 calibrated_mu / calibrated_sigma 以及兼容的 strength 1-10 值。
    """
    if season_id is None:
        season_id = await get_latest_season_id(db)

    # 获取本队玩家平均 mu
    player_stats = await db.execute(
        select(func.avg(Player.mu)).where(
            Player.team_id == team_id,
            Player.status == "active",
        )
    )
    team_avg_mu = player_stats.scalar() or 25.0

    # 获取联盟中的队伍总数
    total_teams_result = await db.execute(
        select(func.count(ExternalTeam.id)).where(ExternalTeam.season_id == season_id)
    )
    total_teams = total_teams_result.scalar() or 1

    # 积分范围（用于兼容 strength 1-10）
    stats = await db.execute(
        select(func.min(ExternalTeam.total_score), func.max(ExternalTeam.total_score))
        .where(ExternalTeam.season_id == season_id)
    )
    min_score, max_score = stats.one()

    result = await db.execute(
        select(ExternalTeam).where(
            ExternalTeam.name == team_name,
            ExternalTeam.season_id == season_id,
        )
    )
    team = result.scalar_one_or_none()
    if not team:
        raise HTTPException(status_code=404, detail="队伍不存在")

    # 兼容旧 strength
    strength = map_score_to_strength(team.total_score, min_score or 0, max_score or 0)

    # v2 校准
    tournament_count = getattr(team, 'tournament_count', 0) or 0
    calibrated_mu, calibrated_sigma = calibrate_opponent(
        opponent_rank=team.rank or 1,
        total_teams=total_teams,
        team_avg_mu=team_avg_mu,
        opponent_tournament_count=tournament_count,
    )

    return {
        "name": team_name,
        "total_score": team.total_score,
        "strength": strength,
        "rank": team.rank,
        "season_id": season_id,
        "calibrated_mu": calibrated_mu,
        "calibrated_sigma": calibrated_sigma,
        "team_id": team.id,
    }
