"""队伍日历/日程管理数据模型"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    DateTime, Date, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ScheduleEventType(str, Enum):
    game = "game"           # 外战比赛
    training = "training"   # 训练
    internal = "internal"   # 内战
    other = "other"         # 其他


class ScheduleEventStatus(str, Enum):
    draft = "draft"
    published = "published"


class AttendanceStatus(str, Enum):
    yes = "yes"       # 参加
    leave = "leave"   # 请假/不参加
    sdl = "sdl"       # sideline（只加油，不上场）
    no = "no"         # 兼容历史数据：前端已下线，读取时统一按 leave 处理


class DivisionMethod(str, Enum):
    auto_balanced = "auto_balanced"             # 自动平均分配（战力均衡）
    auto_strong_to_weak = "auto_strong_to_weak" # 按战力强弱分组（从强到弱）
    manual = "manual"                           # 手动分配


class LineType(str, Enum):
    o_line = "o_line"  # 外战进攻 line
    d_line = "d_line"  # 外战防守 line
    line = "line"      # 普通 line（训练/内战）


class ScheduleEvent(Base):
    __tablename__ = "schedule_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[ScheduleEventType] = mapped_column(
        SAEnum(ScheduleEventType, name="scheduleeventtype"), nullable=False
    )
    start_date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[datetime] = mapped_column(Date, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ScheduleEventStatus] = mapped_column(
        SAEnum(ScheduleEventStatus, name="scheduleeventstatus"),
        nullable=False,
        default=ScheduleEventStatus.draft,
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    # 关联已创建的比赛（反向引用，不改动 match 表）
    linked_match_id: Mapped[int | None] = mapped_column(ForeignKey("match.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    attendances: Mapped[list[ScheduleAttendance]] = relationship(
        "ScheduleAttendance", back_populates="event", cascade="all, delete-orphan"
    )
    line_division: Mapped[ScheduleLineDivision | None] = relationship(
        "ScheduleLineDivision", back_populates="event", uselist=False, cascade="all, delete-orphan"
    )


class ScheduleAttendance(Base):
    __tablename__ = "schedule_attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("schedule_event.id"), nullable=False, index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False, index=True)
    status: Mapped[AttendanceStatus] = mapped_column(
        SAEnum(AttendanceStatus, name="attendancestatus"), nullable=False
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (UniqueConstraint("event_id", "player_id", name="uq_attendance_event_player"),)

    event: Mapped[ScheduleEvent] = relationship("ScheduleEvent", back_populates="attendances")


class ScheduleLineDivision(Base):
    """每个日程事件的分 line 方案（每事件唯一）"""
    __tablename__ = "schedule_line_division"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("schedule_event.id"), nullable=False, unique=True)
    division_method: Mapped[DivisionMethod] = mapped_column(
        SAEnum(DivisionMethod, name="divisionmethod"), nullable=False, default=DivisionMethod.manual
    )
    # 内战多轮支持（training/game 固定为 1）
    total_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    event: Mapped[ScheduleEvent] = relationship("ScheduleEvent", back_populates="line_division")
    lines: Mapped[list[ScheduleLine]] = relationship(
        "ScheduleLine", back_populates="division", cascade="all, delete-orphan", order_by="ScheduleLine.round_number, ScheduleLine.order_index"
    )


class ScheduleLine(Base):
    """单条 line"""
    __tablename__ = "schedule_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    division_id: Mapped[int] = mapped_column(
        ForeignKey("schedule_line_division.id"), nullable=False,
    )
    line_name: Mapped[str] = mapped_column(String(50), nullable=False)
    line_type: Mapped[LineType] = mapped_column(
        SAEnum(LineType, name="linetype"), nullable=False, default=LineType.line
    )
    # 内战多轮时区分轮次，其他类型 = 1
    round_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    division: Mapped[ScheduleLineDivision] = relationship("ScheduleLineDivision", back_populates="lines")
    players: Mapped[list[ScheduleLinePlayer]] = relationship(
        "ScheduleLinePlayer", back_populates="line", cascade="all, delete-orphan"
    )

    # 显式指定索引名，避免与 schedule_line_division.id 的自动索引名重名
    __table_args__ = (
        Index("ix_schedule_line_div_id", "division_id"),
    )


class ScheduleLinePlayer(Base):
    """line 中的球员（内战同轮唯一约束在 API 层校验）"""
    __tablename__ = "schedule_line_player"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    line_id: Mapped[int] = mapped_column(ForeignKey("schedule_line.id"), nullable=False, index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False, index=True)

    __table_args__ = (UniqueConstraint("line_id", "player_id", name="uq_line_player"),)

    line: Mapped[ScheduleLine] = relationship("ScheduleLine", back_populates="players")


class ScheduleLineTemplate(Base):
    """训练/外战可复用的分 line 模板（按队伍 + 活动类型保存，最多 3 个由 API 控制）"""
    __tablename__ = "schedule_line_template"
    __table_args__ = (
        UniqueConstraint("team_id", "event_type", "template_name", name="uq_schedule_line_template_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("team.id"), nullable=False, index=True)
    event_type: Mapped[ScheduleEventType] = mapped_column(
        SAEnum(ScheduleEventType, name="scheduleeventtype"), nullable=False
    )
    template_name: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int] = mapped_column(ForeignKey("player.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
