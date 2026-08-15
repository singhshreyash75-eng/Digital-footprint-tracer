from fastapi import APIRouter

from app.api.v1 import (
    health,
    identity,
    investigations,
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