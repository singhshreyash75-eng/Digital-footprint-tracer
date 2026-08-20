from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.identity.resolver import GitHubIdentityResolver
from app.identity.schemas import (
    IdentitySearchRequest,
    IdentitySearchResponse,
    IdentitySelectRequest,
    IdentitySelectResponse,
    SubjectCapabilitiesResponse,
    SubjectResponse,
)
from app.investigations.models import Subject
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
            detail=(
                f"GitHub identity search failed: {exc}"
            ),
        ) from exc


@router.post(
    "/select",
    response_model=IdentitySelectResponse,
)
async def select_identity(
    request: IdentitySelectRequest,
    db: AsyncSession = Depends(get_db),
) -> IdentitySelectResponse:

    provider_name = request.provider.strip()
    username = request.username.strip()

    if not provider_name:
        raise HTTPException(
            status_code=400,
            detail="Provider cannot be empty.",
        )

    if not username:
        raise HTTPException(
            status_code=400,
            detail="Username cannot be empty.",
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

    provider_user_id = (
        request.provider_user_id
        or username
    )

    subject = Subject(
        provider=provider_name,
        provider_user_id=provider_user_id,
        username=username,
        display_name=request.display_name,
        profile_url=request.profile_url,
        confidence=request.confidence,
        identifiers=request.identifiers,
        capabilities=provider.get_capabilities(),
    )

    db.add(subject)

    try:
        await db.commit()
        await db.refresh(subject)
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to persist selected identity.",
        )

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

    # Read live provider capabilities instead of
    # trusting stale metadata stored on the Subject.
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