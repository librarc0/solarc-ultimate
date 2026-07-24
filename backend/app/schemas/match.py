from datetime import date
from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    """比赛时间轴事件（随 POST /matches 一起提交）"""
    event_type: str  # goal | assist | defense | halftime | start | end
    team_side: str | None = None  # A | B
    player_id: int | None = None
    assist_player_id: int | None = None
    is_break: bool | None = None
    elapsed_seconds: int | None = None


class MatchPlayerEntry(BaseModel):
    player_id: int
    goals: int | None = Field(None, ge=0, le=99)
    assists: int | None = Field(None, ge=0, le=99)
    defenses: int | None = Field(None, ge=0, le=99)  # 防守次数
    turnovers: int | None = Field(None, ge=0, le=99)
    is_mvp: bool = False


class MatchCreate(BaseModel):
    match_date: date
    match_type: str          # "internal" | "external"
    score_us: int = Field(ge=0, le=999)
    score_them: int = Field(ge=0, le=999)
    data_level: int = Field(default=1, ge=0, le=3)
    team_a: list[MatchPlayerEntry]
    team_b: list[MatchPlayerEntry]
    opponent_strength: int | None = Field(default=None, ge=1, le=10)
    opponent_name: str | None = Field(default=None, max_length=100)
    opponent_external_team_id: int | None = None
    opponent_calibrated_mu: float | None = None
    opponent_calibrated_sigma: float | None = None
    notes: str | None = Field(default=None, max_length=500)
    events: list[EventCreate] = []
    schedule_event_id: int | None = None   # 关联日程活动（可选）


class MatchResponse(BaseModel):
    id: int
    status: str
    message: str
    requested_level: int | None = None
    applied_level: int | None = None


class MatchUpdate(BaseModel):
    """PUT /matches/{id} — admin 审批或修改"""
    action: str  # "approve" | "reject" | "edit"
    score_us: int | None = None
    score_them: int | None = None
    team_a: list[MatchPlayerEntry] | None = None
    team_b: list[MatchPlayerEntry] | None = None
    data_level: int | None = Field(default=None, ge=0, le=3)
    opponent_strength: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = Field(default=None, max_length=500)


class DraftCreate(BaseModel):
    match_date: date
    match_type: str
    team_a_ids: list[int]
    team_b_ids: list[int] = []
    data_level: int = Field(default=3, ge=0, le=3)
    opponent_strength: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = None


class DraftEventCreate(BaseModel):
    client_event_id: str
    seq: int = Field(ge=1)
    event_type: str
    team_side: str | None = None
    player_id: int | None = None
    assist_player_id: int | None = None
    is_break: bool | None = None
    elapsed_seconds: int | None = Field(default=None, ge=0)
    payload: dict | None = None


class DraftSaveRequest(BaseModel):
    elapsed_seconds: int | None = Field(default=None, ge=0)
    score_a: int | None = Field(default=None, ge=0)
    score_b: int | None = Field(default=None, ge=0)
    is_halftime: bool | None = None
    possession: str | None = None


class DraftFinalizeRequest(BaseModel):
    notes: str | None = None


class DraftMatchItem(BaseModel):
    id: int
    match_type: str
    match_date: str
    team_a_score: int
    team_b_score: int
    status: str
    data_level: int
    notes: str | None = None
    duration_seconds: int | None = None
    expires_at: str | None = None
    countdown_seconds: int | None = None


class DraftEventResponse(BaseModel):
    id: int
    seq: int
    event_type: str
    team_side: str | None = None
    player_id: int | None = None
    assist_player_id: int | None = None
    is_break: bool | None = None
    elapsed_seconds: int | None = None
    payload: dict | None = None


class DraftDetailResponse(BaseModel):
    id: int
    match_type: str
    match_date: str
    team_a_ids: list[int]
    team_b_ids: list[int]
    team_a_score: int
    team_b_score: int
    status: str
    data_level: int
    notes: str | None = None
    duration_seconds: int | None = None
    last_event_seq: int
    expires_at: str | None = None
    snapshot: dict | None = None
    events: list[DraftEventResponse]


class DraftLockResponse(BaseModel):
    ok: bool


class DraftHeartbeatResponse(BaseModel):
    ok: bool
    lock_expires_in_seconds: int
    lock_lease_seconds: int


class DraftTakeoverResponse(BaseModel):
    ok: bool
    takeover: bool
    message: str | None = None


class MatchListItem(BaseModel):
    id: int
    match_type: str
    match_date: str
    team_a_score: int
    team_b_score: int
    status: str
    data_level: int
    notes: str | None = None
    created_by_id: int | None = None
    created_by_name: str | None = None
    duration_seconds: int | None = None
    expires_at: str | None = None
    countdown_seconds: int | None = None
    lock_status: str
    lock_owner_id: int | None = None
    lock_owner_name: str | None = None
    lock_expires_in_seconds: int
    lock_lease_seconds: int
    spirit_scored: bool = False
    spirit_total_score: int | None = None


class SpiritScoreDimension(BaseModel):
    score: int = Field(ge=0, le=4)
    reasons: list[str] = []
    note: str | None = None


class SpiritScoreUpsert(BaseModel):
    rules: SpiritScoreDimension
    contact: SpiritScoreDimension
    fairness: SpiritScoreDimension
    attitude: SpiritScoreDimension
    communication: SpiritScoreDimension
    note: str | None = None


class SpiritScoreRead(BaseModel):
    rules: SpiritScoreDimension
    contact: SpiritScoreDimension
    fairness: SpiritScoreDimension
    attitude: SpiritScoreDimension
    communication: SpiritScoreDimension
    total_score: int
    note: str | None = None
    updated_by: int
    updated_at: str


class MatchParticipant(BaseModel):
    player_id: int
    player_name: str
    team_side: str
    goals: int | None = None
    assists: int | None = None
    defenses: int | None = None   # 防守次数
    turnovers: int | None = None
    plus_minus: int | None = None  # 正负值（得分差）
    is_mvp: bool = False
    mu_before: float | None = None
    sigma_before: float | None = None
    mu_after: float | None = None
    sigma_after: float | None = None


class MatchDetailResponse(BaseModel):
    id: int
    match_type: str
    match_date: str
    team_a_score: int
    team_b_score: int
    status: str
    data_level: int
    notes: str | None = None
    created_by_id: int
    created_by_name: str
    participants: list[MatchParticipant]
    spirit_score: SpiritScoreRead | None = None


class MatchEventItem(BaseModel):
    id: int
    event_type: str
    team_side: str | None = None
    player_id: int | None = None
    assist_player_id: int | None = None
    is_break: bool | None = None
    elapsed_seconds: int | None = None
