"""导出端点：管理员/超管导出队伍核心数据（CSV）"""
import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_effective_team_id, require_admin, require_superadmin
from app.core.database import get_db
from app.models.match import Match, TeamSettings
from app.models.player import Player
from app.api.v1.endpoints.rankings import _compute_composite_score

router = APIRouter()


def _csv_response(rows: list[list], filename: str) -> StreamingResponse:
    """生成带 UTF-8 BOM（Excel 兼容）的 CSV StreamingResponse"""
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM
    writer = csv.writer(buf)
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _normalize_attendance_status(value: object) -> str:
    raw = value.value if hasattr(value, "value") else str(value)
    return "leave" if raw == "no" else raw


@router.get("/rankings")
async def export_rankings(
    db: AsyncSession = Depends(get_db),
    _admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
    format: str = Query("csv", pattern="^(csv)$"),
    ranking_type: str = Query(
        "conservative",
        pattern="^(conservative|mu|sigma|goals|assists|plus_minus|turnovers|composite)$",
    ),
):
    """导出排行榜（admin 权限）"""
    result = await db.execute(select(Player).where(Player.team_id == team_id))
    players = result.scalars().all()

    ts: TeamSettings | None = None
    if ranking_type == "composite":
        ts_result = await db.execute(
            select(TeamSettings)
            .where(TeamSettings.team_id == team_id)
            .order_by(TeamSettings.id.desc())
            .limit(1)
        )
        ts = ts_result.scalar_one_or_none()
        players.sort(key=lambda p: _compute_composite_score(p, ts), reverse=True)
    elif ranking_type == "conservative":
        players.sort(key=lambda p: p.conservative_rating, reverse=True)
    elif ranking_type == "mu":
        players.sort(key=lambda p: p.mu, reverse=True)
    elif ranking_type == "sigma":
        players.sort(key=lambda p: p.sigma)
    elif ranking_type == "goals":
        players.sort(key=lambda p: p.total_goals, reverse=True)
    elif ranking_type == "assists":
        players.sort(key=lambda p: p.total_assists, reverse=True)
    elif ranking_type == "plus_minus":
        players.sort(key=lambda p: p.total_plus_minus, reverse=True)
    elif ranking_type == "turnovers":
        players.sort(key=lambda p: p.total_turnovers)
    else:
        raise HTTPException(status_code=400, detail="不支持的排行榜类型")

    now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    if ranking_type == "composite":
        rows = [["排名", "用户名", "显示名称", "μ", "σ", "保守评分", "综合战力分", "总场次", "总胜场", "进球", "助攻", "防守", "正负值", "失误"]]
        for rank, p in enumerate(players, 1):
            rows.append([
                rank,
                p.username,
                p.display_name or p.username,
                round(p.mu, 3),
                round(p.sigma, 3),
                round(p.conservative_rating, 3),
                round(_compute_composite_score(p, ts), 2),
                p.total_matches,
                p.total_wins,
                p.total_goals,
                p.total_assists,
                p.total_defenses,
                p.total_plus_minus,
                p.total_turnovers,
            ])
    else:
        rows = [["排名", "用户名", "显示名称", "μ", "σ", "保守评分", "总场次", "总胜场", "进球", "助攻", "防守", "正负值", "失误"]]
        for rank, p in enumerate(players, 1):
            rows.append([
                rank,
                p.username,
                p.display_name or p.username,
                round(p.mu, 3),
                round(p.sigma, 3),
                round(p.conservative_rating, 3),
                p.total_matches,
                p.total_wins,
                p.total_goals,
                p.total_assists,
                p.total_defenses,
                p.total_plus_minus,
                p.total_turnovers,
            ])

    return _csv_response(rows, f"rankings_{ranking_type}_{now_str}.csv")


@router.get("/matches")
async def export_matches(
    db: AsyncSession = Depends(get_db),
    _admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
    format: str = Query("csv", pattern="^(csv)$"),
):
    """导出比赛记录（admin 权限）"""
    result = await db.execute(
        select(Match)
        .where(Match.team_id == team_id)
        .order_by(Match.match_date.desc())
    )
    matches = result.scalars().all()

    now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    rows = [["ID", "日期", "类型", "我方得分", "对方得分", "状态", "数据级别", "对手强度", "备注"]]
    for m in matches:
        rows.append([
            m.id,
            m.match_date.strftime("%Y-%m-%d"),
            m.match_type.value,
            m.team_a_score,
            m.team_b_score,
            m.status.value,
            m.data_level,
            m.opponent_strength or "",
            m.notes or "",
        ])

    return _csv_response(rows, f"matches_{now_str}.csv")


@router.get("/players")
async def export_players(
    db: AsyncSession = Depends(get_db),
    _admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
    format: str = Query("csv", pattern="^(csv)$"),
):
    """导出队员名单（admin 权限）"""
    result = await db.execute(select(Player).where(Player.team_id == team_id))
    players = result.scalars().all()
    players.sort(key=lambda p: (p.role.value, p.username))

    now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    rows = [["ID", "用户名", "显示名称", "角色", "状态", "邮箱", "性别", "球衣号码", "创建时间"]]
    for p in players:
        rows.append([
            p.id,
            p.username,
            p.display_name or p.username,
            p.role.value,
            p.status.value,
            p.email or "",
            p.gender or "",
            p.jersey_number if p.jersey_number is not None else "",
            p.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        ])

    return _csv_response(rows, f"players_{now_str}.csv")


