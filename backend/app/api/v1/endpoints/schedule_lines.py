"""分 line 方案端点：CRUD + 自动分配 + 手动调整"""
from __future__ import annotations

import json
from datetime import datetime, timezone
import math

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_effective_team_id, require_admin
from app.core.database import get_db
from app.models.player import Player
from app.models.match import Match, MatchPlayer, MatchStatus, MatchType, PlayerChemistry, TeamSide
from app.models.schedule import (
    DivisionMethod,
    LineType,
    ScheduleAttendance,
    ScheduleEvent,
    ScheduleEventType,
    ScheduleLine,
    ScheduleLineDivision,
    ScheduleLinePlayer,
    ScheduleLineTemplate,
)
from app.schemas.schedule import (
    AutoAssignRequest,
    DivisionCreate,
    DivisionUpdate,
    LineCreate,
    LinePlayerAdd,
    LineUpdate,
    ManualLineAnalyzeRequest,
    ScheduleLineDivisionRead,
    ScheduleLineRead,
    LinePlayerInfo,
    ScheduleLineTemplateRead,
    ScheduleLineTemplateSave,
    SmartLineAnalyzeRequest,
    SmartLineAnalyzeResponse,
)

router = APIRouter()
MAX_TEMPLATES_PER_TYPE = 3


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


# ─── 获取模板列表（仅训练/外战） ───────────────────────────────────────────────────

