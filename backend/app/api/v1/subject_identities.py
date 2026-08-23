from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.discovery.engine import DiscoveryEngine
from app.investigations.models import (
    Subject,
    SubjectIdentity,
)


router = APIRouter(
    prefix="/subjects",
    tags=["Subject Identities"],
)


@router.post(
    "/{subject_id}/identities",
)
async def link_subject_identity(
    subject_id: UUID,
    provider: str,
    provider_user_id: str,
    query: str,
    db: AsyncSession = Depends(get_db),
) -> dict:

    provider = provider.strip().lower()
    provider_user_id = provider_user_id.strip()
    query = query.strip()

    if not provider:
        raise HTTPException(
            status_code=400,
            detail="Provider cannot be empty.",
        )

    if not provider_user_id:
        raise HTTPException(
            status_code=400,
            detail="Provider user ID cannot be empty.",
        )

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Discovery query cannot be empty.",
        )

    # ---------------------------------------------------------
    # Verify Subject exists.
    # ---------------------------------------------------------
    result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id
        )
    )

    subject = result.scalar_one_or_none()

    if subject is None:
        raise HTTPException(
            status_code=404,
            detail="Subject not found.",
        )

    # ---------------------------------------------------------
    # Re-run discovery to verify that the requested provider
    # identity is a legitimate discovered candidate.
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
                f"Unable to validate provider identity: "
                f"{exc}"
            ),
        ) from exc

    candidate = next(
        (
            item
            for item in candidates
            if (
                item.provider == provider
                and item.provider_user_id
                == provider_user_id
            )
        ),
        None,
    )

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "The provider identity was not found "
                "in discovery results."
            ),
        )

    # ---------------------------------------------------------
    # Prevent duplicate identity links.
    # ---------------------------------------------------------
    existing_result = await db.execute(
        select(SubjectIdentity).where(
            SubjectIdentity.subject_id == subject.id,
            SubjectIdentity.provider == candidate.provider,
            SubjectIdentity.provider_user_id
            == candidate.provider_user_id,
        )
    )

    existing = (
        existing_result.scalar_one_or_none()
    )

    if existing is not None:
        return {
            "success": True,
            "created": False,
            "identity": {
                "id": str(existing.id),
                "subject_id": str(existing.subject_id),
                "provider": existing.provider,
                "provider_user_id": (
                    existing.provider_user_id
                ),
                "username": existing.username,
                "display_name": (
                    existing.display_name
                ),
                "profile_url": (
                    existing.profile_url
                ),
                "confidence": existing.confidence,
                "identifiers": (
                    existing.identifiers
                ),
            },
        }

    # ---------------------------------------------------------
    # Create provider identity from trusted discovery data.
    # ---------------------------------------------------------
    identity = SubjectIdentity(
        subject_id=subject.id,
        provider=candidate.provider,
        provider_user_id=(
            candidate.provider_user_id
        ),
        username=candidate.username,
        display_name=candidate.display_name,
        profile_url=candidate.profile_url,
        confidence=candidate.confidence,
        identifiers=dict(
            candidate.identifiers
        ),
    )

    db.add(identity)

    try:
        await db.commit()
        await db.refresh(identity)

    except Exception as exc:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to link provider identity: "
                f"{exc}"
            ),
        ) from exc

    return {
        "success": True,
        "created": True,
        "identity": {
            "id": str(identity.id),
            "subject_id": str(identity.subject_id),
            "provider": identity.provider,
            "provider_user_id": (
                identity.provider_user_id
            ),
            "username": identity.username,
            "display_name": identity.display_name,
            "profile_url": identity.profile_url,
            "confidence": identity.confidence,
            "identifiers": identity.identifiers,
        },
    }


@router.get(
    "/{subject_id}/identities",
)
async def list_subject_identities(
    subject_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:

    result = await db.execute(
        select(Subject)
        .options(
            selectinload(
                Subject.identities
            )
        )
        .where(
            Subject.id == subject_id
        )
    )

    subject = result.scalar_one_or_none()

    if subject is None:
        raise HTTPException(
            status_code=404,
            detail="Subject not found.",
        )

    return {
        "success": True,
        "subject_id": str(subject.id),
        "count": len(subject.identities),
        "identities": [
            {
                "id": str(identity.id),
                "provider": identity.provider,
                "provider_user_id": (
                    identity.provider_user_id
                ),
                "username": identity.username,
                "display_name": (
                    identity.display_name
                ),
                "profile_url": (
                    identity.profile_url
                ),
                "confidence": identity.confidence,
                "identifiers": (
                    identity.identifiers
                ),
            }
            for identity in subject.identities
        ],
    }