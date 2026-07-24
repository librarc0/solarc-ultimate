from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RankingSeason(Base):
    """赛季：每个榜单属于某一赛季，管理员可新增/维护"""
    __tablename__ = "ranking_season"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)   # e.g. "2025春季赛"
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # e.g. 2025
    start_date: Mapped[str | None] = mapped_column(String(20), nullable=True)   # YYYY-MM-DD
    end_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    batches: Mapped[list["RankingUploadBatch"]] = relationship(
        back_populates="season", passive_deletes=True
    )
    teams: Mapped[list["ExternalTeam"]] = relationship(
        back_populates="season", passive_deletes=True
    )


class RankingAdmin(Base):
    """排行榜专用管理员，与 Player 体系完全隔离"""
    __tablename__ = "ranking_admin"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class RankingApiKey(Base):
    """外部平台 API 推送密钥"""
    __tablename__ = "ranking_api_key"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(10), nullable=False)          # 前6位，用于展示
    key_hash: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)  # SHA-256(full_key)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    season_id: Mapped[int | None] = mapped_column(
        ForeignKey("ranking_season.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    season: Mapped["RankingSeason | None"] = relationship()


class RankingUploadBatch(Base):
    """一次上传/推送为一个批次"""
    __tablename__ = "ranking_upload_batch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    season_id: Mapped[int | None] = mapped_column(
        ForeignKey("ranking_season.id", ondelete="CASCADE"), nullable=True, index=True
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)  # "upload" | "api" | "restore"
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exported_at: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 来源文件中的 exportedAt
    raw_payload: Mapped[str | None] = mapped_column(Text, nullable=True)  # 原始 JSON 用于恢复

    season: Mapped["RankingSeason | None"] = relationship(back_populates="batches")
    tournament_records: Mapped[list["TournamentRecord"]] = relationship(
        back_populates="batch", passive_deletes=True
    )


class ExternalTeam(Base):
    """跨赛事聚合后的队伍排名（每支队伍每赛季一条）"""
    __tablename__ = "external_team"
    __table_args__ = (
        UniqueConstraint("name", "season_id", name="uq_external_team_name_season"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    season_id: Mapped[int | None] = mapped_column(
        ForeignKey("ranking_season.id", ondelete="CASCADE"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prev_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rank_change: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 正=上升，负=下降
    total_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    avg_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tournament_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    draws: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    forfeits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_games: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    points_scored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points_conceded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    net_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    province: Mapped[str | None] = mapped_column(String(20), nullable=True)   # ISO 3166-2, e.g. CN-SH
    city: Mapped[str | None] = mapped_column(String(30), nullable=True)        # ISO 3166-2, e.g. CN-SH or CN-GD-GZ
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    tournament_records: Mapped[list["TournamentRecord"]] = relationship(
        back_populates="team", passive_deletes=True
    )
    season: Mapped["RankingSeason | None"] = relationship(back_populates="teams")


class TournamentRecord(Base):
    """单次赛事记录（原始数据，对应 JSON 中 tournaments[] 的每一项）"""
    __tablename__ = "tournament_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("ranking_upload_batch.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("external_team.id", ondelete="CASCADE"), nullable=False, index=True
    )
    team_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tournament_name: Mapped[str] = mapped_column(String(200), nullable=False)
    level: Mapped[str] = mapped_column(String(20), nullable=False)   # National | Provincial | Local
    month: Mapped[str] = mapped_column(String(7), nullable=False)     # YYYY-MM
    wins: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losses: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    draws: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    forfeits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_games: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    points_scored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    points_conceded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pool: Mapped[str] = mapped_column(String(10), nullable=False)    # A | B | C | NoPool
    final_rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    computed_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    batch: Mapped["RankingUploadBatch"] = relationship(back_populates="tournament_records")
    team: Mapped["ExternalTeam"] = relationship(back_populates="tournament_records")
