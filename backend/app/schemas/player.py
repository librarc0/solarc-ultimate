from pydantic import BaseModel

from app.models.player import PlayerStatus, UserRole


class PlayerPublic(BaseModel):
    id: int
    team_id: int | None = None
    username: str
    display_name: str | None = None
    email: str | None = None
    role: str
    status: str
    gender: str | None = None
    jersey_number: int | None = None
    is_superadmin: bool = False
    show_in_rankings: bool = True
    is_guest: bool = False
    mu: float
    sigma: float
    conservative_rating: float
    avatar_url: str | None = None
    total_matches: int
    total_wins: int
    total_goals: int
    total_assists: int
    total_defenses: int = 0
    total_plus_minus: int = 0
    total_turnovers: int = 0

    model_config = {"from_attributes": True}


class PlayerProfileUpdate(BaseModel):
    username: str | None = None
    display_name: str | None = None
    email: str | None = None
    gender: str | None = None
    jersey_number: int | None = None
    show_in_rankings: bool | None = None


# T052 [US6]: 双层字段更新请求模型
class UserLayerUpdate(BaseModel):
    """更新 User 层字段（全局生效）"""
    username: str | None = None           # 全局唯一用户名，3-20 位英文/数字/下划线


class PlayerLayerUpdate(BaseModel):
    """更新当前队伍 Player 层字段（仅当前队伍生效）"""
    display_name: str | None = None       # 队伍内昵称，最长 50 字
    email: str | None = None
    gender: str | None = None
    jersey_number: int | None = None
    show_in_rankings: bool | None = None


class DualLayerProfileUpdateRequest(BaseModel):
    """双层资料更新请求（user.username 全局 + player 队伍层字段）"""
    user: UserLayerUpdate | None = None
    player: PlayerLayerUpdate | None = None


class DualLayerProfileUpdateResponse(BaseModel):
    """双层资料更新响应"""
    user_username: str
    display_name: str | None
    email: str | None
    gender: str | None
    jersey_number: int | None
    show_in_rankings: bool


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


class PlayerStatusUpdate(BaseModel):
    status: PlayerStatus


class PlayerRoleUpdate(BaseModel):
    role: UserRole


class RankingItem(BaseModel):
    rank: int
    player_id: int
    display_name: str | None = None
    gender: str | None = None
    jersey_number: int | None = None
    rank_change: int | None = None  # 正数=上升，负数=下降，None=无历史可比
    conservative_rating: float
    mu: float = 0.0
    sigma: float = 0.0
    total_matches: int
    total_wins: int
    total_goals: int = 0
    total_assists: int = 0
    total_defenses: int = 0
    total_plus_minus: int = 0
    total_turnovers: int = 0
    is_new: bool = False  # True if total_matches < 5
    composite_score: float = 0.0  # 综合战力分
    attendance_rate: float = 0.0  # 出勤率（0-100）
    progress_speed: float = 0.0   # MIP 四维复合进步分（归一化 [0,1]，完整赛季或全历史）


class ChemistryItem(BaseModel):
    rank: int
    player_a_id: int
    player_b_id: int
    player_a_name: str | None = None
    player_b_name: str | None = None
    player_a_jersey: int | None = None
    player_b_jersey: int | None = None
    chemistry_score: float
    co_matches: int
    co_wins: int
    combo_count: int


class RankingResponse(BaseModel):
    items: list[RankingItem]
    page: int
    page_size: int


class ChemistryResponse(BaseModel):
    items: list[ChemistryItem]
    page: int
    page_size: int


class PlayerPanelBasic(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    role: str
    mu: float
    sigma: float
    conservative_rating: float
    total_matches: int
    total_wins: int
    total_goals: int
    total_assists: int


class PlayerPanelHistoryItem(BaseModel):
    match_id: int
    mu_before: float
    mu_after: float
    delta_mu: float
    conservative_after: float
    created_at: str


class PlayerPanelRecentMatchItem(BaseModel):
    match_id: int
    team_side: str
    goals: int | None = None
    assists: int | None = None
    defenses: int | None = None   # 防守次数
    plus_minus: int | None = None  # 正负值（得分差）
    is_winner: bool | None = None
    is_mvp: bool = False


class PlayerPanelResponse(BaseModel):
    player: PlayerPanelBasic
    rating_history: list[PlayerPanelHistoryItem]
    recent_matches: list[PlayerPanelRecentMatchItem]

