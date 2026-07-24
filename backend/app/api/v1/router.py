from fastapi import APIRouter

from app.api.v1.endpoints import auth, players, matches, rankings, team, exports, audit_logs
from app.api.v1.endpoints import schedule_events, schedule_attendance, schedule_lines, help_docs
from app.api.v1.endpoints import public_rankings, ranking_admin, external_rankings_push
from app.api.v1.endpoints import auth_wechat
from app.api.v1.endpoints.team_membership import router as team_membership_router

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(auth_wechat.router, prefix="/auth", tags=["auth-wechat"])
api_router.include_router(players.router, prefix="/players", tags=["players"])
api_router.include_router(matches.router, prefix="/matches", tags=["matches"])
api_router.include_router(rankings.router, prefix="/rankings", tags=["rankings"])
api_router.include_router(team.router, prefix="/team", tags=["team"])
api_router.include_router(team_membership_router, prefix="/team-membership", tags=["team-membership"])
api_router.include_router(exports.router, prefix="/exports", tags=["exports"])
api_router.include_router(audit_logs.router, prefix="/audit-logs", tags=["audit"])
api_router.include_router(schedule_events.router, prefix="/schedule-events", tags=["schedule"])
api_router.include_router(schedule_attendance.router, prefix="/schedule-attendance", tags=["schedule"])
api_router.include_router(schedule_lines.router, prefix="/schedule-lines", tags=["schedule"])
api_router.include_router(help_docs.router, prefix="/help-docs", tags=["help"])
# 公开排行榜（无需认证）
api_router.include_router(public_rankings.router, prefix="/public", tags=["public-rankings"])
# 排行榜管理员后台
api_router.include_router(ranking_admin.router, prefix="/ranking-admin", tags=["ranking-admin"])
# 外部平台推送
api_router.include_router(external_rankings_push.router, prefix="/external", tags=["external-rankings"])

