"""/team router aggregator."""

from fastapi import APIRouter

from app.api.v1.endpoints.team_membership import router as membership_router
from app.api.v1.endpoints.team_posts import router as posts_router
from app.api.v1.endpoints.team_settings import router as settings_router

router = APIRouter()
router.include_router(membership_router)
router.include_router(settings_router)
router.include_router(posts_router)
