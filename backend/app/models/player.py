from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class UserRole(str, Enum):
    owner = "owner"
    admin = "admin"
    member = "member"


class PlayerStatus(str, Enum):
    pending = "pending"
    active = "active"
    rejected = "rejected"


class Player(Base):
    __tablename__ = "player"

    # unique(user_id, team_id)：同一 user 在同一队伍最多只有一个 player
    # 注意：user_id 为 nullable（过渡期兼容旧账号），SQLite 中 NULL != NULL 不违反约束
    __table_args__ = (
        UniqueConstraint("user_id", "team_id", name="uq_player_user_team"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # 所属 user（架构升级后的认证主体外键，迁移期可为 null 保持兼容）
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", name="fk_player_user_id"), nullable=True, index=True
    )
    team_id: Mapped[int | None] = mapped_column(ForeignKey("team.id"), nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(254), nullable=True, unique=True, index=True)
    reset_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    reset_token_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="userrole"), default=UserRole.member, nullable=False
    )
    status: Mapped[PlayerStatus] = mapped_column(
        SAEnum(PlayerStatus, name="playerstatus"), default=PlayerStatus.pending, nullable=False
    )

    # Profile image
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Gender: 'M' | 'F' | None
    gender: Mapped[str | None] = mapped_column(String(1), nullable=True)

    # Jersey number (球衣号码) — optional
    jersey_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # WeChat openid — for miniprogram login
    wx_openid: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)

    # Super admin: can access ALL teams
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # OpenSkill parameters
    mu: Mapped[float] = mapped_column(Float, default=25.0, nullable=False)
    sigma: Mapped[float] = mapped_column(Float, default=8.333, nullable=False)
    conservative_rating: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)

    # Cumulative stats
    total_goals: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_assists: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_defenses: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 累计防守次数
    total_plus_minus: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 累计正负值（得分差）
    total_turnovers: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_matches: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_wins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Ranking visibility: admin/owner can opt out from leaderboard
    show_in_rankings: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Guest/外援 player: not a permanent member, excluded from rankings
    is_guest: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("player.id"), nullable=True
    )

    # Relationships
    # 反向关联到 User（认证主体）
    user: Mapped["User | None"] = relationship(  # noqa: F821
        "User",
        back_populates="players",
        foreign_keys=[user_id],
    )
    team: Mapped["Team"] = relationship(  # noqa: F821
        "Team", back_populates="players", foreign_keys=[team_id]
    )
    match_participations: Mapped[list["MatchPlayer"]] = relationship(  # noqa: F821
        "MatchPlayer", back_populates="player", foreign_keys="MatchPlayer.player_id"
    )
    rating_history: Mapped[list["RatingHistory"]] = relationship(  # noqa: F821
        "RatingHistory", back_populates="player", foreign_keys="RatingHistory.player_id"
    )
    memberships: Mapped[list["PlayerTeamMembership"]] = relationship(  # noqa: F821
        "PlayerTeamMembership",
        back_populates="player",
        foreign_keys="PlayerTeamMembership.player_id",
        lazy="select",
    )