from datetime import datetime
from typing import Optional
from pydantic import BaseModel


# ────────────────────────────────────────
# 赛季 Schema
# ────────────────────────────────────────

class SeasonCreate(BaseModel):
    name: str
    year: int
    start_date: Optional[str] = None   # YYYY-MM-DD
    end_date: Optional[str] = None
    description: Optional[str] = None


class SeasonUpdate(BaseModel):
    name: Optional[str] = None
    year: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class SeasonOut(BaseModel):
    id: int
    name: str
    year: int
    start_date: Optional[str]
    end_date: Optional[str]
    description: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ────────────────────────────────────────
# 输入 JSON 格式（来自 Ultimate-Frisbee-Scorecard 导出）
# ────────────────────────────────────────

class TournamentRecordInput(BaseModel):
    tournamentName: str
    level: str          # National | Provincial | Local
    month: str          # YYYY-MM
    wins: int
    losses: int
    draws: int
    forfeits: int
    totalGames: int
    winRate: float
    pointsScored: int
    pointsConceded: int
    pool: str           # A | B | C | NoPool
    rank: int
    score: float        # 由工具侧已计算好的积分


class TeamRankingInput(BaseModel):
    name: str
    rank: int | None = None   # 可选；不提供时由系统按 totalScore 自动排序分配
    province: Optional[str] = None   # ISO 3166-2 省级代码, e.g. CN-SH
    city: Optional[str] = None       # ISO 3166-2 市级代码, e.g. CN-GD-GZ
    totalScore: float
    avgScore: float
    tournamentCount: int
    wins: int
    losses: int
    draws: int
    forfeits: int
    totalGames: int
    winRate: float
    pointsScored: int
    pointsConceded: int
    netPoints: int
    tournaments: list[TournamentRecordInput]


class SeasonMeta(BaseModel):
    """JSON 导出中可选包含的赛季元信息（仅作元数据，实际入库以 season_id 为准）"""
    year: int
    name: str


class RankingsExportPayload(BaseModel):
    exportedAt: str
    version: str = "1.0"
    source: str = "Ultimate-Frisbee-Scorecard"
    season: Optional[SeasonMeta] = None   # 可选：赛季元信息
    rankings: list[TeamRankingInput]


# ────────────────────────────────────────
# API 响应格式
# ────────────────────────────────────────

class TournamentRecordOut(BaseModel):
    id: int
    tournament_name: str
    level: str
    month: str
    wins: int
    losses: int
    draws: int
    forfeits: int
    total_games: int
    win_rate: float
    points_scored: int
    points_conceded: int
    pool: str
    final_rank: int
    computed_score: float

    model_config = {"from_attributes": True}


class ExternalTeamListItem(BaseModel):
    id: int
    season_id: Optional[int] = None
    name: str
    rank: int
    rank_change: int
    total_score: float
    avg_score: float
    tournament_count: int
    wins: int
    losses: int
    draws: int
    total_games: int
    win_rate: float
    points_scored: int
    points_conceded: int
    net_points: int
    province: Optional[str] = None
    city: Optional[str] = None
    last_updated: datetime

    model_config = {"from_attributes": True}


class ExternalTeamDetail(ExternalTeamListItem):
    forfeits: int
    prev_rank: int
    tournament_records: list[TournamentRecordOut] = []

    model_config = {"from_attributes": True}


class ExternalTeamForMatch(BaseModel):
    """外战录入专用精简格式"""
    name: str
    total_score: float
    rank: int

    model_config = {"from_attributes": True}


class UploadBatchOut(BaseModel):
    id: int
    season_id: Optional[int] = None
    uploaded_at: datetime
    source: str
    notes: Optional[str]
    record_count: int
    exported_at: Optional[str]

    model_config = {"from_attributes": True}


class ApiKeyOut(BaseModel):
    id: int
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime
    last_used_at: Optional[datetime]
    season_id: Optional[int] = None
    season_name: Optional[str] = None     # 展示用，由接口拼接

    model_config = {"from_attributes": True}


class ApiKeyCreated(ApiKeyOut):
    """仅在创建时返回完整 key，之后不再展示"""
    full_key: str


class RankingAdminToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UploadResult(BaseModel):
    teams_processed: int
    batch_id: int
    season_id: int | None = None   # 实际入库的赛季 ID（auto_create_season 时由服务端决定）
    season_name: str | None = None  # 赛季名称，便于前端展示
    message: str
