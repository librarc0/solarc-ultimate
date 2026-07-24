"""T058 [US7]: MergeTaskRecord 模型 - 记录重复人员合并操作历史与回滚信息"""

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MergeStatus(str, Enum):
    pending = "pending"
    done = "done"
    rolled_back = "rolled_back"
    failed = "failed"


class MergeTaskRecord(Base):
    """记录一次人员合并操作，用于审计和回滚。"""

    __tablename__ = "merge_task_record"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    canonical_user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    """合并后保留的 user（规范账号）"""

    merged_player_ids: Mapped[str] = mapped_column(Text, nullable=False)
    """被合并的 player id 列表（JSON 序列化），这些 player 的 user_id 被更新为 canonical_user_id"""

    snapshot_json: Mapped[str] = mapped_column(Text, nullable=False)
    """合并前各 player 的快照（JSON），用于回滚"""

    status: Mapped[MergeStatus] = mapped_column(String(20), default=MergeStatus.pending, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
