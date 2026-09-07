from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from sqlalchemy import select

from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

from sqlalchemy.orm import (
    selectinload,
)

from app.db.session import get_db

from app.discovery.engine import (
    DiscoveryEngine,
)

from app.discovery.schemas import (
    DiscoveryCandidate,
)

from app.identity.correlation import (
    CrossProviderIdentityCorrelator,
)

from app.identity.schemas import (
    CorrelatedIdentity,
    IdentityCandidate,
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

from app.providers.registry import (
    provider_registry,
)


router = APIRouter(
    prefix="/identity",
    tags=[
        "Identity Resolution"
    ],
)


def _to_identity_candidate(
    candidate: DiscoveryCandidate,
) -> IdentityCandidate:
    """
    Convert the provider-neutral discovery representation
    into the frontend-compatible identity candidate.
    """

    return IdentityCandidate(
        provider=(
            candidate.provider
        ),

        provider_user_id=(
            candidate.provider_user_id
        ),

        username=(
            candidate.username
        ),

        display_name=(
            candidate.display_name
        ),

        profile_url=(
            candidate.profile_url
        ),

        avatar_url=(
            candidate.avatar_url
        ),

        score=(
            candidate.confidence
        ),

        confidence_percent=round(
            candidate.confidence
            * 100
        ),

        match_type=(
            candidate.match_type
        ),

        reasons=list(
            candidate.reasons
        ),

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

        bio=(
            candidate.metadata.get(
                "bio"
            )
        ),

        location=(
            candidate.metadata.get(
                "location"
            )
        ),

        company=(
            candidate.metadata.get(
                "company"
            )
        ),

        blog=(
            candidate.metadata.get(
                "blog"
            )
        ),
    )


def _identity_response(
    *,
    candidate: DiscoveryCandidate,
    confidence: float,
    reasons: list[str],
    auto_linked: bool,
) -> CorrelatedIdentity:

    return CorrelatedIdentity(
        provider=(
            candidate.provider
        ),

        provider_user_id=(
            candidate.provider_user_id
        ),

        username=(
            candidate.username
        ),

        display_name=(
            candidate.display_name
        ),

        profile_url=(
            candidate.profile_url
        ),

        confidence=(
            confidence
        ),

        confidence_percent=round(
            confidence
            * 100
        ),

        reasons=list(
            reasons
        ),

        identifiers=dict(
            candidate.identifiers
        ),

        auto_linked=(
            auto_linked
        ),
    )


@router.post(
    "/search",
    response_model=(
        IdentitySearchResponse
    ),
)
async def search_identity(
    request: IdentitySearchRequest,
) -> IdentitySearchResponse:

    query = (
        request.query.strip()
    )

    if not query:
        raise HTTPException(
            status_code=400,
            detail=(
                "Search query cannot "
                "be empty."
            ),
        )

    engine = DiscoveryEngine()

    try:
        discovered = (
            await engine.search(
                query
            )
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Identity discovery "
                f"failed: {exc}"
            ),
        ) from exc

    return IdentitySearchResponse(
        query=query,

        candidates=[
            _to_identity_candidate(
                candidate
            )
            for candidate
            in discovered
        ],
    )


