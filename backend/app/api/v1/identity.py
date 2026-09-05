from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.discovery.engine import DiscoveryEngine
from app.identity.schemas import (
    IdentitySearchRequest,
    IdentitySearchResponse,
    IdentitySelectRequest,
    IdentitySelectResponse,
    SubjectCapabilitiesResponse,
    SubjectResponse,
)
from app.investigations.models import (
    Subject,
    SubjectIdentity,
)

from app.providers.registry import provider_registry


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

    engine = DiscoveryEngine()

    try:
        discovered = await engine.search(
            query
        )

        # Identity search remains compatible with
        # the existing IdentityCandidate response model.
        candidates = [
            # IdentityCandidate-compatible data
            # is constructed explicitly below.
            candidate
            for candidate in []
        ]

        # Convert normalized discovery candidates
        # back into the richer identity response.
        from app.identity.schemas import (
            IdentityCandidate,
        )

        candidates = [
            IdentityCandidate(
                provider=candidate.provider,
                provider_user_id=(
                    candidate.provider_user_id
                ),
                username=candidate.username,
                display_name=(
                    candidate.display_name
                ),
                profile_url=candidate.profile_url,
                avatar_url=candidate.avatar_url,
                score=candidate.confidence,
                confidence_percent=round(
                    candidate.confidence * 100
                ),
                match_type=candidate.match_type,
                reasons=list(candidate.reasons),
                identifiers=dict(
                    candidate.identifiers
                ),
                public_repos=(
                    candidate.metadata.get(
                        "public_repos"
                    )
                ),
                followers=(
                    candidate.metadata.get(
                        "followers"
                    )
                ),
                following=(
                    candidate.metadata.get(
                        "following"
                    )
                ),
                bio=candidate.metadata.get(
                    "bio"
                ),
                location=candidate.metadata.get(
                    "location"
                ),
                company=candidate.metadata.get(
                    "company"
                ),
                blog=candidate.metadata.get(
                    "blog"
                ),
            )
            for candidate in discovered
        ]

        return IdentitySearchResponse(
            query=query,
            candidates=candidates,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Identity discovery failed: {exc}",
        ) from exc


@router.post(
    "/select",
    response_model=IdentitySelectResponse,
)
async def select_identity(
    request: IdentitySelectRequest,
    db: AsyncSession = Depends(get_db),
) -> IdentitySelectResponse:

    query = request.query.strip()
    provider_name = request.provider.strip()
    provider_user_id = (
        request.provider_user_id.strip()
    )

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Selection query cannot be empty.",
        )

    if not provider_name:
        raise HTTPException(
            status_code=400,
            detail="Provider cannot be empty.",
        )

    if not provider_user_id:
        raise HTTPException(
            status_code=400,
            detail="Provider user ID cannot be empty.",
        )

    provider = provider_registry.get(
        provider_name
    )

    if provider is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Provider '{provider_name}' "
                "is not registered."
            ),
        )

    # ---------------------------------------------------------
    # Re-run discovery and verify the selected identity.
    #
    # This prevents the client from inventing/changing:
    # username, display name, profile URL, confidence, etc.
    # ---------------------------------------------------------
    engine = DiscoveryEngine()

    try:
        candidates = await engine.search(
            query
        )
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Unable to validate selected identity: "
                f"{exc}"
            ),
        ) from exc

    selected = next(
        (
            candidate
            for candidate in candidates
            if (
                candidate.provider
                == provider_name
                and candidate.provider_user_id
                == provider_user_id
            )
        ),
        None,
    )

    if selected is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "The selected identity was not found "
                "in the discovery results."
            ),
        )

    # ---------------------------------------------------------
    # Build Subject exclusively from the verified candidate.
    # ---------------------------------------------------------
    subject = Subject(
        provider=selected.provider,
        provider_user_id=(
            selected.provider_user_id
        ),
        username=selected.username,
        display_name=(
            selected.display_name
        ),
        profile_url=selected.profile_url,
        confidence=selected.confidence,
        identifiers=dict(
            selected.identifiers
        ),
        capabilities=provider.get_capabilities(),
    )

    db.add(subject)

    try:
        await db.commit()
        await db.refresh(subject)

    except Exception as exc:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to persist selected identity: "
                f"{exc}"
            ),
        ) from exc

    return IdentitySelectResponse(
        subject_id=subject.id,
        provider=subject.provider,
        provider_user_id=subject.provider_user_id,
        username=subject.username,
        display_name=subject.display_name,
        profile_url=subject.profile_url,
        confidence=subject.confidence,
        identifiers=subject.identifiers,
        capabilities=subject.capabilities,
        selected=True,
    )


@router.get(
    "/subjects/{subject_id}",
    response_model=SubjectResponse,
)
async def get_subject(
    subject_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SubjectResponse:

    result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id
        )
    )

    subject = result.scalar_one_or_none()

    if subject is None:
        raise HTTPException(
            status_code=404,
            detail="Selected subject not found.",
        )

    return SubjectResponse(
        subject_id=subject.id,
        provider=subject.provider,
        provider_user_id=subject.provider_user_id,
        username=subject.username,
        display_name=subject.display_name,
        profile_url=subject.profile_url,
        confidence=subject.confidence,
        identifiers=subject.identifiers,
        capabilities=subject.capabilities,
    )


@router.get(
    "/subjects/{subject_id}/capabilities",
    response_model=SubjectCapabilitiesResponse,
)
async def get_subject_capabilities(
    subject_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SubjectCapabilitiesResponse:

    result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id
        )
    )

    subject = result.scalar_one_or_none()

    if subject is None:
        raise HTTPException(
            status_code=404,
            detail="Selected subject not found.",
        )

    provider = provider_registry.get(
        subject.provider
    )

    if provider is None:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Provider '{subject.provider}' "
                "is no longer registered."
            ),
        )

    # Refresh capability metadata from the provider.
    capabilities = provider.get_capabilities()

    supported_identifiers = (
        provider.get_supported_identifiers()
    )

    subject.capabilities = capabilities

    await db.commit()

    return SubjectCapabilitiesResponse(
        subject_id=subject.id,
        provider=subject.provider,
        provider_user_id=subject.provider_user_id,
        capabilities=capabilities,
        supported_identifiers=supported_identifiers,
    )