@router.get("/player-stats")
async def export_player_stats(
    db: AsyncSession = Depends(get_db),
    _admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
    format: str = Query("csv", pattern="^(csv)$"),
    player_id: int | None = Query(None, ge=1),
):
    """导出个人数据集合；支持按 player_id 导出单个队员完整信息（admin 权限）"""
    result = await db.execute(
        select(Player)
        .where(Player.team_id == team_id)
        .order_by(Player.conservative_rating.desc())
    )
    players = result.scalars().all()

    if player_id is not None:
        players = [p for p in players if p.id == player_id]
        if not players:
            raise HTTPException(status_code=404, detail="队员不存在或不属于当前队伍")

    now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    rows = [[
        "排名",
        "ID",
        "队伍ID",
        "用户名",
        "显示名称",
        "角色",
        "状态",
        "邮箱",
        "性别",
        "球衣号码",
        "头像URL",
        "是否超级管理员",
        "是否展示在排行榜",
        "总场次",
        "总胜场",
        "进球",
        "助攻",
        "防守",
        "正负值",
        "失误",
        "μ",
        "σ",
        "保守评分",
        "创建时间",
        "审批时间",
        "审批人ID",
    ]]

    for rank, p in enumerate(players, 1):
        rows.append([
            rank,
            p.id,
            p.team_id,
            p.username,
            p.display_name or p.username,
            p.role.value,
            p.status.value,
            p.email or "",
            p.gender or "",
            p.jersey_number if p.jersey_number is not None else "",
            p.avatar_url or "",
            p.is_superadmin,
            p.show_in_rankings,
            p.total_matches,
            p.total_wins,
            p.total_goals,
            p.total_assists,
            p.total_defenses,
            p.total_plus_minus,
            p.total_turnovers,
            round(p.mu, 3),
            round(p.sigma, 3),
            round(p.conservative_rating, 3),
            p.created_at.strftime("%Y-%m-%d %H:%M:%S") if p.created_at else "",
            p.approved_at.strftime("%Y-%m-%d %H:%M:%S") if p.approved_at else "",
            p.approved_by if p.approved_by is not None else "",
        ])

    if player_id is not None and players:
        single_name = players[0].username
        return _csv_response(rows, f"player_profile_{single_name}_{now_str}.csv")
    return _csv_response(rows, f"player_stats_{now_str}.csv")


@router.get("/team-settings")
async def export_team_settings(
    db: AsyncSession = Depends(get_db),
    _superadmin: Player = Depends(require_superadmin),
):
    """导出所有队伍配置系数（超级管理员专属）"""
    from app.models.team import Team  # noqa: PLC0415

    ts_result = await db.execute(select(TeamSettings))
    all_ts = ts_result.scalars().all()

    # 同时查队伍名称
    team_result = await db.execute(select(Team))
    team_map: dict[int, str] = {t.id: (t.name or str(t.id)) for t in team_result.scalars()}

    now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    rows = [[
        "队伍ID",
        "队伍名称",
        "alpha（主动调整幅度）",
        "beta（进球贡献权重）",
        "gamma（助攻贡献权重）",
        "defense_weight（防守贡献权重）",
        "composite_ts_weight（OpenSkill占比）",
        "composite_perf_weight（表现分占比）",
        "composite_attendance_weight（出勤加成占比）",
        "winner_floor_factor（胜者保底比例）",
        "sigma_bonus_factor（σ收缩加分）",
        "turnover_penalty（失误惩罚）",
        "break_bonus_per_goal（break加成）",
        "universal_point_bonus（宇宙分加成）",
        "block_mu_bonus（防守加成）",
        "consecutive_turnover_threshold（连续失误阈值）",
        "consecutive_turnover_multiplier（连续失误倍率）",
        "turnover_sigma_factor（失误σ惩罚）",
        "external_impact_multiplier（外战影响倍率）",
        "external_opp_mu_min（外战对手最低μ）",
        "external_opp_mu_max（外战对手最高μ）",
        "external_opp_sigma（外战对手σ）",
        "openskill_mu（初始μ）",
        "openskill_sigma（初始σ）",
        "openskill_beta（β）",
        "openskill_tau（τ）",
        "openskill_kappa（κ）",
        "openskill_margin（margin）",
        "openskill_limit_sigma（限制σ下限）",
        "openskill_balance（平衡模式）",
        "更新时间",
        "更新人ID",
    ]]
    for ts in all_ts:
        rows.append([
            ts.team_id,
            team_map.get(ts.team_id, str(ts.team_id)),
            ts.alpha,
            ts.beta,
            ts.gamma,
            ts.defense_weight,
            ts.composite_ts_weight,
            ts.composite_perf_weight,
            ts.composite_attendance_weight,
            ts.winner_floor_factor,
            ts.sigma_bonus_factor,
            ts.turnover_penalty,
            ts.break_bonus_per_goal,
            ts.universal_point_bonus,
            ts.block_mu_bonus,
            ts.consecutive_turnover_threshold,
            ts.consecutive_turnover_multiplier,
            ts.turnover_sigma_factor,
            ts.external_impact_multiplier,
            ts.external_opp_mu_min,
            ts.external_opp_mu_max,
            ts.external_opp_sigma,
            ts.openskill_mu,
            round(ts.openskill_sigma, 6),
            round(ts.openskill_beta, 6),
            round(ts.openskill_tau, 6),
            ts.openskill_kappa,
            ts.openskill_margin,
            int(ts.openskill_limit_sigma),
            int(ts.openskill_balance),
            ts.updated_at.strftime("%Y-%m-%d %H:%M:%S") if ts.updated_at else "",
            ts.updated_by if ts.updated_by is not None else "",
        ])

    return _csv_response(rows, f"team_settings_{now_str}.csv")