@router.post(
    "/select",
    response_model=(
        IdentitySelectResponse
    ),
)
async def select_identity(
    request: IdentitySelectRequest,
    db: AsyncSession = Depends(
        get_db
    ),
) -> IdentitySelectResponse:

    query = (
        request.query.strip()
    )

    provider_name = (
        request.provider
        .strip()
        .lower()
    )

    provider_user_id = (
        request.provider_user_id
        .strip()
    )

    if not query:
        raise HTTPException(
            status_code=400,
            detail=(
                "Selection query "
                "cannot be empty."
            ),
        )

    if not provider_name:
        raise HTTPException(
            status_code=400,
            detail=(
                "Provider cannot "
                "be empty."
            ),
        )

    if not provider_user_id:
        raise HTTPException(
            status_code=400,
            detail=(
                "Provider user ID "
                "cannot be empty."
            ),
        )

    provider = (
        provider_registry.get(
            provider_name
        )
    )

    if provider is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Provider "
                f"'{provider_name}' "
                "is not registered."
            ),
        )

    # =========================================================
    # Re-run provider-neutral discovery.
    # =========================================================

    engine = DiscoveryEngine()

    try:
        discovered = (
            await engine.search(
                query
            )
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Unable to validate "
                "selected identity: "
                f"{exc}"
            ),
        ) from exc

    # =========================================================
    # Verify selected anchor.
    # =========================================================

    selected = next(
        (
            candidate
            for candidate
            in discovered
            if (
                candidate.provider
                .strip()
                .lower()
                == provider_name

                and

                candidate.provider_user_id
                == provider_user_id
            )
        ),
        None,
    )

    if selected is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "The selected identity "
                "was not found in the "
                "verified discovery "
                "results."
            ),
        )

    # =========================================================
    # Create logical Subject.
    # =========================================================

    subject = Subject(
        provider=(
            selected.provider
        ),

        provider_user_id=(
            selected.provider_user_id
        ),

        username=(
            selected.username
        ),

        display_name=(
            selected.display_name
        ),

        profile_url=(
            selected.profile_url
        ),

        confidence=(
            selected.confidence
        ),

        identifiers=dict(
            selected.identifiers
        ),

        capabilities=(
            provider.get_capabilities()
        ),
    )

    db.add(
        subject
    )

    # Flush obtains subject.id without committing the
    # transaction yet.
    try:
        await db.flush()

    except Exception as exc:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to create "
                f"selected subject: {exc}"
            ),
        ) from exc

    # =========================================================
    # Persist selected anchor as SubjectIdentity.
    # =========================================================

    anchor_identity = (
        SubjectIdentity(
            subject_id=(
                subject.id
            ),

            provider=(
                selected.provider
            ),

            provider_user_id=(
                selected.provider_user_id
            ),

            username=(
                selected.username
            ),

            display_name=(
                selected.display_name
            ),

            profile_url=(
                selected.profile_url
            ),

            confidence=(
                selected.confidence
            ),

            identifiers=dict(
                selected.identifiers
            ),
        )
    )

    db.add(
        anchor_identity
    )

    # =========================================================
    # Cross-provider correlation.
    # =========================================================

    correlator = (
        CrossProviderIdentityCorrelator()
    )

    correlated = (
        correlator.correlate(
            anchor=selected,
            candidates=discovered,
        )
    )

    linked_responses: list[
        CorrelatedIdentity
    ] = []

    possible_responses: list[
        CorrelatedIdentity
    ] = []

    # Only one automatically linked identity per provider.
    linked_providers = {
        provider_name
    }

    for result in correlated:
        candidate = (
            result.candidate
        )

        candidate_provider = (
            candidate.provider
            .strip()
            .lower()
        )

        response_item = (
            _identity_response(
                candidate=candidate,
                confidence=(
                    result.score
                ),
                reasons=(
                    result.reasons
                ),
                auto_linked=(
                    result.auto_link
                ),
            )
        )

        if (
            result.auto_link
            and candidate_provider
            not in linked_providers
        ):
            db.add(
                SubjectIdentity(
                    subject_id=(
                        subject.id
                    ),

                    provider=(
                        candidate.provider
                    ),

                    provider_user_id=(
                        candidate.provider_user_id
                    ),

                    username=(
                        candidate.username
                    ),

                    display_name=(
                        candidate.display_name
                    ),

                    profile_url=(
                        candidate.profile_url
                    ),

                    confidence=(
                        result.score
                    ),

                    identifiers=dict(
                        candidate.identifiers
                    ),
                )
            )

            linked_providers.add(
                candidate_provider
            )

            linked_responses.append(
                response_item
            )

        else:
            possible_responses.append(
                response_item
            )

    # =========================================================
    # Commit Subject + provider identities atomically.
    # =========================================================

    try:
        await db.commit()

        await db.refresh(
            subject
        )

    except Exception as exc:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to persist "
                "selected identity "
                f"cluster: {exc}"
            ),
        ) from exc

    return IdentitySelectResponse(
        subject_id=(
            subject.id
        ),

        provider=(
            subject.provider
        ),

        provider_user_id=(
            subject.provider_user_id
        ),

        username=(
            subject.username
        ),

        display_name=(
            subject.display_name
        ),

        profile_url=(
            subject.profile_url
        ),

        confidence=(
            subject.confidence
        ),

        identifiers=dict(
            subject.identifiers
            or {}
        ),

        capabilities=dict(
            subject.capabilities
            or {}
        ),

        selected=True,

        linked_identities=(
            linked_responses
        ),

        possible_identities=(
            possible_responses
        ),
    )


