"""T043: /rankings 端点 — 排行榜 + 球员面板"""
import math
from datetime import date as date_type, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_active_player, get_effective_team_id
from app.core.database import get_db
from app.models.match import Match, MatchPlayer, MatchStatus, PlayerChemistry, RatingHistory, TeamSettings
from app.models.player import Player, PlayerStatus, UserRole
from app.models.schedule import (
    AttendanceStatus,
    ScheduleAttendance,
    ScheduleEvent,
    ScheduleEventStatus,
    ScheduleEventType,
)
from app.schemas.player import (
    ChemistryItem,
    ChemistryResponse,
    PlayerPanelResponse,
    RankingItem,
    RankingResponse,
)

router = APIRouter()

# ── 综合战力分辅助计算 ────────────────────────────────────────────────────────────

def _enum_value(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _match_confidence(total_matches: int, ts: TeamSettings | None) -> float:
    """场次置信度：场次越少，越向基准收敛。"""
    if total_matches <= 0:
        return 0.0
    N = ts.perf_confidence_decay if ts else 8.0
    return 1.0 - math.exp(-total_matches / N)


def _compute_perf_score(p: Player, ts: TeamSettings | None) -> float:
    """每场表现分，以 50 为基准，使用 TeamSettings 系数加权。

    公式: 50 + confidence * (raw_perf - 50)
      raw_perf  = 50 + (beta*goals_pg + gamma*assists_pg + dw*defenses_pg - tp*to_pg) * 10
      confidence = 1 - exp(-total_matches / N)   [N = perf_confidence_decay, 默认 8]

    其中 defenses_pg = total_defenses / total_matches（场均防守次数，已取 max(x,0) 确保非负）。
    场次越少，分数向基准 50.0 收敛，防止小样本球员因数据噪声异常高分。
    0 场时 confidence=0，返回 50.0（基准分）。
    """
    if p.total_matches == 0:
        return 50.0
    beta = ts.beta if ts else 0.6
    gamma = ts.gamma if ts else 0.4
    dw = ts.defense_weight if ts else 0.1
    tp = ts.turnover_penalty if ts else 0.2
    raw = (
        beta * (p.total_goals / p.total_matches)
        + gamma * (p.total_assists / p.total_matches)
        + dw * max(p.total_defenses / p.total_matches, 0.0)
        - tp * (p.total_turnovers / p.total_matches)
    )
    raw_perf = 50.0 + raw * 10.0
    confidence = _match_confidence(p.total_matches, ts)
    return max(0.0, 50.0 + confidence * (raw_perf - 50.0))


async def _compute_attendance_rate_map(
    db: AsyncSession,
    team_id: int,
    players: list[Player],
) -> dict[int, float]:
    """批量计算训练/比赛出勤率（0-100），新成员仅统计入队后的已发布历史日程。"""
    if not players:
        return {}

    today = date_type.today()
    result = await db.execute(
        select(ScheduleEvent.id, ScheduleEvent.event_type, ScheduleEvent.end_date)
        .where(
            ScheduleEvent.team_id == team_id,
            ScheduleEvent.status == ScheduleEventStatus.published,
            ScheduleEvent.end_date <= today,
            ScheduleEvent.event_type.in_(
                [
                    ScheduleEventType.training,
                    ScheduleEventType.game,
                    ScheduleEventType.internal,
                ]
            ),
        )
        .order_by(ScheduleEvent.end_date, ScheduleEvent.id)
    )
    events = result.all()
    if not events:
        return {p.id: 0.0 for p in players}

    event_map = {
        event_id: {
            "event_type": _enum_value(event_type),
            "end_date": end_date,
        }
        for event_id, event_type, end_date in events
    }
    player_ids = [p.id for p in players]

    attendance_rows = await db.execute(
        select(
            ScheduleAttendance.player_id,
            ScheduleAttendance.event_id,
            ScheduleAttendance.status,
        ).where(
            ScheduleAttendance.player_id.in_(player_ids),
            ScheduleAttendance.event_id.in_(list(event_map.keys())),
        )
    )

    stats_by_player: dict[int, dict[str, float | date_type]] = {}
    for player in players:
        joined_at = player.approved_at or player.created_at
        joined_on = joined_at.date() if joined_at else today
        training_total = 0
        match_total = 0
        for event in event_map.values():
            if event["end_date"] < joined_on:
                continue
            if event["event_type"] == ScheduleEventType.training.value:
                training_total += 1
            else:
                match_total += 1
        stats_by_player[player.id] = {
            "joined_on": joined_on,
            "training_total": float(training_total),
            "training_attended": 0.0,
            "match_total": float(match_total),
            "match_attended": 0.0,
        }

    attended_statuses = {AttendanceStatus.yes.value, AttendanceStatus.sdl.value}
    for player_id, event_id, status in attendance_rows.all():
        player_stats = stats_by_player.get(player_id)
        event = event_map.get(event_id)
        if not player_stats or not event:
            continue
        joined_on = player_stats["joined_on"]
        if isinstance(joined_on, date_type) and event["end_date"] < joined_on:
            continue
        if _enum_value(status) not in attended_statuses:
            continue
        if event["event_type"] == ScheduleEventType.training.value:
            player_stats["training_attended"] += 1.0
        else:
            player_stats["match_attended"] += 1.0

    attendance_rate_map: dict[int, float] = {}
    for player_id, stats in stats_by_player.items():
        ratios: list[float] = []
        training_total = float(stats["training_total"])
        match_total = float(stats["match_total"])
        if training_total > 0:
            ratios.append(float(stats["training_attended"]) / training_total)
        if match_total > 0:
            ratios.append(float(stats["match_attended"]) / match_total)
        attendance_rate_map[player_id] = (sum(ratios) / len(ratios) * 100.0) if ratios else 0.0
    return attendance_rate_map


def _compute_composite_score(
    p: Player,
    ts: TeamSettings | None,
    attendance_rate: float = 0.0,
) -> float:
    """综合战力分 = OpenSkill保守分 + 表现分 + 出勤加成，并按场次做软收敛。"""
    tw = ts.composite_ts_weight if ts else 0.85
    pw = ts.composite_perf_weight if ts else 0.15
    aw = ts.composite_attendance_weight if ts else 0.0
    perf = _compute_perf_score(p, ts)
    raw = tw * p.conservative_rating + pw * perf + aw * attendance_rate
    # 以当前权重下的中性基准为锚，低场次时向基准收敛，避免小样本冲榜。
    baseline = tw * 50.0 + pw * 50.0 + aw * attendance_rate
    confidence = _match_confidence(p.total_matches, ts)
    return baseline + confidence * (raw - baseline)


# sort_by → (column, asc/desc)
_SORT_MAP = {
    "conservative": (Player.conservative_rating, "desc"),
    "mu": (Player.mu, "desc"),
    "sigma": (Player.sigma, "asc"),
    "goals": (Player.total_goals, "desc"),
    "assists": (Player.total_assists, "desc"),
    "defense": (Player.total_defenses, "desc"),
    "plus_minus": (Player.total_plus_minus, "desc"),
    "net_wins": (2 * Player.total_wins - Player.total_matches, "desc"),
    "turnovers": (Player.total_turnovers, "asc"),
}


def _weighted_slope(values: list[float], lam: float = 0.15) -> float:
    """指数衰减加权最小二乘斜率。λ 越大越强调近期（λ=0.15 时首场权重≈末场 15%）。"""
    n = len(values)
    if n < 2:
        return 0.0
    weights = [math.exp(-lam * (n - 1 - i)) for i in range(n)]
    sw = sum(weights)
    x_bar = sum(w * i for i, w in enumerate(weights)) / sw
    y_bar = sum(w * v for v, w in zip(values, weights)) / sw
    num = sum(weights[i] * (i - x_bar) * (values[i] - y_bar) for i in range(n))
    den = sum(weights[i] * (i - x_bar) ** 2 for i in range(n))
    return num / den if den else 0.0


async def _compute_mip_score_map(
    db: AsyncSession,
    player_ids: list[int],
    ts: TeamSettings | None,
    season_start: datetime | None = None,
    season_end: datetime | None = None,
) -> dict[int, float]:
    """MIP 四维复合进步分，归一化至 [0, 1]，完全替代旧线性斜率方案。

    四维指标（权重均可在 TeamSettings 中调整）：
      ① µ 绝对增幅（mip_weight_mu_delta=40%）：赛季首场 → 末场 mu 净增量
      ② 加权趋势斜率（mip_weight_slope=30%）：指数衰减加权回归斜率，抑制末场单点拉高
      ③ 后半程优势（mip_weight_half=20%）：后半段 mu 均值 − 前半段均值
      ④ σ 稳定性（mip_weight_sigma=10%）：σ 首场 − σ 末场（越稳定分越高）

    参与资格：赛季内场次 ≥ mip_min_matches（默认 6）；不达标球员返回 0.0。
    归一化基于当前队伍候选人之间的 min-max，抗单次极端值干扰。
    """
    if not player_ids:
        return {}

    w_delta = ts.mip_weight_mu_delta if ts else 0.40
    w_slope = ts.mip_weight_slope    if ts else 0.30
    w_half  = ts.mip_weight_half     if ts else 0.20
    w_sigma = ts.mip_weight_sigma    if ts else 0.10
    lam     = ts.mip_slope_lambda    if ts else 0.15
    min_n   = int(ts.mip_min_matches) if ts else 6

    conds = [RatingHistory.player_id.in_(player_ids)]
    if season_start:
        conds.append(RatingHistory.created_at >= season_start)
    if season_end:
        conds.append(RatingHistory.created_at < season_end)

    hist_result = await db.execute(
        select(
            RatingHistory.player_id,
            RatingHistory.mu_after,
            RatingHistory.sigma_after,
        )
        .where(*conds)
        .order_by(RatingHistory.player_id, RatingHistory.id)
    )

    player_data: dict[int, dict] = {}
    for pid, mu_after, sigma_after in hist_result.all():
        if pid not in player_data:
            player_data[pid] = {"mus": [], "sigmas": []}
        player_data[pid]["mus"].append(mu_after)
        player_data[pid]["sigmas"].append(sigma_after)

    eligible = {pid: d for pid, d in player_data.items() if len(d["mus"]) >= min_n}
    if not eligible:
        return {pid: 0.0 for pid in player_ids}

    raw: dict[int, dict[str, float]] = {}
    for pid, d in eligible.items():
        mus    = d["mus"]
        sigmas = d["sigmas"]
        n      = len(mus)
        mid    = max(n // 2, 1)
        tail   = mus[mid:] if len(mus[mid:]) > 0 else mus[-1:]
        raw[pid] = {
            "delta": mus[-1] - mus[0],
            "slope": _weighted_slope(mus, lam),
            "half":  sum(tail) / len(tail) - sum(mus[:mid]) / mid,
            "sigma": sigmas[0] - sigmas[-1],
        }

    pids = list(raw.keys())

    def _minmax(vals: list[float]) -> list[float]:
        mn, mx = min(vals), max(vals)
        rng = mx - mn
        return [(v - mn) / rng for v in vals] if rng else [0.5] * len(vals)

    normed: dict[int, dict[str, float]] = {pid: {} for pid in pids}
    for dim in ("delta", "slope", "half", "sigma"):
        for pid, nv in zip(pids, _minmax([raw[pid][dim] for pid in pids])):
            normed[pid][dim] = nv

    mip_map = {
        pid: round(
            w_delta * normed[pid]["delta"]
            + w_slope * normed[pid]["slope"]
            + w_half  * normed[pid]["half"]
            + w_sigma * normed[pid]["sigma"],
            4,
        )
        for pid in pids
    }
    return {pid: mip_map.get(pid, 0.0) for pid in player_ids}


async def _compute_before_rank_map(
    db: AsyncSession,
    team_id: int,
    sort_by: str,
    all_players_full: list["Player"] | None = None,
    ts: "TeamSettings | None" = None,
    attendance_rate_map: dict[int, float] | None = None,
) -> dict[int, int]:
    """计算最近比赛日之前每名球员的排名位置。返回 {player_id: before_rank}
    composite 模式需要传入 all_players_full（含 perf 数据）和 ts（队伍设置）。
    """
    # 找到本队最近一场已通过的比赛
    latest_dt_result = await db.execute(
        select(Match.match_date)
        .where(Match.team_id == team_id, Match.status == MatchStatus.approved)
        .order_by(desc(Match.match_date))
        .limit(1)
    )
    latest_dt = latest_dt_result.scalar()
    if not latest_dt:
        return {}

    # 同一天（按 date 函数）的所有比赛 id
    latest_date_str = latest_dt.strftime("%Y-%m-%d")
    mids_result = await db.execute(
        select(Match.id).where(
            Match.team_id == team_id,
            Match.status == MatchStatus.approved,
            func.date(Match.match_date) == latest_date_str,
        )
    )
    latest_match_ids = [r[0] for r in mids_result.all()]
    if not latest_match_ids:
        return {}

    # 每名参赛球员当天最早那条 RatingHistory（用 min(id) 取比赛日前的 before 值）
    subq = (
        select(
            RatingHistory.player_id,
            func.min(RatingHistory.id).label("min_rh_id"),
        )
        .where(RatingHistory.match_id.in_(latest_match_ids))
        .group_by(RatingHistory.player_id)
        .subquery()
    )
    before_hist = await db.execute(
        select(
            RatingHistory.player_id,
            RatingHistory.conservative_before,
            RatingHistory.sigma_before,
        ).join(
            subq,
            (RatingHistory.player_id == subq.c.player_id)
            & (RatingHistory.id == subq.c.min_rh_id),
        )
    )
    player_before: dict[int, tuple[float, float]] = {
        pid: (cr_b, sig_b) for pid, cr_b, sig_b in before_hist.all()
    }

    # 全队活跃球员（用于重建「比赛日前」的排名列表）
    all_pl = await db.execute(
        select(Player.id, Player.conservative_rating, Player.sigma).where(
            Player.status == PlayerStatus.active,
            Player.team_id == team_id,
            Player.show_in_rankings.is_(True),
        )
    )
    all_players_data = all_pl.all()

    if sort_by == "conservative":
        before_vals = [
            (pid, player_before[pid][0] if pid in player_before else cr)
            for pid, cr, _sig in all_players_data
        ]
        sorted_before = sorted(before_vals, key=lambda x: -x[1])
    elif sort_by == "composite" and all_players_full is not None:
        # 用 conservative_before 替换当前值，保留 perf_score / 出勤率，近似重建比赛前的综合战力
        player_full_map = {p.id: p for p in all_players_full}
        tw = ts.composite_ts_weight if ts else 0.85
        pw = ts.composite_perf_weight if ts else 0.15
        aw = ts.composite_attendance_weight if ts else 0.0
        before_composite: list[tuple[int, float]] = []
        for pid, cr, _sig in all_players_data:
            cr_before = player_before[pid][0] if pid in player_before else cr
            attendance_rate = (attendance_rate_map or {}).get(pid, 0.0)
            p = player_full_map.get(pid)
            if p is None or p.total_matches <= 0:
                continue
            perf_score = _compute_perf_score(p, ts)
            raw_before = tw * cr_before + pw * perf_score + aw * attendance_rate
            baseline = tw * 50.0 + pw * 50.0 + aw * attendance_rate
            confidence = _match_confidence(p.total_matches, ts)
            before_composite.append((pid, baseline + confidence * (raw_before - baseline)))
        sorted_before = sorted(before_composite, key=lambda x: -x[1])
    else:  # sigma（越小越好，升序）
        before_vals = [
            (pid, player_before[pid][1] if pid in player_before else sig)
            for pid, _cr, sig in all_players_data
        ]
        sorted_before = sorted(before_vals, key=lambda x: x[1])

    return {pid: idx + 1 for idx, (pid, _) in enumerate(sorted_before)}


@router.get("", response_model=RankingResponse)
async def get_rankings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("conservative"),
    db: AsyncSession = Depends(get_db),
    team_id: int = Depends(get_effective_team_id),
    current_player: Player = Depends(get_current_active_player),
):
    """排行榜 — 需要登录，仅返回本队成员。sort_by: conservative|mu|sigma|goals|assists|defense|composite|progress

    公平性规则：sort_by=composite 时仅纳入 total_matches>0 的球员。
    """
    # 战力榜（Score = μ - k×σ）仅队伍管理员或超级管理员可见
    if sort_by == "conservative":
        is_admin = (
            current_player.is_superadmin
            or current_player.role in (UserRole.admin, UserRole.owner)
        )
        if not is_admin:
            raise HTTPException(status_code=403, detail="战力榜仅队伍管理员及以上权限可见")
    # 加载本队设置系数（用于 composite/perf 计算，所有排序方式都需要）
    ts_result = await db.execute(select(TeamSettings).where(TeamSettings.team_id == team_id))
    ts = ts_result.scalar_one_or_none()

    offset = (page - 1) * page_size
    speed_map: dict[int, float] = {}
    attendance_rate_map: dict[int, float] = {}
    all_players: list[Player] = []

    if sort_by in ("composite", "progress"):
        # Python 侧计算后排序再分页（队伍规模小，性能不是问题）
        all_result = await db.execute(
            select(Player)
            .where(
                Player.status == PlayerStatus.active,
                Player.team_id == team_id,
                Player.show_in_rankings == True,  # noqa: E712
            )
        )
        all_players = list(all_result.scalars().all())
        if sort_by == "composite":
            all_players = [p for p in all_players if p.total_matches > 0]
        attendance_rate_map = await _compute_attendance_rate_map(db, team_id, all_players)
        if sort_by == "composite":
            all_players.sort(
                key=lambda p: _compute_composite_score(p, ts, attendance_rate_map.get(p.id, 0.0)),
                reverse=True,
            )
        else:  # progress
            all_ids = [p.id for p in all_players]
            speed_map = await _compute_mip_score_map(db, all_ids, ts)
            all_players.sort(key=lambda p: speed_map.get(p.id, 0.0), reverse=True)
        players = all_players[offset: offset + page_size]
    else:
        if sort_by not in _SORT_MAP:
            sort_by = "conservative"
        col, direction = _SORT_MAP[sort_by]
        order = asc(col) if direction == "asc" else desc(col)
        result = await db.execute(
            select(Player)
            .where(
                Player.status == PlayerStatus.active,
                Player.team_id == team_id,
                Player.show_in_rankings == True,  # noqa: E712
            )
            .order_by(order)
            .offset(offset)
            .limit(page_size)
        )
        players = list(result.scalars().all())
        attendance_rate_map = await _compute_attendance_rate_map(db, team_id, players)

    # 仅战力榜和综合战力榜计算名次变化
    before_rank_map: dict[int, int] = {}
    if sort_by == "conservative":
        before_rank_map = await _compute_before_rank_map(db, team_id, sort_by)
    elif sort_by == "composite":
        before_rank_map = await _compute_before_rank_map(
            db,
            team_id,
            "composite",
            all_players_full=all_players,
            ts=ts,
            attendance_rate_map=attendance_rate_map,
        )

    items = [
        RankingItem(
            rank=offset + idx + 1,
            player_id=p.id,
            display_name=p.display_name,
            gender=p.gender,
            jersey_number=p.jersey_number,
            rank_change=(
                before_rank_map.get(p.id, offset + idx + 1) - (offset + idx + 1)
                if before_rank_map
                else None
            ),
            conservative_rating=round(p.conservative_rating, 2),
            mu=round(p.mu, 2),
            sigma=round(p.sigma, 3),
            total_matches=p.total_matches,
            total_wins=p.total_wins,
            total_goals=p.total_goals,
            total_assists=p.total_assists,
            total_defenses=p.total_defenses,
            total_plus_minus=p.total_plus_minus,
            total_turnovers=p.total_turnovers,
            is_new=p.total_matches < 5,
            composite_score=round(
                _compute_composite_score(p, ts, attendance_rate_map.get(p.id, 0.0)),
                2,
            ),
            attendance_rate=round(attendance_rate_map.get(p.id, 0.0), 1),
            progress_speed=round(speed_map.get(p.id, 0.0), 4),
        )
        for idx, p in enumerate(players)
    ]
    return RankingResponse(items=items, page=page, page_size=page_size)


@router.get("/chemistry", response_model=ChemistryResponse)
async def get_chemistry_rankings(
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    team_id: int = Depends(get_effective_team_id),
):
    """默契度排行榜 — 按 chemistry_score 降序，仅返回本队数据，默认前 30 组"""
    from sqlalchemy.orm import aliased

    PlayerA = aliased(Player)
    PlayerB = aliased(Player)

    offset = (page - 1) * page_size
    result = await db.execute(
        select(PlayerChemistry, PlayerA.display_name, PlayerB.display_name,
               PlayerA.jersey_number, PlayerB.jersey_number)
        .join(PlayerA, PlayerChemistry.player_a_id == PlayerA.id)
        .join(PlayerB, PlayerChemistry.player_b_id == PlayerB.id)
        .where(PlayerChemistry.team_id == team_id)
        .order_by(desc(PlayerChemistry.chemistry_score))
        .offset(offset)
        .limit(page_size)
    )
    rows = result.all()

    items = [
        ChemistryItem(
            rank=offset + idx + 1,
            player_a_id=chem.player_a_id,
            player_b_id=chem.player_b_id,
            player_a_name=name_a,
            player_b_name=name_b,
            player_a_jersey=jersey_a,
            player_b_jersey=jersey_b,
            chemistry_score=round(chem.chemistry_score, 2),
            co_matches=chem.co_matches,
            co_wins=chem.co_wins,
            combo_count=chem.combo_count,
        )
        for idx, (chem, name_a, name_b, jersey_a, jersey_b) in enumerate(rows)
    ]
    return ChemistryResponse(items=items, page=page, page_size=page_size)


@router.get("/my-ranks", response_model=dict)
async def get_my_ranks(
    db: AsyncSession = Depends(get_db),
    team_id: int = Depends(get_effective_team_id),
    current_player: Player = Depends(get_current_active_player),
):
    """返回当前登录球员在各个榜单中的排名位置"""
    ts_result = await db.execute(select(TeamSettings).where(TeamSettings.team_id == team_id))
    ts = ts_result.scalar_one_or_none()

    all_result = await db.execute(
        select(Player)
        .where(
            Player.status == PlayerStatus.active,
            Player.team_id == team_id,
            Player.show_in_rankings == True,  # noqa: E712
        )
    )
    all_players = list(all_result.scalars().all())
    if not all_players:
        return {"total": 0, "ranks": {}}

    total = len(all_players)
    attendance_rate_map = await _compute_attendance_rate_map(db, team_id, all_players)
    all_ids = [p.id for p in all_players]
    speed_map = await _compute_mip_score_map(db, all_ids, ts)

    my_id = current_player.id

    def _rank_in(sorted_list: list[Player]) -> int | None:
        for idx, p in enumerate(sorted_list):
            if p.id == my_id:
                return idx + 1
        return None

    # 综合战力榜
    composite_sorted = sorted(
        all_players,
        key=lambda p: _compute_composite_score(p, ts, attendance_rate_map.get(p.id, 0.0)),
        reverse=True,
    )
    # 保守评分榜
    conservative_sorted = sorted(all_players, key=lambda p: p.conservative_rating, reverse=True)
    # 进步榜
    progress_sorted = sorted(all_players, key=lambda p: speed_map.get(p.id, 0.0), reverse=True)
    # 得分榜
    goals_sorted = sorted(all_players, key=lambda p: p.total_goals, reverse=True)
    # 助攻榜
    assists_sorted = sorted(all_players, key=lambda p: p.total_assists, reverse=True)
    # 正负值榜
    pm_sorted = sorted(all_players, key=lambda p: p.total_plus_minus, reverse=True)
    # 失误榜（越少越好，升序）
    turnovers_sorted = sorted(all_players, key=lambda p: p.total_turnovers)

    ranks = {
        "composite": _rank_in(composite_sorted),
        "conservative": _rank_in(conservative_sorted),
        "progress": _rank_in(progress_sorted),
        "goals": _rank_in(goals_sorted),
        "assists": _rank_in(assists_sorted),
        "plus_minus": _rank_in(pm_sorted),
        "turnovers": _rank_in(turnovers_sorted),
    }
    return {"total": total, "ranks": ranks}


@router.get("/panel/{player_id}", response_model=PlayerPanelResponse)
async def get_player_panel(
    player_id: int,
    db: AsyncSession = Depends(get_db),
    _: Player = Depends(get_current_active_player),
):
    """球员个人面板 — 含评分历史、最近比赛、技术统计"""
    # 球员基本信息
    result = await db.execute(
        select(Player).where(Player.id == player_id, Player.status == PlayerStatus.active)
    )
    player = result.scalar_one_or_none()
    if not player:
        raise HTTPException(status_code=404, detail="球员不存在")

    # 最近 10 条评分历史（按时间倒序）
    hist_result = await db.execute(
        select(RatingHistory)
        .where(RatingHistory.player_id == player_id)
        .order_by(desc(RatingHistory.created_at))
        .limit(10)
    )
    history = hist_result.scalars().all()

    # 最近 10 场上场统计
    parts_result = await db.execute(
        select(MatchPlayer)
        .where(MatchPlayer.player_id == player_id)
        .order_by(desc(MatchPlayer.id))
        .limit(10)
    )
    participations = parts_result.scalars().all()

    return {
        "player": {
            "id": player.id,
            "username": player.username,
            "display_name": player.display_name,
            "role": player.role.value,
            "mu": round(player.mu, 3),
            "sigma": round(player.sigma, 3),
            "conservative_rating": round(player.conservative_rating, 3),
            "total_matches": player.total_matches,
            "total_wins": player.total_wins,
            "total_goals": player.total_goals,
            "total_assists": player.total_assists,
        },
        "rating_history": [
            {
                "match_id": h.match_id,
                "mu_before": round(h.mu_before, 3),
                "mu_after": round(h.mu_after, 3),
                "delta_mu": round(h.delta_mu, 3),
                "conservative_after": round(h.conservative_after, 3),
                "created_at": h.created_at.isoformat(),
            }
            for h in history
        ],
        "recent_matches": [
            {
                "match_id": mp.match_id,
                "team_side": mp.team_side.value,
                "goals": mp.goals,
                "assists": mp.assists,
                "defenses": mp.defenses,
                "plus_minus": mp.plus_minus,
                "is_winner": mp.is_winner,
                "is_mvp": mp.is_mvp,
            }
            for mp in participations
        ],
    }

