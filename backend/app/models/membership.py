"""PlayerTeamMembership — 用户与队伍的多对多关联表，含队伍独立评分。"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.player import PlayerStatus, UserRole


class PlayerTeamMembership(Base):
    __tablename__ = "player_team_membership"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    player_id: Mapped[int] = mapped_column(
        ForeignKey("player.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("team.id", ondelete="CASCADE"), nullable=False, index=True
    )

    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="userrole"), default=UserRole.member, nullable=False
    )
    status: Mapped[PlayerStatus] = mapped_column(
        SAEnum(PlayerStatus, name="playerstatus"), default=PlayerStatus.pending, nullable=False
    )

    # 申请理由（用户申请加入时填写）
    join_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # 该用户在本队伍的独立评分（与 Player 表保持双写冗余）
    mu: Mapped[float] = mapped_column(Float, default=25.0, nullable=False)
    sigma: Mapped[float] = mapped_column(Float, default=8.333, nullable=False)
    conservative_rating: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)

    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("player.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # T040 [US4]: 审核时快照的建议初始 μ（FR-013：用于记录审核参考依据）
    suggested_mu_snapshot: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("player_id", "team_id", name="uq_player_team"),
    )

    # Relationships
    player: Mapped["Player"] = relationship(  # noqa: F821
        "Player", foreign_keys=[player_id], back_populates="memberships"
    )
    team: Mapped["Team"] = relationship("Team", foreign_keys=[team_id])  # noqa: F821
