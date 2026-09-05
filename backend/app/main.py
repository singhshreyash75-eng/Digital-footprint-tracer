from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
    )

    # ---------------------------------------------------------
    # CORS
    # Allow the local frontend to communicate with FastAPI.
    # ---------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---------------------------------------------------------
    # API v1
    #
    # Expected architecture:
    #
    # Name
    #   ↓
    # Identity Discovery
    #   ↓
    # Candidate Selection
    #   ↓
    # Subject
    #   ↓
    # GitHub ─┐
    # Steam ──┤
    # Twitch ─┼─> Aggregated Investigation Result
    # StackEx ┘
    #
    # Provider failures / NOT_FOUND / TIMEOUT should be handled
    # inside the investigation/provider orchestration layer,
    # NOT here.
    # ---------------------------------------------------------
    app.include_router(
        api_router,
        prefix=settings.api_v1_prefix,
    )

    return app


app = create_app()