"""比赛服务 — data_level 自动检测、比赛 CRUD"""
from __future__ import annotations

from datetime import datetime, timezone
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match, MatchEvent, MatchPlayer, MatchStatus, MatchType, RatingHistory, TeamSide, EventType
from app.models.player import Player
from app.schemas.match import MatchCreate, MatchPlayerEntry, MatchUpdate
from app.services.rating_service import apply_ratings


logger = logging.getLogger(__name__)


def detect_data_level(entries: list[MatchPlayerEntry], requested_level: int) -> int:
    """
    根据提交的球员数据自动推断 data_level：
      - 所有人都有 goals/assists/plus_minus → Level 3
      - 所有人都有 goals/assists → Level 2
      - 只有比分 → Level 1
      - 提交的 data_level=0 强制返回 0
    """
    if requested_level == 0:
        return 0
    all_entries = entries
    has_goals = all(e.goals is not None for e in all_entries)
    has_assists = all(e.assists is not None for e in all_entries)
    has_def = all(e.defenses is not None for e in all_entries)

    if has_goals and has_assists and has_def:
        return min(requested_level, 3)
    if has_goals and has_assists:
        return min(requested_level, 2)
    return 1


async def create_match(
    db: AsyncSession,
    body: MatchCreate,
    created_by_id: int,
    team_id: int,
    auto_approve: bool = False,
) -> Match:
    """
    创建比赛记录（含 MatchPlayer）。

    auto_approve=True 时直接核算评分（管理员提交走此路径）。
    否则状态为 pending_approval。
    """
    all_entries = body.team_a + body.team_b
    actual_level = detect_data_level(all_entries, body.data_level)
    if actual_level != body.data_level:
        logger.info(
            "match_data_level_downgraded requested=%s applied=%s match_type=%s team_id=%s",
            body.data_level,
            actual_level,
            body.match_type,
            team_id,
        )

    match = Match(
        team_id=team_id,
        match_type=MatchType(body.match_type),
        data_level=actual_level,
        team_a_score=body.score_us,
        team_b_score=body.score_them,
        opponent_strength=body.opponent_strength,
        opponent_external_team_id=getattr(body, 'opponent_external_team_id', None),
        opponent_calibrated_mu=getattr(body, 'opponent_calibrated_mu', None),
        opponent_calibrated_sigma=getattr(body, 'opponent_calibrated_sigma', None),
        # 保留用户选择的日期，并附上当前录入时间（而非午夜 00:00:00）
        match_date=datetime.now(timezone.utc).replace(
            year=body.match_date.year,
            month=body.match_date.month,
            day=body.match_date.day,
        ),
        notes=body.notes,
        status=MatchStatus.approved if auto_approve else MatchStatus.pending_approval,
        created_by=created_by_id,
        approved_by=created_by_id if auto_approve else None,
        approved_at=datetime.now(timezone.utc) if auto_approve else None,
    )
    db.add(match)
    await db.flush()  # 获取 match.id

    # 验证所有球员是否存在，同时建立 player_map
    all_player_ids = [e.player_id for e in all_entries]
    players_result = await db.execute(
        select(Player).where(Player.id.in_(all_player_ids))
    )
    player_map: dict[int, Player] = {p.id: p for p in players_result.scalars()}
    missing = set(all_player_ids) - set(player_map.keys())
    if missing:
        raise ValueError(f"球员 ID 不存在: {sorted(missing)}")

    participants: list[MatchPlayer] = []
    for entry in body.team_a:
        mp = _make_match_player(match.id, entry, TeamSide.A, player_map[entry.player_id])
        db.add(mp)
        participants.append(mp)
    for entry in body.team_b:
        mp = _make_match_player(match.id, entry, TeamSide.B, player_map[entry.player_id])
        db.add(mp)
        participants.append(mp)

    await db.flush()

    # 写入时间轴事件（必须在 apply_ratings 之前 flush，否则 _apply_chemistry 查不到 goal 事件）
    for ec in body.events:
        try:
            etype = EventType(ec.event_type)
        except ValueError:
            continue  # 忽略无效类型
        event = MatchEvent(
            match_id=match.id,
            event_type=etype,
            team_side=TeamSide(ec.team_side) if ec.team_side else None,
            player_id=ec.player_id,
            assist_player_id=ec.assist_player_id,
            is_break=ec.is_break,
            elapsed_seconds=ec.elapsed_seconds,
        )
        db.add(event)

    await db.flush()  # flush events before rating calculation

    if auto_approve:
        await apply_ratings(db, match, operated_by=created_by_id, participants=participants)

    await db.commit()
    # 只刷新 scalar 属性（column 字段），避免触发 relationship lazy-load
    await db.refresh(match, attribute_names=["id", "status", "team_a_score", "team_b_score", "data_level", "notes", "match_type", "match_date"])
    return match


