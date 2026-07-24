from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MatchType(str, Enum):
    internal = "internal"
    external = "external"


class GameType(str, Enum):
    ultimate = "ultimate"
    goal = "goal"


class MatchStatus(str, Enum):
    draft = "draft"
    pending_approval = "pending_approval"
    approved = "approved"
    rejected = "rejected"


class EventType(str, Enum):
    goal = "goal"
    assist = "assist"
    defense = "defense"
    turnover = "turnover"
    halftime = "halftime"
    start = "start"
    end = "end"


class TeamSide(str, Enum):
    A = "A"
    B = "B"


class Match(Base):
    __tablename__ = "match"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False, index=True)
    match_type: Mapped[MatchType] = mapped_column(SAEnum(MatchType, name="matchtype"), nullable=False)
    game_type: Mapped[GameType] = mapped_column(SAEnum(GameType, name="gametype"), default=GameType.ultimate, nullable=False)
    data_level: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    team_a_score: Mapped[int] = mapped_column(Integer, nullable=False)
    team_b_score: Mapped[int] = mapped_column(Integer, nullable=False)
    opponent_strength: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opponent_external_team_id: Mapped[int | None] = mapped_column(ForeignKey("external_team.id"), nullable=True)
    opponent_calibrated_mu: Mapped[float | None] = mapped_column(Float, nullable=True)
    opponent_calibrated_sigma: Mapped[float | None] = mapped_column(Float, nullable=True)
    match_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[MatchStatus] = mapped_column(SAEnum(MatchStatus, name="matchstatus"), default=MatchStatus.draft, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False, index=True)
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("player.id"), nullable=True, index=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_owner_id: Mapped[int | None] = mapped_column(ForeignKey("player.id"), nullable=True, index=True)
    last_event_seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    saved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    draft_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    participants: Mapped[list["MatchPlayer"]] = relationship("MatchPlayer", back_populates="match", cascade="all, delete-orphan")
    rating_changes: Mapped[list["RatingHistory"]] = relationship("RatingHistory", back_populates="match")
    events: Mapped[list["MatchEvent"]] = relationship("MatchEvent", back_populates="match", cascade="all, delete-orphan")
    spirit_score: Mapped["MatchSpiritScore | None"] = relationship(
        "MatchSpiritScore",
        back_populates="match",
        cascade="all, delete-orphan",
        uselist=False,
    )


class MatchPlayer(Base):
    __tablename__ = "match_player"
    __table_args__ = (UniqueConstraint("match_id", "player_id", name="uq_match_player"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.id"), nullable=False, index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False, index=True)
    team_side: Mapped[TeamSide] = mapped_column(SAEnum(TeamSide, name="teamside"), nullable=False)
    goals: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assists: Mapped[int | None] = mapped_column(Integer, nullable=True)
    defenses: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 防守次数（事件统计）
    plus_minus: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 正负值（得分差：A队=a-b，B队=b-a）
    turnovers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_mvp: Mapped[bool] = mapped_column(Boolean, default=False)
    is_winner: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    mu_before: Mapped[float] = mapped_column(Float, nullable=False)
    sigma_before: Mapped[float] = mapped_column(Float, nullable=False)
    mu_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    sigma_after: Mapped[float | None] = mapped_column(Float, nullable=True)

    match: Mapped["Match"] = relationship("Match", back_populates="participants")
    player: Mapped["Player"] = relationship("Player", back_populates="match_participations", foreign_keys=[player_id])  # noqa: F821


class RatingHistory(Base):
    __tablename__ = "rating_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False, index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.id"), nullable=False, index=True)
    mu_before: Mapped[float] = mapped_column(Float, nullable=False)
    sigma_before: Mapped[float] = mapped_column(Float, nullable=False)
    mu_after: Mapped[float] = mapped_column(Float, nullable=False)
    sigma_after: Mapped[float] = mapped_column(Float, nullable=False)
    conservative_before: Mapped[float] = mapped_column(Float, nullable=False)
    conservative_after: Mapped[float] = mapped_column(Float, nullable=False)
    delta_mu: Mapped[float] = mapped_column(Float, nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False, default="match_result")
    operated_by: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    player: Mapped["Player"] = relationship("Player", back_populates="rating_history", foreign_keys=[player_id])  # noqa: F821
    match: Mapped["Match"] = relationship("Match", back_populates="rating_changes")


