from fastapi import APIRouter

from app.api.v1 import (
    capabilities,
    github_actions,
    health,
    identity,
    investigations,
)
from app.api.v1.providers import (
    router as providers_router,
)


api_router = APIRouter()


api_router.include_router(
    health.router
)

api_router.include_router(
    investigations.router
)

api_router.include_router(
    identity.router
)

api_router.include_router(
    github_actions.router
)

api_router.include_router(
    providers_router
)

api_router.include_router(
    capabilities.router
)