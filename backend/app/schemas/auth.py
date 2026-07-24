import re

from pydantic import BaseModel, EmailStr, field_validator


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str


# ──────────────────────────────────────────────────────────────────────────────
# T018 [US1]: /auth/me/context 响应 Schema
# ──────────────────────────────────────────────────────────────────────────────


class TeamEntry(BaseModel):
    """用户可进入的单个队伍条目。"""

    team_id: int
    team_name: str | None
    player_id: int
    role: str
    status: str


class ActivePlayerContext(BaseModel):
    """当前激活的 player 上下文（切队后更新）。"""

    player_id: int
    team_id: int
    role: str
    status: str
    display_name: str | None
    mu: float
    conservative_rating: float


class UserContextData(BaseModel):
    """/auth/me/context data 字段内容。"""

    user_id: int
    username: str
    email: str | None
    is_superadmin: bool
    default_team_id: int | None
    teams: list[TeamEntry]
    active_player: ActivePlayerContext | None


class UserContextResponse(BaseModel):
    """统一 code/data/message 响应包装。"""

    code: int = 0
    data: UserContextData
    message: str = ""


class SwitchTeamRequest(BaseModel):
    """POST /auth/switch-team 请求体。"""

    team_id: int


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr  # 必填，用于找回密码
    display_name: str | None = None
    password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9]{6,20}$", v):
            raise ValueError("账号必须为 6-20 位字母数字")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密码最少 8 位")
        return v