class TeamSettings(Base):
    __tablename__ = "team_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), unique=True, nullable=False)
    # ── 个人贡献调整系数 ──────────────────────────────────────────────────────
    alpha: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    beta: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)
    gamma: Mapped[float] = mapped_column(Float, default=0.4, nullable=False)
    defense_weight: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)
    # ── 综合评分混合系数 ─────────────────────────────────────────────────────
    composite_ts_weight: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)
    composite_perf_weight: Mapped[float] = mapped_column(Float, default=0.15, nullable=False)
    composite_attendance_weight: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # ── 特殊奖惩系数 ─────────────────────────────────────────────────────────
    turnover_penalty: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)
    turnover_sigma_factor: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    break_bonus_per_goal: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)
    winner_floor_factor: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)
    # ── 内战 / 外战影响力 ────────────────────────────────────────────────────
    external_impact_multiplier: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    external_opp_mu_min: Mapped[float] = mapped_column(Float, default=15.0, nullable=False)
    external_opp_mu_max: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    external_opp_sigma: Mapped[float] = mapped_column(Float, default=6.0, nullable=False)
    # ── OpenSkill 模型超参数（队伍级）────────────────────────────────────────
    openskill_mu: Mapped[float] = mapped_column(Float, default=25.0, nullable=False)
    openskill_sigma: Mapped[float] = mapped_column(Float, default=25.0 / 3.0, nullable=False)
    openskill_beta: Mapped[float] = mapped_column(Float, default=25.0 / 6.0, nullable=False)
    openskill_tau: Mapped[float] = mapped_column(Float, default=25.0 / 300.0, nullable=False)
    openskill_kappa: Mapped[float] = mapped_column(Float, default=0.0001, nullable=False)
    openskill_margin: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    openskill_limit_sigma: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    openskill_balance: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # ── 化学值公式权重 ───────────────────────────────────────────────────────
    chemistry_win_weight: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    chemistry_combo_weight: Mapped[float] = mapped_column(Float, default=0.3, nullable=False)
    chemistry_decay_constant: Mapped[float] = mapped_column(Float, default=8.0, nullable=False)
    # ── 动态 K 因子 / 飞盘特性事件奖惩 ─────────────────────────────────────────
    sigma_bonus_factor: Mapped[float] = mapped_column(Float, default=0.15, nullable=False)
    weight_cap: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)
    universal_point_bonus: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    block_mu_bonus: Mapped[float] = mapped_column(Float, default=0.05, nullable=False)
    consecutive_turnover_threshold: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    consecutive_turnover_multiplier: Mapped[float] = mapped_column(Float, default=1.5, nullable=False)
    # ── 综合战力：表现分场次置信衰减 ────────────────────────────────────────────
    # perf_score 折扣公式: 50 + (1-exp(-matches/N)) * (raw_perf-50)
    # N 越大，需要更多场次才能充分反映表现；默认 8 场时置信度约 63%
    perf_confidence_decay: Mapped[float] = mapped_column(Float, default=8.0, nullable=False)
    # ── MIP 最佳进步球员评分参数 ──────────────────────────────────────────────
    # 四维权重之和建议保持 1.0；mip_slope_lambda 越大越强调近期表现
    mip_weight_mu_delta: Mapped[float] = mapped_column(Float, default=0.40, nullable=False)   # µ 绝对增幅权重（首→末场净增量）
    mip_weight_slope: Mapped[float] = mapped_column(Float, default=0.30, nullable=False)       # 加权趋势斜率权重（指数衰减回归）
    mip_weight_half: Mapped[float] = mapped_column(Float, default=0.20, nullable=False)        # 后半程 vs 前半程均值差权重
    mip_weight_sigma: Mapped[float] = mapped_column(Float, default=0.10, nullable=False)       # σ 降幅权重（稳定性增长）
    mip_slope_lambda: Mapped[float] = mapped_column(Float, default=0.15, nullable=False)       # 指数衰减系数（λ=0.15 时首场权重≈末场 15%）
    mip_min_matches: Mapped[int] = mapped_column(Integer, default=6, nullable=False)           # 参与进步榜最少场次门槛
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    updated_by: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)

    team: Mapped["Team"] = relationship("Team", back_populates="settings")  # noqa: F821


class PlayerChemistry(Base):
    __tablename__ = "player_chemistry"
    __table_args__ = (UniqueConstraint("player_a_id", "player_b_id", "team_id", name="uq_chemistry"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    player_a_id: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    player_b_id: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False, index=True)
    co_matches: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    co_wins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    combo_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chemistry_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    expected_win_rate: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    synergy_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class MatchEvent(Base):
    __tablename__ = "match_event"
    __table_args__ = (
        UniqueConstraint("match_id", "seq", name="uq_match_event_seq"),
        UniqueConstraint("match_id", "client_event_id", name="uq_match_event_client_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.id"), nullable=False, index=True)
    event_type: Mapped[EventType] = mapped_column(SAEnum(EventType, name="eventtype"), nullable=False)
    team_side: Mapped[TeamSide | None] = mapped_column(SAEnum(TeamSide, name="teamside"), nullable=True)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("player.id"), nullable=True)
    assist_player_id: Mapped[int | None] = mapped_column(ForeignKey("player.id"), nullable=True)
    is_break: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    is_universe_point: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    elapsed_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seq: Mapped[int | None] = mapped_column(Integer, nullable=True)
    client_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("player.id"), nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="manual", nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    match: Mapped["Match"] = relationship("Match", back_populates="events")


class MatchSpiritScore(Base):
    __tablename__ = "match_spirit_score"
    __table_args__ = (UniqueConstraint("match_id", name="uq_match_spirit_score_match"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("match.id"), nullable=False, index=True)
    rules: Mapped[int] = mapped_column(Integer, nullable=False)
    contact: Mapped[int] = mapped_column(Integer, nullable=False)
    fairness: Mapped[int] = mapped_column(Integer, nullable=False)
    attitude: Mapped[int] = mapped_column(Integer, nullable=False)
    communication: Mapped[int] = mapped_column(Integer, nullable=False)
    total_score: Mapped[int] = mapped_column(Integer, nullable=False)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    updated_by: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    match: Mapped["Match"] = relationship("Match", back_populates="spirit_score")


class TeamPost(Base):
    __tablename__ = "team_post"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("team_post.id"), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    team: Mapped["Team"] = relationship("Team", back_populates="posts")  # noqa: F821
    replies: Mapped[list["TeamPost"]] = relationship("TeamPost", foreign_keys=[parent_id], back_populates="parent")
    parent: Mapped["TeamPost | None"] = relationship("TeamPost", foreign_keys=[parent_id], back_populates="replies", remote_side=[id])