@router.get("/schedule")
async def export_schedule(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    """导出指定日期范围内的日程活动及出勤明细（CSV）"""
    from datetime import date as date_type
    from app.models.schedule import (
        ScheduleEvent, ScheduleAttendance, ScheduleLine, ScheduleLinePlayer,
        ScheduleLineDivision,
    )

    try:
        start = date_type.fromisoformat(start_date)
        end = date_type.fromisoformat(end_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")

    if end < start:
        raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")

    ev_res = await db.execute(
        select(ScheduleEvent).where(
            ScheduleEvent.team_id == team_id,
            ScheduleEvent.start_date <= end,
            ScheduleEvent.end_date >= start,
        ).order_by(ScheduleEvent.start_date)
    )
    events = ev_res.scalars().all()

    # 预载全队活跃球员，确保导出中能看到每个活动的完整出勤情况
    p_res = await db.execute(
        select(Player)
        .where(Player.team_id == team_id, Player.status == "active")
        .order_by(Player.id.asc())
    )
    team_players = p_res.scalars().all()
    player_map = {p.id: p.display_name or p.username for p in team_players}
    team_player_ids = [p.id for p in team_players]

    now_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    type_label_map = {"game": "外战", "training": "训练", "internal": "内战", "other": "其他"}
    status_label_map = {"draft": "草稿", "published": "已发布"}
    attendance_label_map = {"yes": "出勤", "leave": "请假", "sdl": "场边加油", "未填写": "未填写"}

    rows: list[list] = [
        ["队伍日程 / 出勤导出"],
        ["时间范围", f"{start_date} ~ {end_date}"],
        ["活动数量", len(events)],
        [],
    ]

    for index, ev in enumerate(events, start=1):
        # 出勤记录
        att_res = await db.execute(
            select(ScheduleAttendance).where(ScheduleAttendance.event_id == ev.id)
        )
        att_map = {a.player_id: _normalize_attendance_status(a.status) for a in att_res.scalars().all()}

        # Line 分配
        div_res = await db.execute(
            select(ScheduleLineDivision).where(ScheduleLineDivision.event_id == ev.id)
        )
        div = div_res.scalar_one_or_none()
        player_line_map: dict[int, dict[str, object]] = {}
        if div:
            lines_res = await db.execute(
                select(ScheduleLine).where(ScheduleLine.division_id == div.id)
            )
            for line in lines_res.scalars().all():
                lp_res = await db.execute(
                    select(ScheduleLinePlayer).where(ScheduleLinePlayer.line_id == line.id)
                )
                for lp in lp_res.scalars().all():
                    player_line_map[lp.player_id] = {
                        "line_name": line.line_name,
                        "round_number": line.round_number,
                    }

        rows.append([f"==== 活动 {index} ===="])
        rows.append(["活动标题", ev.title, "类型", type_label_map.get(ev.event_type.value, ev.event_type.value), "状态", status_label_map.get(ev.status.value, ev.status.value)])
        rows.append(["开始日期", ev.start_date.isoformat(), "结束日期", ev.end_date.isoformat(), "备注", ev.description or "-"])
        rows.append(["序号", "球员ID", "球员名称", "出勤状态", "所在分组", "轮次"])

        # 以全队活跃球员为基准导出每场活动的完整出勤情况；若队伍暂无活跃球员，则退回到有记录的球员集合
        all_pids = team_player_ids or sorted(set(att_map.keys()) | set(player_line_map.keys()))
        if not all_pids:
            rows.append([1, "", "", attendance_label_map["未填写"], "", ""])
        else:
            for row_no, pid in enumerate(all_pids, start=1):
                line_info = player_line_map.get(pid, {})
                raw_status = att_map.get(pid, "未填写")
                rows.append([
                    row_no,
                    pid,
                    player_map.get(pid, str(pid)),
                    attendance_label_map.get(raw_status, raw_status),
                    line_info.get("line_name", ""),
                    line_info.get("round_number", ""),
                ])
        rows.append([])

    return _csv_response(rows, f"schedule_{start_date}_{end_date}_{now_str}.csv")