async def approve_match(
    db: AsyncSession,
    match_id: int,
    approver_id: int,
) -> Match:
    """审批 pending_approval 比赛并结算评分"""
    result = await db.execute(
        select(Match).where(Match.id == match_id).with_for_update()
    )
    match = result.scalar_one_or_none()
    if not match:
        raise ValueError("比赛不存在")
    if match.status != MatchStatus.pending_approval:
        raise ValueError(f"只能审批 pending_approval 状态的比赛，当前状态: {match.status.value}")

    match.status = MatchStatus.approved
    match.approved_by = approver_id
    match.approved_at = datetime.now(timezone.utc)

    parts_result = await db.execute(
        select(MatchPlayer).where(MatchPlayer.match_id == match.id)
    )
    parts_list = list(parts_result.scalars())

    await apply_ratings(db, match, operated_by=approver_id, participants=parts_list)
    await db.commit()
    await db.refresh(match, attribute_names=["id", "status", "team_a_score", "team_b_score", "data_level"])
    return match


def _make_match_player(match_id: int, entry: MatchPlayerEntry, side: TeamSide, player: "Player") -> MatchPlayer:
    return MatchPlayer(
        match_id=match_id,
        player_id=entry.player_id,
        team_side=side,
        goals=entry.goals,
        assists=entry.assists,
        defenses=entry.defenses,
        turnovers=entry.turnovers,
        is_mvp=entry.is_mvp,
        mu_before=player.mu,
        sigma_before=player.sigma,
    )


async def revert_ratings(
    db: AsyncSession,
    match: Match,
    participants: list[MatchPlayer] | None = None,
) -> None:
    """
    将此场比赛的评分影响回退到赛前状态。

    查找该比赛最新一条 RatingHistory（mu_before），将球员 mu/sigma 还原；
    同时还原累计统计（total_matches / total_wins / total_goals / total_assists）。
    """
    if participants is None:
        mp_result = await db.execute(
            select(MatchPlayer).where(MatchPlayer.match_id == match.id)
        )
        participants = list(mp_result.scalars())

    mp_map: dict[int, MatchPlayer] = {mp.player_id: mp for mp in participants}

    # 取每位球员该场比赛的最新 RatingHistory（支持多次 admin_correction）
    rh_result = await db.execute(
        select(RatingHistory)
        .where(RatingHistory.match_id == match.id)
        .order_by(RatingHistory.created_at.desc())
    )
    all_rh: list[RatingHistory] = list(rh_result.scalars())
    # 每位球员只取 created_at 最晚的一条
    latest_rh: dict[int, RatingHistory] = {}
    for rh in all_rh:
        if rh.player_id not in latest_rh:
            latest_rh[rh.player_id] = rh

    if not latest_rh:
        return

    player_ids = list(latest_rh.keys())
    players_result = await db.execute(
        select(Player).where(Player.id.in_(player_ids))
    )
    player_map: dict[int, Player] = {p.id: p for p in players_result.scalars()}

    for pid, rh in latest_rh.items():
        p = player_map.get(pid)
        mp = mp_map.get(pid)
        if not p:
            continue
        p.mu = rh.mu_before
        p.sigma = rh.sigma_before
        p.conservative_rating = rh.conservative_before
        p.total_matches = max(0, p.total_matches - 1)
        if mp:
            if mp.is_winner:
                p.total_wins = max(0, p.total_wins - 1)
            if mp.goals:
                p.total_goals = max(0, p.total_goals - mp.goals)
            if mp.assists:
                p.total_assists = max(0, p.total_assists - mp.assists)
            if mp.defenses:
                p.total_defenses = max(0, p.total_defenses - mp.defenses)
            if mp.plus_minus:
                p.total_plus_minus -= mp.plus_minus
            if mp.turnovers:
                p.total_turnovers = max(0, p.total_turnovers - mp.turnovers)

    await db.flush()