@router.get(
    "/subjects/{subject_id}",
    response_model=SubjectResponse,
)
async def get_subject(
    subject_id: UUID,
    db: AsyncSession = Depends(
        get_db
    ),
) -> SubjectResponse:

    result = await db.execute(
        select(
            Subject
        )
        .options(
            selectinload(
                Subject.identities
            )
        )
        .where(
            Subject.id
            == subject_id
        )
    )

    subject = (
        result.scalar_one_or_none()
    )

    if subject is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Selected subject "
                "not found."
            ),
        )

    linked_identities = [
        CorrelatedIdentity(
            provider=(
                identity.provider
            ),

            provider_user_id=(
                identity.provider_user_id
            ),

            username=(
                identity.username
            ),

            display_name=(
                identity.display_name
            ),

            profile_url=(
                identity.profile_url
            ),

            confidence=(
                identity.confidence
                or 0.0
            ),

            confidence_percent=round(
                (
                    identity.confidence
                    or 0.0
                )
                * 100
            ),

            reasons=[
                (
                    "Persisted provider "
                    "identity"
                )
            ],

            identifiers=dict(
                identity.identifiers
                or {}
            ),

            auto_linked=True,
        )
        for identity
        in subject.identities
    ]

    return SubjectResponse(
        subject_id=(
            subject.id
        ),

        provider=(
            subject.provider
        ),

        provider_user_id=(
            subject.provider_user_id
        ),

        username=(
            subject.username
        ),

        display_name=(
            subject.display_name
        ),

        profile_url=(
            subject.profile_url
        ),

        confidence=(
            subject.confidence
        ),

        identifiers=dict(
            subject.identifiers
            or {}
        ),

        capabilities=dict(
            subject.capabilities
            or {}
        ),

        linked_identities=(
            linked_identities
        ),
    )


@router.get(
    "/subjects/{subject_id}/capabilities",
    response_model=(
        SubjectCapabilitiesResponse
    ),
)
async def get_subject_capabilities(
    subject_id: UUID,
    db: AsyncSession = Depends(
        get_db
    ),
) -> SubjectCapabilitiesResponse:

    result = await db.execute(
        select(
            Subject
        ).where(
            Subject.id
            == subject_id
        )
    )

    subject = (
        result.scalar_one_or_none()
    )

    if subject is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Selected subject "
                "not found."
            ),
        )

    provider = (
        provider_registry.get(
            subject.provider
        )
    )

    if provider is None:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Provider "
                f"'{subject.provider}' "
                "is no longer "
                "registered."
            ),
        )

    capabilities = (
        provider.get_capabilities()
    )

    supported_identifiers = (
        provider
        .get_supported_identifiers()
    )

    subject.capabilities = (
        capabilities
    )

    await db.commit()

    return (
        SubjectCapabilitiesResponse(
            subject_id=(
                subject.id
            ),

            provider=(
                subject.provider
            ),

            provider_user_id=(
                subject.provider_user_id
            ),

            capabilities=(
                capabilities
            ),

            supported_identifiers=(
                supported_identifiers
            ),
        )
    )