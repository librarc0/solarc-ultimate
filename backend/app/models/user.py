"""User 模型 — 全局登录身份主体，一人一号。

架构说明：
- User 是唯一的认证主体，JWT sub 绑定 user_id
- 每个 User 可在多个 Team 中拥有独立的 Player 分身
- 登录凭证（username、email、password_hash）在 User 层管理，不再分散在 Player 中
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # 全局唯一登录账号名（6-20 位字母数字）
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    # 全局唯一邮箱（用于找回密码，可选）
    email: Mapped[str | None] = mapped_column(String(254), unique=True, nullable=True, index=True)
    # 密码哈希（bcrypt）
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)

    # 微信 openid（小程序登录，全局唯一，可选）
    wx_openid: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True, index=True)

    # 是否为超级管理员（全局角色，不与任何具体队伍绑定）
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # 用户设置的默认队伍（登录后优先进入此队伍）
    # 应用层保证该队伍在该 user 的可用队伍集合内
    default_team_id: Mapped[int | None] = mapped_column(
        ForeignKey("team.id", name="fk_user_default_team_id"), nullable=True
    )

    # 密码重置 token（找回密码流程）
    reset_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    reset_token_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────────

    # 该 user 在各队伍中的 player 分身（正向：一 user 多 player）
    players: Mapped[list["Player"]] = relationship(  # noqa: F821
        "Player",
        back_populates="user",
        foreign_keys="Player.user_id",
        lazy="select",
    )

    # 默认队伍对象（仅读）
    default_team: Mapped["Team | None"] = relationship(  # noqa: F821
        "Team",
        foreign_keys=[default_team_id],
    )