@router.get("/templates", response_model=list[ScheduleLineTemplateRead])
async def list_templates(
    event_type: str,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    if event_type not in {ScheduleEventType.game.value, ScheduleEventType.training.value}:
        raise HTTPException(status_code=400, detail="仅外战和训练支持模板")

    result = await db.execute(
        select(ScheduleLineTemplate)
        .where(
            ScheduleLineTemplate.team_id == team_id,
            ScheduleLineTemplate.event_type == ScheduleEventType(event_type),
        )
        .order_by(ScheduleLineTemplate.updated_at.desc(), ScheduleLineTemplate.id.desc())
    )
    templates = result.scalars().all()
    return [_build_template_read(item) for item in templates]


# ─── 获取分 line 方案（含所有 line 和球员） ──────────────────────────────────────────

@router.get("/{event_id}/division", response_model=ScheduleLineDivisionRead)
async def get_division(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    await _require_event(db, event_id, team_id)
    div = await _get_division(db, event_id)
    if not div:
        raise HTTPException(status_code=404, detail="尚未建立分 line 方案")
    return await _build_division_read(db, div)


# ─── 创建 / 重置分 line 方案 ────────────────────────────────────────────────────────

@router.post("/{event_id}/division", response_model=ScheduleLineDivisionRead, status_code=201)
async def create_or_reset_division(
    event_id: int,
    body: DivisionCreate,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    ev = await _require_event(db, event_id, team_id)

    # 训练/外战强制 total_rounds=1
    if ev.event_type in (ScheduleEventType.training, ScheduleEventType.game):
        total_rounds = 1
    else:
        total_rounds = body.total_rounds

    # 已有则删除重建（重置）
    existing = await _get_division(db, event_id)
    if existing:
        await db.delete(existing)
        await db.flush()

    div = ScheduleLineDivision(
        event_id=event_id,
        division_method=DivisionMethod(body.division_method),
        total_rounds=total_rounds,
    )
    db.add(div)
    await db.commit()
    await db.refresh(div)
    return await _build_division_read(db, div)


@router.put("/{event_id}/division", response_model=ScheduleLineDivisionRead)
async def update_division(
    event_id: int,
    body: DivisionUpdate,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    """增加内战分 line 轮数，最多 10 轮；外战/训练固定为 1 轮。"""
    ev = await _require_event(db, event_id, team_id)
    div = await _require_division(db, event_id)

    if ev.event_type in (ScheduleEventType.training, ScheduleEventType.game):
        div.total_rounds = 1
    else:
        if body.total_rounds < div.total_rounds:
            raise HTTPException(status_code=400, detail="暂不支持减少轮数，请直接保持或增加到 10 轮内")
        div.total_rounds = min(body.total_rounds, 10)

    div.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(div)
    return await _build_division_read(db, div)


@router.delete("/{event_id}/division/rounds/{round_number}", response_model=ScheduleLineDivisionRead)
async def delete_division_round(
    event_id: int,
    round_number: int,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    """删除指定轮次，并将后续轮次顺序前移一位。"""
    ev = await _require_event(db, event_id, team_id)
    div = await _require_division(db, event_id)

    if ev.event_type != ScheduleEventType.internal:
        raise HTTPException(status_code=400, detail="只有内战支持删除轮次")
    if div.total_rounds <= 1:
        raise HTTPException(status_code=400, detail="当前仅剩 1 轮，无法继续删除")
    if round_number < 1 or round_number > div.total_rounds:
        raise HTTPException(status_code=404, detail="轮次不存在")

    lines_res = await db.execute(
        select(ScheduleLine).where(
            ScheduleLine.division_id == div.id,
            ScheduleLine.round_number == round_number,
        )
    )
    for line in lines_res.scalars().all():
        await db.delete(line)

    later_lines_res = await db.execute(
        select(ScheduleLine).where(
            ScheduleLine.division_id == div.id,
            ScheduleLine.round_number > round_number,
        )
    )
    for line in later_lines_res.scalars().all():
        line.round_number -= 1

    div.total_rounds -= 1
    div.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(div)
    return await _build_division_read(db, div)


# ─── 新建一条 line ──────────────────────────────────────────────────────────────

@router.post("/{event_id}/division/lines", response_model=ScheduleLineRead, status_code=201)
async def create_line(
    event_id: int,
    body: LineCreate,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    await _require_event(db, event_id, team_id)
    div = await _require_division(db, event_id)

    # line 数量限制
    existing_lines = await db.execute(
        select(ScheduleLine).where(
            ScheduleLine.division_id == div.id,
            ScheduleLine.round_number == body.round_number,
        )
    )
    count = len(existing_lines.scalars().all())
    ev = await _require_event(db, event_id, team_id)
    max_lines = 4 if ev.event_type == ScheduleEventType.game else 8
    if count >= max_lines:
        raise HTTPException(status_code=400, detail=f"当前轮最多 {max_lines} 条 line")

    line = ScheduleLine(
        division_id=div.id,
        line_name=body.line_name,
        line_type=LineType(body.line_type),
        round_number=body.round_number,
        order_index=body.order_index,
    )
    db.add(line)
    await db.commit()
    await db.refresh(line)
    return ScheduleLineRead(id=line.id, line_name=line.line_name, line_type=_enum_value(line.line_type),
                            round_number=line.round_number, order_index=line.order_index, players=[])


# ─── 更新 line 信息 ──────────────────────────────────────────────────────────────

@router.put("/{event_id}/division/lines/{line_id}", response_model=ScheduleLineRead)
async def update_line(
    event_id: int,
    line_id: int,
    body: LineUpdate,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    await _require_event(db, event_id, team_id)
    line = await _require_line(db, line_id, event_id)

    if body.line_name is not None:
        line.line_name = body.line_name
    if body.line_type is not None:
        line.line_type = LineType(body.line_type)
    if body.order_index is not None:
        line.order_index = body.order_index

    await db.commit()
    await db.refresh(line)
    return await _build_line_read(db, line)


# ─── 删除一条 line ──────────────────────────────────────────────────────────────

@router.delete("/{event_id}/division/lines/{line_id}", status_code=204)
async def delete_line(
    event_id: int,
    line_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    await _require_event(db, event_id, team_id)
    line = await _require_line(db, line_id, event_id)
    await db.delete(line)
    await db.commit()


# ─── 向 line 添加球员 ────────────────────────────────────────────────────────────

@router.post("/{event_id}/division/lines/{line_id}/players", response_model=ScheduleLineRead, status_code=201)
async def add_player_to_line(
    event_id: int,
    line_id: int,
    body: LinePlayerAdd,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    await _require_event(db, event_id, team_id)
    line = await _require_line(db, line_id, event_id)

    # 当前轮内同一球员只能出现在一条 line 中（外战/训练/内战均适用）
    await _check_round_uniqueness(db, line, body.player_id, event_id)

    # 校验球员属于本队
    p_res = await db.execute(select(Player).where(Player.id == body.player_id, Player.team_id == team_id))
    if not p_res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="球员不存在或不属于本队")

    # 校验 line 内不重复
    dup = await db.execute(
        select(ScheduleLinePlayer).where(
            ScheduleLinePlayer.line_id == line_id,
            ScheduleLinePlayer.player_id == body.player_id,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该球员已在此 line 中")

    lp = ScheduleLinePlayer(line_id=line_id, player_id=body.player_id)
    db.add(lp)
    await db.commit()
    await db.refresh(line)
    return await _build_line_read(db, line)


# ─── 从 line 移除球员 ────────────────────────────────────────────────────────────

@router.delete("/{event_id}/division/lines/{line_id}/players/{player_id}", status_code=204)
async def remove_player_from_line(
    event_id: int,
    line_id: int,
    player_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    await _require_event(db, event_id, team_id)
    await _require_line(db, line_id, event_id)

    lp_res = await db.execute(
        select(ScheduleLinePlayer).where(
            ScheduleLinePlayer.line_id == line_id,
            ScheduleLinePlayer.player_id == player_id,
        )
    )
    lp = lp_res.scalar_one_or_none()
    if not lp:
        raise HTTPException(status_code=404, detail="球员不在此 line 中")
    await db.delete(lp)
    await db.commit()


# ─── 自动分 line ─────────────────────────────────────────────────────────────────

@router.post("/{event_id}/division/auto-assign", response_model=ScheduleLineDivisionRead)
async def auto_assign(
    event_id: int,
    body: AutoAssignRequest,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    """
    自动分 line：
    - auto_balanced:  尽量使各 line 战力平均（蛇形分配）
    - auto_strong_to_weak: 按战力从强到弱顺序排入各 line（仅外战/训练）
    内战时按 round_number 分配，同轮球员不可重复。
    """
    ev = await _require_event(db, event_id, team_id)
    div = await _require_division(db, event_id)

    # 确定参与球员池
    if body.player_ids:
        p_res = await db.execute(
            select(Player).where(Player.id.in_(body.player_ids), Player.team_id == team_id)
        )
        players = p_res.scalars().all()
    else:
        # 默认取出勤为 yes 的球员
        att_res = await db.execute(
            select(ScheduleAttendance.player_id).where(
                ScheduleAttendance.event_id == event_id,
                ScheduleAttendance.status == "yes",
            )
        )
        yes_ids = [r for (r,) in att_res]
        if not yes_ids:
            raise HTTPException(status_code=400, detail="没有确认出勤的球员")
        p_res = await db.execute(select(Player).where(Player.id.in_(yes_ids)))
        players = p_res.scalars().all()

    if not players:
        raise HTTPException(status_code=400, detail="球员池为空")

    # 删除该轮已有的 line（重新分配）
    old_lines = await db.execute(
        select(ScheduleLine).where(
            ScheduleLine.division_id == div.id,
            ScheduleLine.round_number == body.round_number,
        )
    )
    for ol in old_lines.scalars().all():
        await db.delete(ol)
    await db.flush()

    # 按战力排序（保守评分降序）
    sorted_players = sorted(players, key=lambda p: p.conservative_rating, reverse=True)

    num_lines = min(body.num_lines, len(sorted_players))
    # 为外战赛事自动生成 O/D line 命名
    if ev.event_type == ScheduleEventType.game:
        line_names = ["O Line"] + [f"D Line {i}" for i in range(1, num_lines)]
        line_types = [LineType.o_line] + [LineType.d_line] * (num_lines - 1)
    else:
        line_names = [f"Line {i + 1}" for i in range(num_lines)]
        line_types = [LineType.line] * num_lines

    # 创建 line 对象
    lines: list[ScheduleLine] = []
    for i in range(num_lines):
        line = ScheduleLine(
            division_id=div.id,
            line_name=line_names[i],
            line_type=line_types[i],
            round_number=body.round_number,
            order_index=i,
        )
        db.add(line)
        lines.append(line)
    await db.flush()
    for line in lines:
        await db.refresh(line)

    # 分配球员
    if body.method == "auto_balanced":
        # 蛇形分配：1→2→3→3→2→1→...
        assignments: list[list[int]] = [[] for _ in range(num_lines)]
        direction = 1
        idx = 0
        for player in sorted_players:
            assignments[idx].append(player.id)
            idx += direction
            if idx >= num_lines:
                idx = num_lines - 1
                direction = -1
            elif idx < 0:
                idx = 0
                direction = 1
    else:  # auto_strong_to_weak
        # 顺序分配
        assignments = [[] for _ in range(num_lines)]
        for i, player in enumerate(sorted_players):
            assignments[i % num_lines].append(player.id)

    for line, pid_list in zip(lines, assignments):
        for pid in pid_list:
            db.add(ScheduleLinePlayer(line_id=line.id, player_id=pid))

    # 同步更新 div.division_method
    div.division_method = DivisionMethod(body.method)
    div.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(div)
    return await _build_division_read(db, div)


# ─── 保存 / 套用分 line 模板（仅训练 / 外战） ──────────────────────────────────────

@router.post("/{event_id}/division/templates", response_model=ScheduleLineTemplateRead, status_code=201)
async def save_division_template(
    event_id: int,
    body: ScheduleLineTemplateSave,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    ev = await _require_event(db, event_id, team_id)
    _ensure_template_supported(ev)
    div = await _require_division(db, event_id)

    round_lines_result = await db.execute(
        select(ScheduleLine)
        .where(
            ScheduleLine.division_id == div.id,
            ScheduleLine.round_number == 1,
        )
        .order_by(ScheduleLine.order_index, ScheduleLine.id)
    )
    round_lines = round_lines_result.scalars().all()
    if not round_lines:
        raise HTTPException(status_code=400, detail="当前没有可保存的 Line，先完成分组再保存模板")

    # Batch-fetch all ScheduleLinePlayer records for round_lines in one query
    round_line_ids = [round_line.id for round_line in round_lines]
    lp_batch = await db.execute(
        select(ScheduleLinePlayer).where(ScheduleLinePlayer.line_id.in_(round_line_ids))
    )
    lp_by_line_id: dict[int, list[int]] = {}
    for lp in lp_batch.scalars().all():
        lp_by_line_id.setdefault(lp.line_id, []).append(lp.player_id)

    lines_payload = [
        {
            "line_name": line.line_name,
            "line_type": _enum_value(line.line_type),
            "order_index": line.order_index,
            "player_ids": lp_by_line_id.get(line.id, []),
        }
        for line in round_lines
    ]

    template_name = body.template_name.strip()
    if not template_name:
        raise HTTPException(status_code=400, detail="模板名称不能为空")

    existing_result = await db.execute(
        select(ScheduleLineTemplate).where(
            ScheduleLineTemplate.team_id == team_id,
            ScheduleLineTemplate.event_type == ev.event_type,
            ScheduleLineTemplate.template_name == template_name,
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing is None:
        count_result = await db.execute(
            select(ScheduleLineTemplate.id).where(
                ScheduleLineTemplate.team_id == team_id,
            )
        )
        if len(count_result.scalars().all()) >= MAX_TEMPLATES_PER_TYPE:
            raise HTTPException(status_code=400, detail="当前队伍最多保存 3 个模板，请先覆盖同名模板或减少模板数量")
        existing = ScheduleLineTemplate(
            team_id=team_id,
            event_type=ev.event_type,
            template_name=template_name,
            payload_json=json.dumps(lines_payload, ensure_ascii=False),
            created_by=admin.id,
        )
        db.add(existing)
    else:
        existing.payload_json = json.dumps(lines_payload, ensure_ascii=False)
        existing.created_by = admin.id
        existing.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(existing)
    return _build_template_read(existing)


@router.post("/{event_id}/division/templates/{template_id}/apply", response_model=ScheduleLineDivisionRead)
async def apply_division_template(
    event_id: int,
    template_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    ev = await _require_event(db, event_id, team_id)
    _ensure_template_supported(ev)
    div = await _require_division(db, event_id)
    template = await _require_template(db, template_id, team_id, ev.event_type)

    try:
        lines_payload = json.loads(template.payload_json or "[]")
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="模板数据损坏，请重新保存模板") from exc

    if not isinstance(lines_payload, list) or not lines_payload:
        raise HTTPException(status_code=400, detail="模板为空，请重新保存")

    existing_lines_result = await db.execute(
        select(ScheduleLine)
        .where(
            ScheduleLine.division_id == div.id,
            ScheduleLine.round_number == 1,
        )
        .order_by(ScheduleLine.order_index, ScheduleLine.id)
    )
    existing_lines = existing_lines_result.scalars().all()

    current_player_ids: list[int] = []
    if existing_lines:
        existing_line_ids = [existing_line.id for existing_line in existing_lines]
        lp_rows = await db.execute(
            select(ScheduleLinePlayer.player_id).where(
                ScheduleLinePlayer.line_id.in_(existing_line_ids)
            )
        )
        seen_ids: set[int] = set()
        for pid in lp_rows.scalars().all():
            if pid not in seen_ids:
                seen_ids.add(pid)
                current_player_ids.append(pid)

    if not current_player_ids:
        template_player_ids: list[int] = []
        for line_payload in lines_payload:
            for player_id in line_payload.get("player_ids", []):
                if player_id not in template_player_ids:
                    template_player_ids.append(player_id)
        if template_player_ids:
            valid_players = await db.execute(
                select(Player.id).where(
                    Player.id.in_(template_player_ids),
                    Player.team_id == team_id,
                )
            )
            current_player_ids = list(valid_players.scalars().all())

    for line in existing_lines:
        await db.delete(line)
    await db.flush()

    created_lines: list[ScheduleLine] = []
    for index, line_payload in enumerate(lines_payload):
        line_type = line_payload.get("line_type") or LineType.line.value
        line = ScheduleLine(
            division_id=div.id,
            line_name=line_payload.get("line_name") or f"Line {index + 1}",
            line_type=LineType(line_type),
            round_number=1,
            order_index=index,
        )
        db.add(line)
        created_lines.append(line)
    await db.flush()

    available_ids = set(current_player_ids)
    placed_ids: set[int] = set()
    for line, line_payload in zip(created_lines, lines_payload):
        for player_id in line_payload.get("player_ids", []):
            if player_id in available_ids and player_id not in placed_ids:
                db.add(ScheduleLinePlayer(line_id=line.id, player_id=player_id))
                placed_ids.add(player_id)

    remaining_ids = [player_id for player_id in current_player_ids if player_id not in placed_ids]
    if created_lines and remaining_ids:
        for index, player_id in enumerate(remaining_ids):
            db.add(ScheduleLinePlayer(line_id=created_lines[index % len(created_lines)].id, player_id=player_id))

    div.division_method = DivisionMethod.manual
    div.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(div)
    return await _build_division_read(db, div)


# ─── 获取可用于导入到比赛阵容的分 line 信息 ─────────────────────────────────────────

@router.get("/{event_id}/division/for-match", response_model=dict)
async def get_division_for_match(
    event_id: int,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    """
    返回可导入比赛阵容的分 line 结构：
    - 外战/训练：lines（所有球员合并或按 line 列出）
    - 内战：rounds → lines
    """
    ev = await _require_event(db, event_id, team_id)
    div = await _get_division(db, event_id)
    if not div:
        raise HTTPException(status_code=404, detail="尚未建立分 line 方案")

    read = await _build_division_read(db, div)

    # 按轮次分组
    rounds: dict[int, list[ScheduleLineRead]] = {}
    for line in read.lines:
        rounds.setdefault(line.round_number, []).append(line)

    return {
        "event_id": event_id,
        "event_type": _enum_value(ev.event_type),
        "total_rounds": div.total_rounds,
        "rounds": {
            str(rn): [
                {
                    "id": round_line.id,
                    "line_name": round_line.line_name,
                    "line_type": round_line.line_type,
                    "player_ids": [lp.player_id for lp in round_line.players],
                }
                for round_line in lines
            ]
            for rn, lines in rounds.items()
        },
    }


@router.post("/smart-external-lines", response_model=SmartLineAnalyzeResponse)
async def analyze_smart_external_lines(
    body: SmartLineAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    event: ScheduleEvent | None = None
    if body.schedule_event_id:
        event = await _require_event(db, body.schedule_event_id, team_id)
        if event.event_type != ScheduleEventType.game:
            raise HTTPException(status_code=400, detail="仅外战支持智能 O/D 分线")

    return await _run_smart_external_line_analysis(
        db=db,
        team_id=team_id,
        body=body,
        event=event,
    )


@router.post("/{event_id}/division/smart-external-lines", response_model=SmartLineAnalyzeResponse)
async def smart_external_lines(
    event_id: int,
    body: SmartLineAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    ev = await _require_event(db, event_id, team_id)
    if ev.event_type != ScheduleEventType.game:
        raise HTTPException(status_code=400, detail="仅外战支持智能 O/D 分线")

    return await _run_smart_external_line_analysis(
        db=db,
        team_id=team_id,
        body=body,
        event=ev,
    )


@router.post("/analyze-assigned-lines", response_model=SmartLineAnalyzeResponse)
async def analyze_assigned_lines(
    body: ManualLineAnalyzeRequest,
    db: AsyncSession = Depends(get_db),
    admin: Player = Depends(require_admin),
    team_id: int = Depends(get_effective_team_id),
):
    """对已手动分配好的 Line 方案执行与智能分析相同的算法，返回统一格式的分析报告。"""
    if not body.lines:
        raise HTTPException(status_code=400, detail="请至少提供一条 Line 数据")

    return await _run_assigned_line_analysis(db=db, team_id=team_id, body=body)


# ─── 内部工具函数 ────────────────────────────────────────────────────────────────


async def _load_attendance_yes_ids(db: AsyncSession, event_id: int) -> list[int]:
    att_res = await db.execute(
        select(ScheduleAttendance.player_id).where(
            ScheduleAttendance.event_id == event_id,
            ScheduleAttendance.status == "yes",
        )
    )
    return [row for (row,) in att_res]


async def _load_players_by_ids(db: AsyncSession, team_id: int, player_ids: list[int]) -> list[Player]:
    result = await db.execute(
        select(Player).where(Player.team_id == team_id, Player.id.in_(player_ids))
    )
    return result.scalars().all()


async def _load_recent_metrics(
    db: AsyncSession,
    team_id: int,
    player_ids: list[int],
    recent_matches: int,
) -> dict[int, dict]:
    match_res = await db.execute(
        select(Match.id)
        .where(
            Match.team_id == team_id,
            Match.status == MatchStatus.approved,
            Match.match_type == MatchType.external,
            Match.deleted_at.is_(None),
        )
        .order_by(desc(Match.match_date))
        .limit(recent_matches)
    )
    match_ids = [mid for (mid,) in match_res]
    if not match_ids:
        return {}
    stats_res = await db.execute(
        select(MatchPlayer).where(
            MatchPlayer.match_id.in_(match_ids),
            MatchPlayer.player_id.in_(player_ids),
            MatchPlayer.team_side == TeamSide.A,
        )
    )
    metrics: dict[int, dict] = {}
    for row in stats_res.scalars().all():
        item = metrics.setdefault(row.player_id, {"goals": 0, "assists": 0, "pm": 0, "turnovers": 0, "matches": 0})
        item["goals"] += row.goals or 0
        item["assists"] += row.assists or 0
        item["pm"] += row.plus_minus or 0
        item["turnovers"] += row.turnovers or 0
        item["matches"] += 1
    return metrics


async def _load_chemistry_pairs(db: AsyncSession, team_id: int, players: list[Player]) -> dict[tuple[int, int], dict]:
    player_ids = [player.id for player in players]
    if len(player_ids) < 2:
        return {}
    chem_res = await db.execute(
        select(PlayerChemistry).where(
            PlayerChemistry.team_id == team_id,
            PlayerChemistry.player_a_id.in_(player_ids),
            PlayerChemistry.player_b_id.in_(player_ids),
        )
    )
    names = {player.id: (player.display_name or player.username) for player in players}
    pair_map: dict[tuple[int, int], dict] = {}
    for row in chem_res.scalars().all():
        key = tuple(sorted((row.player_a_id, row.player_b_id)))
        pair_map[key] = {
            "player_a_id": key[0],
            "player_b_id": key[1],
            "player_a_name": names.get(key[0], f"#{key[0]}"),
            "player_b_name": names.get(key[1], f"#{key[1]}"),
            "chemistry_score": round(float(row.chemistry_score or 0.0), 3),
            "combo_count": int(row.combo_count or 0),
            "co_matches": int(row.co_matches or 0),
        }
    return pair_map


def _average_player_chemistry(player_id: int, pair_map: dict[tuple[int, int], dict]) -> float:
    values = [item["chemistry_score"] for key, item in pair_map.items() if player_id in key]
    if not values:
        return 0.0
    return sum(values) / len(values)


def _pair_chemistry_score(pair_map: dict[tuple[int, int], dict], player_a_id: int, player_b_id: int) -> float:
    key = tuple(sorted((player_a_id, player_b_id)))
    return float(pair_map.get(key, {}).get("chemistry_score", 0.0))


def _build_player_feature_row(player: Player, recent: dict | None, chemistry_score: float) -> dict:
    recent = recent or {"goals": 0, "assists": 0, "pm": 0, "turnovers": 0, "matches": 0}
    matches = max(1, recent["matches"])
    goals_per_match = recent["goals"] / matches
    assists_per_match = recent["assists"] / matches
    pm_per_match = recent["pm"] / matches
    to_per_match = recent["turnovers"] / matches
    ability = max(0.0, float(player.conservative_rating))
    offense = max(0.0, assists_per_match * 12 + pm_per_match * 8 - to_per_match * 8)
    scoring = max(0.0, goals_per_match * 15)
    recent_form = max(0.0, goals_per_match * 10 + assists_per_match * 8 + pm_per_match * 6 - to_per_match * 6)
    chemistry = max(0.0, chemistry_score * 10)
    playmaking = max(0.0, assists_per_match * 15)
    defense = max(0.0, pm_per_match * 12 + (2.0 - to_per_match) * 6)
    turnover_control = max(0.0, 12 - to_per_match * 8)
    stability = max(0.0, turnover_control * 0.55 + recent_form * 0.45)
    total = ability * 0.35 + chemistry * 0.2 + offense * 0.15 + scoring * 0.15 + recent_form * 0.15
    # O line 优先级：得分(30%) + 稳定(28%) + 默契(20%) + 助攻(15%) + 能力(7%)
    o_line_score = scoring * 0.30 + stability * 0.28 + chemistry * 0.20 + playmaking * 0.15 + ability * 0.07
    # D line 优先级：防守(32%) + 低失误(27%) + 出盘(18%) + 默契(15%) + 能力(8%)
    d_line_score = defense * 0.32 + turnover_control * 0.27 + playmaking * 0.18 + chemistry * 0.15 + ability * 0.08
    return {
        "player_id": player.id,
        "player_name": player.username,
        "display_name": player.display_name,
        "gender": player.gender,
        "ability_score": round(ability, 2),
        "chemistry_score": round(chemistry, 2),
        "offense_score": round(offense, 2),
        "defense_score": round(defense, 2),
        "scoring_score": round(scoring, 2),
        "recent_form_score": round(recent_form, 2),
        "turnover_control_score": round(turnover_control, 2),
        "playmaking_score": round(playmaking, 2),
        "stability_score": round(stability, 2),
        "total_score": round(total, 2),
        "o_line_score": round(o_line_score, 2),
        "d_line_score": round(d_line_score, 2),
        "role_hint": assists_per_match - goals_per_match,
    }


def _build_line_specs(scored: list[dict], max_line_size: int, d_line_count: int) -> list[dict]:
    total_players = len(scored)
    if total_players < 3:
        return []

    # O line 固定容量 = max_line_size，D line 分配剩余
    o_line_size = min(max_line_size, total_players)
    remaining = total_players - o_line_size
    
    if d_line_count == 1:
        # 单条 D line 容纳所有剩余
        d_line_sizes = [remaining] if remaining > 0 else []
    else:
        # 双条 D line：先满足 D1 >= 7 人（如果可能），剩余分给 D2
        d1_min_target = 7
        if remaining >= d1_min_target + 1:  # D1 至少 7 人，D2 至少 1 人
            d1_size = max(d1_min_target, (remaining + 1) // 2)  # D1 尽量多但至少 7
            d2_size = remaining - d1_size
        elif remaining > 0:
            # 人数不足 14，尽量均分
            d1_size = (remaining + 1) // 2
            d2_size = remaining - d1_size
        else:
            d1_size, d2_size = 0, 0
        d_line_sizes = [d1_size, d2_size] if d1_size > 0 or d2_size > 0 else []

    line_specs = [{"line_name": "O Line", "line_type": "o_line", "size": o_line_size, "players": []}]
    for idx, size in enumerate(d_line_sizes):
        line_specs.append(
            {
                "line_name": f"D Line {idx + 1}" if d_line_count == 2 else "D Line",
                "line_type": "d_line",
                "size": size,
                "players": [],
            }
        )
    return line_specs


def _build_gender_targets(scored: list[dict], line_specs: list[dict]) -> None:
    total_slots = sum(spec["size"] for spec in line_specs)
    for gender in ("M", "F"):
        total_count = sum(1 for row in scored if row.get("gender") == gender)
        if total_count <= 0 or total_slots <= 0:
            continue
        raw_targets = [total_count * spec["size"] / total_slots for spec in line_specs]
        assigned = [int(math.floor(value)) for value in raw_targets]
        remainder = total_count - sum(assigned)
        if remainder > 0:
            ranked = sorted(
                range(len(line_specs)),
                key=lambda idx: (raw_targets[idx] - assigned[idx], -idx),
                reverse=True,
            )
            for idx in ranked[:remainder]:
                assigned[idx] += 1
        for idx, spec in enumerate(line_specs):
            spec.setdefault("gender_targets", {})[gender] = assigned[idx]


def _gender_need_bonus(spec: dict, row: dict) -> float:
    gender = row.get("gender")
    if gender not in {"M", "F"}:
        return 0.0
    target = spec.get("gender_targets", {}).get(gender)
    if target is None:
        return 0.0
    current_count = sum(1 for item in spec["players"] if item.get("gender") == gender)
    if current_count < target:
        return 8.0 + (target - current_count - 1) * 1.5
    return -4.0


def _score_line_fit(spec: dict, row: dict, pair_map: dict[tuple[int, int], dict]) -> float:
    profile_score = row["o_line_score"] if spec["line_type"] == "o_line" else row["d_line_score"]
    chemistry_scores = [
        _pair_chemistry_score(pair_map, row["player_id"], member["player_id"])
        for member in spec["players"]
    ]
    chemistry_weight = 16 if spec["line_type"] == "o_line" else 10
    chemistry_bonus = (sum(chemistry_scores) / len(chemistry_scores) * chemistry_weight) if chemistry_scores else 0.0
    return profile_score + chemistry_bonus + _gender_need_bonus(spec, row)


def _distribute_players_to_lines(
    scored: list[dict],
    pair_map: dict[tuple[int, int], dict],
    max_line_size: int,
    d_line_count: int,
) -> list[dict]:
    line_specs = _build_line_specs(scored, max_line_size, d_line_count)
    _build_gender_targets(scored, line_specs)

    # Round 1: O line takes highest o_line_score players
    o_line_spec = next((spec for spec in line_specs if spec["line_type"] == "o_line"), None)
    if o_line_spec:
        o_line_candidates = sorted(scored, key=lambda item: item["o_line_score"], reverse=True)
        for row in o_line_candidates:
            if len(o_line_spec["players"]) < o_line_spec["size"]:
                o_line_spec["players"].append(row)
    
    # Round 2: D line takes remaining players by d_line_score
    assigned_ids = {row["player_id"] for row in o_line_spec["players"]} if o_line_spec else set()
    remaining = [row for row in scored if row["player_id"] not in assigned_ids]
    
    d_line_specs = [spec for spec in line_specs if spec["line_type"] == "d_line"]
    for row in sorted(remaining, key=lambda item: item["d_line_score"], reverse=True):
        candidates = [spec for spec in d_line_specs if len(spec["players"]) < spec["size"]]
        if not candidates:
            continue
        best_spec = max(
            candidates,
            key=lambda spec: _score_line_fit(spec, row, pair_map),
        )
        best_spec["players"].append(row)
    
    return line_specs


def _assign_roles(players: list[dict], handler_ratio: int, cutter_ratio: int, line_type: str) -> list[dict]:
    if not players:
        return []
    role_players = sorted(players, key=lambda item: item["role_hint"], reverse=True)
    if line_type == "d_line":
        # D line 固定尽量保留 2 名可出盘 handler，满足防守后稳态推进
        handler_count = 2 if len(role_players) >= 4 else 1
    else:
        ratio_sum = max(1, handler_ratio + cutter_ratio)
        handler_count = max(1, round(len(role_players) * handler_ratio / ratio_sum))
    handler_ids = {item["player_id"] for item in role_players[:handler_count]}
    rows = []
    for item in players:
        role = "handler" if item["player_id"] in handler_ids else "cutter"
        reason = (
            ("组织与控盘指标更优，适合作为 O line handler" if line_type == "o_line" else "控盘稳定性与转移能力更优，适合作为 D line handler")
            if role == "handler"
            else ("终结与冲击分更高，适合作为 O line cutter" if line_type == "o_line" else "防守覆盖与回盘压迫更优，适合作为 D line cutter")
        )
        rows.append({**item, "role": role, "reason": reason})
    return rows


def _build_line_chemistry_pairs(rows: list[dict], pair_map: dict[tuple[int, int], dict]) -> list[dict]:
    details: list[dict] = []
    player_ids = [row["player_id"] for row in rows]
    for idx, player_a_id in enumerate(player_ids):
        for player_b_id in player_ids[idx + 1:]:
            key = tuple(sorted((player_a_id, player_b_id)))
            pair = pair_map.get(key)
            if not pair:
                continue
            details.append(
                {
                    **pair,
                    "summary": (
                        f"{pair['player_a_name']} + {pair['player_b_name']}：默契 {pair['chemistry_score']:.2f}，"
                        f"同场 {pair['co_matches']} 次，配合得分 {pair['combo_count']} 次"
                    ),
                }
            )
    details.sort(key=lambda item: item["chemistry_score"], reverse=True)
    return details


def _serialize_smart_line(line_name: str, line_type: str, rows: list[dict], pair_map: dict[tuple[int, int], dict]) -> dict:
    chemistry_pairs = _build_line_chemistry_pairs(rows, pair_map)
    chemistry_average = 0.0
    if chemistry_pairs:
        chemistry_average = round(
            sum(item["chemistry_score"] for item in chemistry_pairs) / len(chemistry_pairs),
            3,
        )
    return {
        "line_name": line_name,
        "line_type": line_type,
        "total_score": round(sum(item["total_score"] for item in rows), 2),
        "chemistry_average": chemistry_average,
        "player_ids": [item["player_id"] for item in rows],
        "players": [
            {
                "player_id": item["player_id"],
                "player_name": item["player_name"],
                "display_name": item["display_name"],
                "gender": item.get("gender"),
                "role": item["role"],
                "ability_score": item["ability_score"],
                "chemistry_score": item["chemistry_score"],
                "offense_score": item["offense_score"],
                "defense_score": item.get("defense_score", 0.0),
                "scoring_score": item["scoring_score"],
                "recent_form_score": item["recent_form_score"],
                "total_score": item["total_score"],
                "reason": item["reason"],
            }
            for item in rows
        ],
        "chemistry_pairs": chemistry_pairs,
    }


async def _ensure_division(db: AsyncSession, event_id: int) -> ScheduleLineDivision:
    div = await _get_division(db, event_id)
    if div:
        return div
    div = ScheduleLineDivision(
        event_id=event_id,
        division_method=DivisionMethod.manual,
        total_rounds=1,
    )
    db.add(div)
    await db.flush()
    return div


async def _run_assigned_line_analysis(
    db: AsyncSession,
    team_id: int,
    body: ManualLineAnalyzeRequest,
) -> dict:
    """
    对已知 Line 分组（手动调整结果）运行与智能分析相同的算法：
    - 使用真实近期战绩计算各维度评分
    - 使用真实双人默契数据（PlayerChemistry）
    - 返回与 SmartLineAnalyzeResponse 完全相同的格式
    """
    # 收集全部正式球员 ID（过滤 guest 负数 ID）
    all_player_ids = list(dict.fromkeys(
        pid for line_input in body.lines for pid in line_input.player_ids if pid > 0
    ))
    if not all_player_ids:
        raise HTTPException(status_code=400, detail="未找到有效球员 ID（guest 球员不参与计算）")

    players = await _load_players_by_ids(db, team_id, all_player_ids)
    player_map: dict[int, Player] = {p.id: p for p in players}

    # 全局近期战绩 & 默契数据
    recent_map = await _load_recent_metrics(db, team_id, all_player_ids, body.recent_matches)
    global_pair_map = await _load_chemistry_pairs(db, team_id, players)

    serialized_lines: list[dict] = []
    o_line_serialized: dict | None = None
    d_lines_serialized: list[dict] = []

    for line_input in body.lines:
        # 只处理在本队 DB 中存在的球员
        valid_pids = [pid for pid in line_input.player_ids if pid > 0 and pid in player_map]
        line_players = [player_map[pid] for pid in valid_pids]

        # 计算各球员特征行（chemistry 基于全局 pair_map，与智能分析保持一致）
        scored = [
            _build_player_feature_row(
                player,
                recent_map.get(player.id),
                _average_player_chemistry(player.id, global_pair_map),
            )
            for player in line_players
        ]

        # 分配 handler / cutter 角色
        role_rows = _assign_roles(scored, body.handler_ratio, body.cutter_ratio, line_input.line_type)

        # 序列化（汇总文本、两两默契等全部由 _serialize_smart_line 统一处理）
        serialized = _serialize_smart_line(line_input.line_name, line_input.line_type, role_rows, global_pair_map)
        serialized_lines.append(serialized)

        if line_input.line_type == "o_line":
            o_line_serialized = serialized
        else:
            d_lines_serialized.append(serialized)

    # 兜底：如果没有明确 o_line，使用第一条 line
    if o_line_serialized is None and serialized_lines:
        o_line_serialized = serialized_lines[0]
        d_lines_serialized = serialized_lines[1:]

    if o_line_serialized is None:
        raise HTTPException(status_code=400, detail="请提供至少一条 Line 数据")

    male_count = sum(1 for p in players if p.gender == "M")
    female_count = sum(1 for p in players if p.gender == "F")

    return {
        "event_id": None,
        "applied_to_match": False,
        "lines": serialized_lines,
        "o_line": o_line_serialized,
        "d_lines": d_lines_serialized,
        "rationale": {
            "description": "基于当前手动分 Line 配置，使用与智能分析完全相同的算法计算各维度评分",
            "recent_matches_window": body.recent_matches,
            "from_local": True,
            "gender_distribution": {
                "male": male_count,
                "female": female_count,
                "unknown": len(players) - male_count - female_count,
            },
        },
    }


async def _run_smart_external_line_analysis(
    db: AsyncSession,
    team_id: int,
    body: SmartLineAnalyzeRequest,
    event: ScheduleEvent | None,
) -> dict:
    player_ids = list(dict.fromkeys(body.player_ids or []))
    if not player_ids and event is not None:
        player_ids = await _load_attendance_yes_ids(db, event.id)
    if len(player_ids) < 7:
        raise HTTPException(status_code=400, detail="至少需要 7 名队员进行 O/D 分线")

    players = await _load_players_by_ids(db, team_id, player_ids)
    if len(players) < 7:
        raise HTTPException(status_code=400, detail="有效队员不足 7 人")
    if len(players) < 1 + body.d_line_count:
        raise HTTPException(status_code=400, detail="队员数量不足以覆盖 O line + D line")

    recent_map = await _load_recent_metrics(db, team_id, [p.id for p in players], body.recent_matches)
    pair_map = await _load_chemistry_pairs(db, team_id, players)

    scored = [
        _build_player_feature_row(
            player,
            recent_map.get(player.id),
            _average_player_chemistry(player.id, pair_map),
        )
        for player in players
    ]

    line_specs = _distribute_players_to_lines(scored, pair_map, body.max_line_size, body.d_line_count)
    serialized_lines: list[dict] = []
    o_line_rows: list[dict] = []
    d_line_rows: list[list[dict]] = []
    for spec in line_specs:
        role_rows = _assign_roles(spec["players"], body.handler_ratio, body.cutter_ratio, spec["line_type"])
        serialized = _serialize_smart_line(spec["line_name"], spec["line_type"], role_rows, pair_map)
        serialized_lines.append(serialized)
        if spec["line_type"] == "o_line":
            o_line_rows = role_rows
        else:
            d_line_rows.append(role_rows)

    applied = False
    if body.apply_to_match and event is not None:
        div = await _ensure_division(db, event.id)
        await _apply_smart_lines_to_division(db, div, o_line_rows, d_line_rows)
        applied = True

    male_count = sum(1 for player in players if player.gender == "M")
    female_count = sum(1 for player in players if player.gender == "F")
    return {
        "event_id": event.id if event is not None else body.schedule_event_id,
        "applied_to_match": applied,
        "lines": serialized_lines,
        "o_line": next(line for line in serialized_lines if line["line_type"] == "o_line"),
        "d_lines": [line for line in serialized_lines if line["line_type"] == "d_line"],
        "rationale": {
            "weights": {
                "ability": 0.35,
                "chemistry": 0.2,
                "offense": 0.15,
                "scoring": 0.15,
                "recent_form": 0.15,
            },
            "recent_matches_window": body.recent_matches,
            "max_line_size": body.max_line_size,
            "d_line_count": body.d_line_count,
            "o_line_size": len(o_line_rows),
            "d_line_sizes": [len(rows) for rows in d_line_rows],
            "gender_distribution": {
                "male": male_count,
                "female": female_count,
                "unknown": len(players) - male_count - female_count,
            },
            "description": "O line 优先得分、助攻、稳定与两两默契；D line 优先防守压迫与回盘能力，并保留 2 名可出盘 handler（小阵容降为 1 名）。",
        },
    }


async def _apply_smart_lines_to_division(
    db: AsyncSession,
    div: ScheduleLineDivision,
    o_line_rows: list[dict],
    d_line_rows: list[list[dict]],
) -> None:
    old_lines = await db.execute(
        select(ScheduleLine).where(
            ScheduleLine.division_id == div.id,
            ScheduleLine.round_number == 1,
        )
    )
    for line in old_lines.scalars().all():
        await db.delete(line)
    await db.flush()

    all_rows = [("O Line", LineType.o_line, o_line_rows)]
    if len(d_line_rows) == 1:
        all_rows.append(("D Line", LineType.d_line, d_line_rows[0]))
    else:
        for idx, rows in enumerate(d_line_rows, start=1):
            all_rows.append((f"D Line {idx}", LineType.d_line, rows))
    for order_index, (line_name, line_type, rows) in enumerate(all_rows):
        line = ScheduleLine(
            division_id=div.id,
            line_name=line_name,
            line_type=line_type,
            round_number=1,
            order_index=order_index,
        )
        db.add(line)
        await db.flush()
        for row in rows:
            db.add(ScheduleLinePlayer(line_id=line.id, player_id=row["player_id"]))
    div.division_method = DivisionMethod.auto_balanced
    div.updated_at = datetime.now(timezone.utc)
    await db.commit()

async def _require_event(db: AsyncSession, event_id: int, team_id: int) -> ScheduleEvent:
    res = await db.execute(
        select(ScheduleEvent).where(ScheduleEvent.id == event_id, ScheduleEvent.team_id == team_id)
    )
    ev = res.scalar_one_or_none()
    if not ev:
        raise HTTPException(status_code=404, detail="日程不存在")
    return ev


async def _get_division(db: AsyncSession, event_id: int) -> ScheduleLineDivision | None:
    res = await db.execute(
        select(ScheduleLineDivision).where(ScheduleLineDivision.event_id == event_id)
    )
    return res.scalar_one_or_none()


async def _require_division(db: AsyncSession, event_id: int) -> ScheduleLineDivision:
    div = await _get_division(db, event_id)
    if not div:
        raise HTTPException(status_code=404, detail="请先创建分 line 方案")
    return div


def _ensure_template_supported(ev: ScheduleEvent) -> None:
    if ev.event_type not in (ScheduleEventType.game, ScheduleEventType.training):
        raise HTTPException(status_code=400, detail="当前仅外战和训练支持模板")


async def _require_template(
    db: AsyncSession,
    template_id: int,
    team_id: int,
    event_type: ScheduleEventType,
) -> ScheduleLineTemplate:
    result = await db.execute(
        select(ScheduleLineTemplate).where(
            ScheduleLineTemplate.id == template_id,
            ScheduleLineTemplate.team_id == team_id,
            ScheduleLineTemplate.event_type == event_type,
        )
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")
    return template


async def _require_line(db: AsyncSession, line_id: int, event_id: int) -> ScheduleLine:
    div = await _get_division(db, event_id)
    if not div:
        raise HTTPException(status_code=404, detail="分 line 方案不存在")
    res = await db.execute(
        select(ScheduleLine).where(ScheduleLine.id == line_id, ScheduleLine.division_id == div.id)
    )
    line = res.scalar_one_or_none()
    if not line:
        raise HTTPException(status_code=404, detail="Line 不存在")
    return line


async def _check_round_uniqueness(db: AsyncSession, line: ScheduleLine, player_id: int, event_id: int) -> None:
    """内战：同轮内同一球员不能出现在多条 line"""
    div = await db.get(ScheduleLineDivision, line.division_id)
    if not div:
        return
    # 获取同轮的所有其他 line
    sibling_lines = await db.execute(
        select(ScheduleLine).where(
            ScheduleLine.division_id == div.id,
            ScheduleLine.round_number == line.round_number,
            ScheduleLine.id != line.id,
        )
    )
    sibling_ids = [sibling_line.id for sibling_line in sibling_lines.scalars().all()]
    if not sibling_ids:
        return

    dup = await db.execute(
        select(ScheduleLinePlayer).where(
            ScheduleLinePlayer.line_id.in_(sibling_ids),
            ScheduleLinePlayer.player_id == player_id,
        )
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该球员在本轮其他 line 中已存在（内战同轮不可重复）")


async def _build_line_read(db: AsyncSession, line: ScheduleLine) -> ScheduleLineRead:
    lp_res = await db.execute(
        select(ScheduleLinePlayer).where(ScheduleLinePlayer.line_id == line.id)
    )
    lps = lp_res.scalars().all()
    player_ids = [lp.player_id for lp in lps]
    players: list[LinePlayerInfo] = []
    if player_ids:
        p_res = await db.execute(select(Player).where(Player.id.in_(player_ids)))
        for p in p_res.scalars().all():
            players.append(LinePlayerInfo(
                player_id=p.id,
                player_name=p.username,
                display_name=p.display_name,
                conservative_rating=p.conservative_rating,
                gender=getattr(p, 'gender', None),
                jersey_number=getattr(p, 'jersey_number', None),
            ))
    return ScheduleLineRead(
        id=line.id,
        line_name=line.line_name,
        line_type=_enum_value(line.line_type),
        round_number=line.round_number,
        order_index=line.order_index,
        players=players,
    )


def _build_template_read(template: ScheduleLineTemplate) -> ScheduleLineTemplateRead:
    try:
        payload = json.loads(template.payload_json or "[]")
    except json.JSONDecodeError:
        payload = []
    return ScheduleLineTemplateRead(
        id=template.id,
        event_type=_enum_value(template.event_type),
        template_name=template.template_name,
        line_count=len(payload) if isinstance(payload, list) else 0,
        updated_at=template.updated_at,
    )


async def _build_division_read(db: AsyncSession, div: ScheduleLineDivision) -> ScheduleLineDivisionRead:
    lines_res = await db.execute(
        select(ScheduleLine)
        .where(ScheduleLine.division_id == div.id)
        .order_by(ScheduleLine.round_number, ScheduleLine.order_index)
    )
    lines = lines_res.scalars().all()

    line_reads: list[ScheduleLineRead] = []
    if lines:
        # Batch-fetch all line-player records for all lines in one query
        line_ids = [line.id for line in lines]
        lp_res = await db.execute(
            select(ScheduleLinePlayer).where(ScheduleLinePlayer.line_id.in_(line_ids))
        )
        all_lps = lp_res.scalars().all()

        # Group by line_id
        lp_by_line: dict[int, list[ScheduleLinePlayer]] = {}
        for lp in all_lps:
            lp_by_line.setdefault(lp.line_id, []).append(lp)

        # Batch-fetch all players in one query
        all_player_ids = list({lp.player_id for lp in all_lps})
        player_map: dict[int, Player] = {}
        if all_player_ids:
            p_res = await db.execute(select(Player).where(Player.id.in_(all_player_ids)))
            player_map = {p.id: p for p in p_res.scalars().all()}

        for line in lines:
            lps = lp_by_line.get(line.id, [])
            players = []
            for lp in lps:
                p = player_map.get(lp.player_id)
                if p:
                    players.append(LinePlayerInfo(
                        player_id=p.id,
                        player_name=p.username,
                        display_name=p.display_name,
                        conservative_rating=p.conservative_rating,
                        gender=getattr(p, 'gender', None),
                        jersey_number=getattr(p, 'jersey_number', None),
                    ))
            line_reads.append(ScheduleLineRead(
                id=line.id,
                line_name=line.line_name,
                line_type=_enum_value(line.line_type),
                round_number=line.round_number,
                order_index=line.order_index,
                players=players,
            ))

    return ScheduleLineDivisionRead(
        id=div.id,
        event_id=div.event_id,
        division_method=_enum_value(div.division_method),
        total_rounds=div.total_rounds,
        lines=line_reads,
    )