async def edit_approved_match(
    db: AsyncSession,
    match_id: int,
    body: MatchUpdate,
    admin_id: int,
    team_id: int,
) -> Match:
    """
    管理员修改已审批比赛：回退旧评分 → 重算新评分 → 追加 RatingHistory(reason=admin_correction)。
    """

    result = await db.execute(
        select(Match).where(Match.id == match_id, Match.team_id == team_id)
    )
    match = result.scalar_one_or_none()
    if not match:
        raise ValueError("比赛不存在")
    if match.status != MatchStatus.approved:
        raise ValueError(f"只能编辑已审批 (approved) 的比赛，当前状态: {match.status.value}")

    # 1. 加载旧 MatchPlayer（回退前需要）
    old_mp_result = await db.execute(
        select(MatchPlayer).where(MatchPlayer.match_id == match.id)
    )
    old_participants = list(old_mp_result.scalars())

    # 2. 回退旧评分
    await revert_ratings(db, match, old_participants)

    # 3. 删除旧 MatchPlayer（如果有新阵容）
    if body.team_a is not None and body.team_b is not None:
        for mp in old_participants:
            await db.delete(mp)
        await db.flush()

    # 4. 更新比赛字段
    if body.score_us is not None:
        match.team_a_score = body.score_us
    if body.score_them is not None:
        match.team_b_score = body.score_them
    if body.notes is not None:
        match.notes = body.notes
    if body.opponent_strength is not None:
        match.opponent_strength = body.opponent_strength

    # 5. 创建新 MatchPlayer 并重算
    if body.team_a is not None and body.team_b is not None:
        all_entries = body.team_a + body.team_b
        if body.data_level is not None:
            match.data_level = body.data_level
        else:
            match.data_level = detect_data_level(all_entries, 3)

        all_ids = [e.player_id for e in all_entries]
        players_result = await db.execute(
            select(Player).where(Player.id.in_(all_ids))
        )
        player_map: dict[int, Player] = {p.id: p for p in players_result.scalars()}
        missing = set(all_ids) - set(player_map.keys())
        if missing:
            raise ValueError(f"球员 ID 不存在: {sorted(missing)}")

        new_participants: list[MatchPlayer] = []
        for entry in body.team_a:
            mp = _make_match_player(match.id, entry, TeamSide.A, player_map[entry.player_id])
            db.add(mp)
            new_participants.append(mp)
        for entry in body.team_b:
            mp = _make_match_player(match.id, entry, TeamSide.B, player_map[entry.player_id])
            db.add(mp)
            new_participants.append(mp)
        await db.flush()
        await apply_ratings(db, match, operated_by=admin_id, participants=new_participants, reason="admin_correction")
    else:
        # 只改比分，阵容不变：用原来的 participants 重新计算
        # 此时旧 MatchPlayer 还在，但 mu_before 需反映 revert 后的状态
        # _make_match_player 读 player.mu（已回退），这里直接更新旧 MatchPlayer.mu_before
        player_ids = [mp.player_id for mp in old_participants]
        players_result = await db.execute(
            select(Player).where(Player.id.in_(player_ids))
        )
        player_map = {p.id: p for p in players_result.scalars()}
        for mp in old_participants:
            p = player_map.get(mp.player_id)
            if p:
                mp.mu_before = p.mu
                mp.sigma_before = p.sigma
        await db.flush()
        await apply_ratings(db, match, operated_by=admin_id, participants=old_participants, reason="admin_correction")

    await db.commit()
    await db.refresh(match, attribute_names=["id", "status", "team_a_score", "team_b_score", "data_level", "notes"])
    return match
