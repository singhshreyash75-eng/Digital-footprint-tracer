from fastapi import APIRouter, HTTPException

from app.discovery.engine import DiscoveryEngine
from app.discovery.schemas import (
    DiscoveryRequest,
    DiscoveryResponse,
)


router = APIRouter(
    prefix="/discovery",
    tags=["Discovery"],
)


@router.post(
    "/search",
    response_model=DiscoveryResponse,
)
async def discovery_search(
    request: DiscoveryRequest,
) -> DiscoveryResponse:

    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Discovery query cannot be empty.",
        )

    engine = DiscoveryEngine()

    try:
        candidates = await engine.search(
            query
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Discovery failed: {exc}",
        ) from exc

    return DiscoveryResponse(
        query=query,
        candidates=candidates,
        total=len(candidates),
    )