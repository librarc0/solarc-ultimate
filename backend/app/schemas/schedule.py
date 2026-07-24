"""日程模块 Pydantic Schemas"""
from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel, Field


# ─── Schedule Event ────────────────────────────────────────────────────────────

class ScheduleEventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    event_type: str = Field(..., pattern="^(game|training|internal|other)$")
    start_date: date
    end_date: date
    description: str | None = Field(default=None, max_length=2000)

    def model_post_init(self, __context: object) -> None:
        if self.end_date < self.start_date:
            raise ValueError("end_date 不能早于 start_date")


class ScheduleEventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    event_type: str | None = Field(default=None, pattern="^(game|training|internal|other)$")
    start_date: date | None = None
    end_date: date | None = None
    description: str | None = None


class ScheduleEventRead(BaseModel):
    id: int
    team_id: int
    title: str
    event_type: str
    start_date: date
    end_date: date
    description: str | None
    status: str
    created_by: int
    linked_match_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScheduleEventListItem(BaseModel):
    """日历中每个日程的简要信息（用于日历格点展示）"""
    id: int
    title: str
    event_type: str
    start_date: date
    end_date: date
    status: str
    linked_match_id: int | None
    attendance_count: int = 0    # 已提交出勤数
    total_players: int = 0       # 队伍总人数
    yes_count: int = 0
    sdl_count: int = 0
    leave_count: int = 0
    no_count: int = 0
    not_submitted_count: int = 0

    model_config = {"from_attributes": True}


# ─── Attendance ────────────────────────────────────────────────────────────────

class AttendanceSubmit(BaseModel):
    status: str = Field(..., pattern="^(yes|leave|sdl)$")


class AttendanceRead(BaseModel):
    id: int
    event_id: int
    player_id: int
    player_name: str
    player_display_name: str | None
    status: str
    submitted_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AttendanceSummary(BaseModel):
    """管理员查看出勤汇总"""
    event_id: int
    yes: list[AttendanceRead] = []
    leave: list[AttendanceRead] = []
    sdl: list[AttendanceRead] = []
    not_submitted: list[dict] = []  # {"player_id": int, "player_name": str}


# ─── Line Division ─────────────────────────────────────────────────────────────

class LinePlayerInfo(BaseModel):
    player_id: int
    player_name: str
    display_name: str | None
    conservative_rating: float
    gender: str | None = None
    jersey_number: int | None = None

    model_config = {"from_attributes": True}


class ScheduleLineRead(BaseModel):
    id: int
    line_name: str
    line_type: str
    round_number: int
    order_index: int
    players: list[LinePlayerInfo] = []

    model_config = {"from_attributes": True}


class ScheduleLineDivisionRead(BaseModel):
    id: int
    event_id: int
    division_method: str
    total_rounds: int
    lines: list[ScheduleLineRead] = []

    model_config = {"from_attributes": True}


class DivisionCreate(BaseModel):
    """创建/重置分 line 方案"""
    division_method: str = Field(default="manual", pattern="^(manual|auto_balanced|auto_strong_to_weak)$")
    total_rounds: int = Field(default=1, ge=1, le=10)


class DivisionUpdate(BaseModel):
    """更新分 line 方案轮数（仅支持增加）"""
    total_rounds: int = Field(..., ge=1, le=10)


class LineCreate(BaseModel):
    """在方案下新建一条 line"""
    line_name: str = Field(..., min_length=1, max_length=50)
    line_type: str = Field(default="line", pattern="^(o_line|d_line|line)$")
    round_number: int = Field(default=1, ge=1)
    order_index: int = Field(default=0, ge=0)


class LineUpdate(BaseModel):
    line_name: str | None = Field(default=None, min_length=1, max_length=50)
    line_type: str | None = Field(default=None, pattern="^(o_line|d_line|line)$")
    order_index: int | None = None


class LinePlayerAdd(BaseModel):
    player_id: int


class AutoAssignRequest(BaseModel):
    """自动分line请求"""
    method: str = Field(..., pattern="^(auto_balanced|auto_strong_to_weak)$")
    num_lines: int = Field(..., ge=1, le=8)
    round_number: int = Field(default=1, ge=1)
    # 仅包含这些球员（可以是 yes + sdl + leave），不传则取出勤为 yes 的
    player_ids: list[int] | None = None


class ScheduleLineTemplateSave(BaseModel):
    template_name: str = Field(..., min_length=1, max_length=50)


class ScheduleLineTemplateRead(BaseModel):
    id: int
    event_type: str
    template_name: str
    line_count: int = 0
    updated_at: datetime

    model_config = {"from_attributes": True}


class SmartLineAnalyzeRequest(BaseModel):
    player_ids: list[int] = []
    schedule_event_id: int | None = None
    apply_to_match: bool = False
    max_line_size: int = Field(default=7, ge=3, le=20)
    d_line_count: int = Field(default=1, ge=1, le=2)
    handler_ratio: int = Field(default=3, ge=1, le=5)
    cutter_ratio: int = Field(default=4, ge=1, le=6)
    recent_matches: int = Field(default=6, ge=3, le=20)


class ManualLineInput(BaseModel):
    line_name: str
    line_type: str  # "o_line" | "d_line" | "line"
    player_ids: list[int]


class ManualLineAnalyzeRequest(BaseModel):
    lines: list[ManualLineInput]
    recent_matches: int = Field(default=6, ge=3, le=20)
    handler_ratio: int = Field(default=3, ge=1, le=5)
    cutter_ratio: int = Field(default=4, ge=1, le=6)


class SmartLinePlayerRead(BaseModel):
    player_id: int
    player_name: str
    display_name: str | None
    gender: str | None = None
    role: str
    ability_score: float
    chemistry_score: float
    offense_score: float
    scoring_score: float
    recent_form_score: float
    total_score: float
    reason: str


class SmartLineChemistryPairRead(BaseModel):
    player_a_id: int
    player_b_id: int
    player_a_name: str
    player_b_name: str
    chemistry_score: float
    combo_count: int
    co_matches: int
    summary: str


class SmartLineGroupRead(BaseModel):
    line_name: str
    line_type: str
    total_score: float
    chemistry_average: float = 0.0
    player_ids: list[int]
    players: list[SmartLinePlayerRead]
    chemistry_pairs: list[SmartLineChemistryPairRead] = []


class SmartLineAnalyzeResponse(BaseModel):
    event_id: int | None = None
    applied_to_match: bool = False
    lines: list[SmartLineGroupRead] = []
    o_line: SmartLineGroupRead
    d_lines: list[SmartLineGroupRead]
    rationale: dict


# ─── Used by MatchInputView to fetch schedule info for linking ──────────────────

class ScheduleForMatchLink(BaseModel):
    """新建比赛时可选关联的日程信息（精简）"""
    id: int
    title: str
    event_type: str
    start_date: date
    rounds: list[int] = []                   # 内战：可用轮次列表
    lines_by_round: dict[int, list[ScheduleLineRead]] = {}  # 内战：每轮 line 列表

    model_config = {"from_attributes": True}
