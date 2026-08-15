from fastapi import APIRouter, HTTPException

from app.identity.resolver import GitHubIdentityResolver
from app.identity.schemas import (
    IdentitySearchRequest,
    IdentitySearchResponse,
    IdentitySelectRequest,
    IdentitySelectResponse,
)

router = APIRouter(
    prefix="/identity",
    tags=["Identity Resolution"],
)


@router.post(
    "/search",
    response_model=IdentitySearchResponse,
)
async def search_identity(
    request: IdentitySearchRequest,
) -> IdentitySearchResponse:

    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Search query cannot be empty.",
        )

    try:
        resolver = GitHubIdentityResolver()

        candidates = await resolver.search(
            query
        )

        return IdentitySearchResponse(
            query=query,
            candidates=candidates,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub identity search failed: {exc}",
        ) from exc


@router.post(
    "/select",
    response_model=IdentitySelectResponse,
)
async def select_identity(
    request: IdentitySelectRequest,
) -> IdentitySelectResponse:

    username = request.username.strip()

    if not username:
        raise HTTPException(
            status_code=400,
            detail="Username cannot be empty.",
        )

    return IdentitySelectResponse(
        provider=request.provider,
        username=username,
        selected=True,
    )