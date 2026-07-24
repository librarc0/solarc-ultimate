"""操作审计日志模型"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # 操作所属队伍（None 表示全局操作，如超管审批队伍）
    team_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # 操作者信息（冗余存储，避免 JOIN；超管删除自身时仍可查询历史）
    actor_id: Mapped[int] = mapped_column(ForeignKey("player.id", ondelete="SET NULL"), nullable=True)
    actor_username: Mapped[str] = mapped_column(String(100), nullable=False)
    # 操作描述
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON 字符串
    # 时间
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
