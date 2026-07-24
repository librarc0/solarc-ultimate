from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Team(Base):
    __tablename__ = "team"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="0")

    players: Mapped[list["Player"]] = relationship(  # noqa: F821
        "Player", back_populates="team", foreign_keys="Player.team_id"
    )
    settings: Mapped["TeamSettings"] = relationship(  # noqa: F821
        "TeamSettings", back_populates="team", uselist=False
    )
    posts: Mapped[list["TeamPost"]] = relationship(  # noqa: F821
        "TeamPost", back_populates="team"
    )
