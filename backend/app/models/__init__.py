# 导入所有模型以确保 SQLAlchemy mapper 注册
# 注意：User 必须在 Player 之前导入，因为 Player.user_id 依赖 user 表
from app.models.user import User  # noqa: F401
from app.models.team import Team  # noqa: F401
from app.models.player import Player, UserRole, PlayerStatus  # noqa: F401
from app.models.membership import PlayerTeamMembership  # noqa: F401
from app.models.match import (  # noqa: F401
    Match, MatchPlayer, RatingHistory,
    TeamSettings, PlayerChemistry, MatchEvent, MatchSpiritScore, TeamPost,
    MatchType, GameType, MatchStatus, EventType, TeamSide,
)
from app.models.audit import AuditLog  # noqa: F401
from app.models.schedule import (  # noqa: F401
    ScheduleEvent, ScheduleAttendance, ScheduleLineDivision, ScheduleLine, ScheduleLinePlayer,
    ScheduleLineTemplate,
    ScheduleEventType, ScheduleEventStatus, AttendanceStatus, DivisionMethod, LineType,
)

__all__ = [
    "User",
    "Team",
    "Player", "UserRole", "PlayerStatus",
    "PlayerTeamMembership",
    "Match", "MatchPlayer", "RatingHistory",
    "TeamSettings", "PlayerChemistry", "MatchEvent", "MatchSpiritScore", "TeamPost",
    "MatchType", "GameType", "MatchStatus", "EventType", "TeamSide",
    "AuditLog",
    "ScheduleEvent", "ScheduleAttendance", "ScheduleLineDivision", "ScheduleLine", "ScheduleLinePlayer", "ScheduleLineTemplate",
    "ScheduleEventType", "ScheduleEventStatus", "AttendanceStatus", "DivisionMethod", "LineType",
]
