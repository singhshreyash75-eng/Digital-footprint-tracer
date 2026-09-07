from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
)

from pydantic import (
    BaseModel,
    Field,
)

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db

from app.discovery.engine import (
    DiscoveryEngine,
)

from app.discovery.schemas import (
    DiscoveryCandidate,
)

from app.identity.resolution import (
    CrossProviderIdentityResolutionService,
)

from app.investigations.models import (
    Subject,
    SubjectIdentity,
)


router = APIRouter(
    prefix="/subjects",
    tags=["Subject Identities"],
)


# =============================================================
# REQUEST MODELS
# =============================================================


class ResolveSubjectIdentityRequest(
    BaseModel
):
    """
    Resolve one provider-native identity from a known provider
    username / identifier.

    This is the MANUAL FALLBACK path.

    Example:

        provider = "twitch"
        query = "<known Twitch handle>"
    """

    provider: str = Field(
        min_length=1,
        max_length=100,
    )

    query: str = Field(
        min_length=1,
        max_length=255,
    )


class LinkDiscoveredIdentityRequest(
    BaseModel
):
    """
    Explicitly confirm one candidate that the backend has
    already discovered.
    """

    provider: str = Field(
        min_length=1,
        max_length=100,
    )

    provider_user_id: str = Field(
        min_length=1,
        max_length=255,
    )

    query: str = Field(
        min_length=1,
        max_length=255,
    )


class ConfirmCorrelatedIdentityRequest(
    BaseModel
):
    """
    Confirm a candidate returned by /correlate.

    discovery_query is the exact public signal that originally
    produced the candidate. The backend re-runs discovery with
    that signal before persisting the identity.
    """

    provider: str = Field(
        min_length=1,
        max_length=100,
    )

    provider_user_id: str = Field(
        min_length=1,
        max_length=255,
    )

    discovery_query: str = Field(
        min_length=1,
        max_length=255,
    )


class CorrelateSubjectIdentitiesRequest(
    BaseModel
):
    """
    Automatically search for cross-provider identities related
    to the verified Subject anchor.

    The client supplies only the original human-readable query.
    """

    query: str = Field(
        min_length=1,
        max_length=255,
    )


# =============================================================
# SERIALIZATION HELPERS
# =============================================================


def _identity_payload(
    identity: SubjectIdentity,
) -> dict:

    return {
        "id": str(
            identity.id
        ),

        "subject_id": str(
            identity.subject_id
        ),

        "provider":
            identity.provider,

        "provider_user_id":
            identity.provider_user_id,

        "username":
            identity.username,

        "display_name":
            identity.display_name,

        "profile_url":
            identity.profile_url,

        "confidence":
            identity.confidence,

        "identifiers": dict(
            identity.identifiers
            or {}
        ),
    }


def _candidate_payload(
    candidate: DiscoveryCandidate,
) -> dict:

    return {
        "provider":
            candidate.provider,

        "provider_user_id":
            candidate.provider_user_id,

        "username":
            candidate.username,

        "display_name":
            candidate.display_name,

        "profile_url":
            candidate.profile_url,

        "confidence":
            candidate.confidence,

        "match_type":
            candidate.match_type,

        "reasons": list(
            candidate.reasons
        ),

        "identifiers": dict(
            candidate.identifiers
            or {}
        ),

        "discovery_query": (
            str(
                (
                    candidate.metadata
                    or {}
                ).get(
                    "correlation_discovery_query",
                    "",
                )
            ).strip()
            or None
        ),
    }


# =============================================================
# DATABASE HELPERS
# =============================================================


async def _get_subject(
    *,
    subject_id: UUID,
    db: AsyncSession,
    load_identities: bool = False,
) -> Subject:

    statement = (
        select(
            Subject
        )
        .where(
            Subject.id
            == subject_id
        )
    )

    if load_identities:
        statement = (
            statement.options(
                selectinload(
                    Subject.identities
                )
            )
        )

    result = await db.execute(
        statement
    )

    subject = (
        result.scalar_one_or_none()
    )

    if subject is None:
        raise HTTPException(
            status_code=404,
            detail="Subject not found.",
        )

    return subject


async def _find_existing_identity(
    *,
    db: AsyncSession,
    subject_id: UUID,
    provider: str,
    provider_user_id: str,
) -> SubjectIdentity | None:

    result = await db.execute(
        select(
            SubjectIdentity
        )
        .where(
            SubjectIdentity.subject_id
            == subject_id,

            SubjectIdentity.provider
            == provider,

            SubjectIdentity.provider_user_id
            == provider_user_id,
        )
    )

    return (
        result.scalar_one_or_none()
    )


async def _persist_candidate(
    *,
    subject: Subject,
    candidate: DiscoveryCandidate,
    db: AsyncSession,
) -> tuple[
    SubjectIdentity,
    bool,
]:

    provider = (
        candidate.provider
        .strip()
        .lower()
    )

    provider_user_id = (
        candidate.provider_user_id
        .strip()
    )

    existing = (
        await _find_existing_identity(
            db=db,
            subject_id=subject.id,
            provider=provider,
            provider_user_id=(
                provider_user_id
            ),
        )
    )

    if existing is not None:
        return (
            existing,
            False,
        )

    identity = SubjectIdentity(
        subject_id=(
            subject.id
        ),

        provider=(
            provider
        ),

        provider_user_id=(
            provider_user_id
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
            candidate.confidence
        ),

        identifiers=dict(
            candidate.identifiers
            or {}
        ),
    )

    db.add(
        identity
    )

    try:
        await db.commit()

        await db.refresh(
            identity
        )

    except Exception as exc:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to persist "
                "provider identity: "
                f"{exc}"
            ),
        ) from exc

    return (
        identity,
        True,
    )


# =============================================================
# NATIVE IDENTITY MATCHING
# =============================================================


def _normalize_handle(
    value: str | None,
) -> str:

    if not value:
        return ""

    return "".join(
        character.lower()
        for character
        in value.strip()
        if character.isalnum()
    )


def _is_exact_native_match(
    *,
    provider: str,
    query: str,
    candidate: DiscoveryCandidate,
) -> bool:
    """
    Determine whether a provider-native query produced an
    unambiguous exact identity.

    Display-name-only similarity is intentionally insufficient.
    """

    provider = (
        provider
        .strip()
        .lower()
    )

    query_handle = (
        _normalize_handle(
            query
        )
    )

    username_handle = (
        _normalize_handle(
            candidate.username
        )
    )

    if (
        query_handle
        and username_handle
        and query_handle
        == username_handle
    ):
        return True

    match_type = (
        candidate.match_type
        .strip()
        .upper()
    )

    exact_types = {
        "EXACT_USERNAME",
        "EXACT_LOGIN",
        "EXACT_IDENTIFIER_MATCH",
    }

    if (
        match_type
        in exact_types
        and candidate.confidence
        >= 0.95
    ):
        return True

    # ---------------------------------------------------------
    # SteamID64
    # ---------------------------------------------------------

    if provider == "steam":

        steam_id = (
            candidate.identifiers.get(
                "steamid64"
            )
        )

        if (
            steam_id
            and str(
                steam_id
            ).strip()
            == query.strip()
        ):
            return True

    # ---------------------------------------------------------
    # Stack Exchange provider-native ID
    # ---------------------------------------------------------

    if provider == "stackexchange":

        provider_value = (
            candidate.provider_user_id
            .strip()
        )

        if (
            provider_value
            and provider_value
            == query.strip()
        ):
            return True

    return False


# =============================================================
# PROVIDER-SPECIFIC DISCOVERY HELPER
# =============================================================


async def _discover_provider_candidates(
    *,
    provider: str,
    query: str,
) -> list[
    DiscoveryCandidate
]:

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
                "Unable to resolve "
                f"{provider} identity: "
                f"{exc}"
            ),
        ) from exc

    return [
        candidate
        for candidate
        in discovered
        if (
            candidate.provider
            .strip()
            .lower()
            == provider
        )
    ]


# =============================================================
# AUTOMATIC CROSS-PROVIDER CORRELATION
# =============================================================


@router.post(
    "/{subject_id}/correlate",
)
async def correlate_subject_identities(
    subject_id: UUID,
    request: CorrelateSubjectIdentitiesRequest,
    db: AsyncSession = Depends(
        get_db
    ),
) -> dict:
    """
    Automatically search for provider identities related to
    the verified anchor Subject.

    Flow:

        verified Subject
              ↓
        reusable public signals
              ↓
        provider discovery
              ↓
        cross-provider scoring
              ↓
        strong unique match → auto-link
        ambiguous match     → return candidates
        no evidence         → unresolved

    Manual provider input is NOT required by this endpoint.
    """

    query = (
        request.query
        .strip()
    )

    if not query:
        raise HTTPException(
            status_code=400,
            detail=(
                "Correlation query "
                "cannot be empty."
            ),
        )

    subject = (
        await _get_subject(
            subject_id=subject_id,
            db=db,
            load_identities=True,
        )
    )

    # ---------------------------------------------------------
    # Reconstruct verified anchor candidate.
    # ---------------------------------------------------------

    anchor = DiscoveryCandidate(
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
            if subject.confidence
            is not None
            else 1.0
        ),

        match_type=(
            "VERIFIED_ANCHOR"
        ),

        reasons=[
            (
                "Operator-selected "
                "verified anchor identity"
            )
        ],

        identifiers=dict(
            subject.identifiers
            or {}
        ),

        metadata={},
    )

    resolver = (
        CrossProviderIdentityResolutionService()
    )

    try:
        resolution = (
            await resolver.resolve(
                anchor=anchor,
                original_query=query,
            )
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                "Cross-provider identity "
                "correlation failed: "
                f"{exc}"
            ),
        ) from exc

    # ---------------------------------------------------------
    # Already-linked provider identities.
    # ---------------------------------------------------------

    linked_provider_names = {
        identity.provider
        .strip()
        .lower()
        for identity
        in subject.identities
    }

    auto_linked: list[
        dict
    ] = []

    # ---------------------------------------------------------
    # Persist uniquely strong automatic correlations.
    # ---------------------------------------------------------

    for provider_name, group in (
        resolution.providers.items()
    ):

        normalized_provider = (
            provider_name
            .strip()
            .lower()
        )

        if (
            normalized_provider
            in linked_provider_names
        ):
            continue

        correlation_result = (
            group.auto_link_candidate
        )

        if (
            correlation_result
            is None
        ):
            continue

        identity, created = (
            await _persist_candidate(
                subject=subject,
                candidate=(
                    correlation_result
                    .candidate
                ),
                db=db,
            )
        )

        linked_provider_names.add(
            normalized_provider
        )

        auto_linked.append(
            {
                "created":
                    created,

                "correlation_score":
                    correlation_result.score,

                "correlation_percent":
                    round(
                        correlation_result.score
                        * 100
                    ),

                "correlation_reasons":
                    list(
                        correlation_result.reasons
                    ),

                "identity":
                    _identity_payload(
                        identity
                    ),
            }
        )

    # ---------------------------------------------------------
    # Ranked provider correlation output.
    # ---------------------------------------------------------

    provider_results: dict[
        str,
        dict,
    ] = {}

    for provider_name, group in (
        resolution.providers.items()
    ):

        normalized_provider = (
            provider_name
            .strip()
            .lower()
        )

        provider_results[
            normalized_provider
        ] = {
            "resolved": (
                normalized_provider
                in linked_provider_names
            ),

            "auto_link_available": (
                group.auto_link_candidate
                is not None
            ),

            "candidate_count": len(
                group.candidates
            ),

            "candidates": [
                {
                    **_candidate_payload(
                        result.candidate
                    ),

                    "correlation_score":
                        result.score,

                    "correlation_percent":
                        round(
                            result.score
                            * 100
                        ),

                    "correlation_reasons":
                        list(
                            result.reasons
                        ),

                    "auto_link":
                        result.auto_link,
                }
                for result
                in group.candidates
            ],
        }

    return {
        "success": True,

        "subject_id": str(
            subject.id
        ),

        "query":
            query,

        "signals":
            list(
                resolution.signals
            ),

        "discovered_candidate_count":
            len(
                resolution
                .discovered_candidates
            ),

        "auto_linked":
            auto_linked,

        "providers":
            provider_results,
    }


# =============================================================
# MANUAL PROVIDER-NATIVE RESOLUTION
# =============================================================


@router.post(
    "/{subject_id}/identities/resolve",
)
async def resolve_subject_identity(
    subject_id: UUID,
    request: ResolveSubjectIdentityRequest,
    db: AsyncSession = Depends(
        get_db
    ),
) -> dict:
    """
    Manual fallback.

    Resolve a known provider-native username or identifier.

    This endpoint is intentionally separate from automatic
    cross-provider correlation.
    """

    provider = (
        request.provider
        .strip()
        .lower()
    )

    query = (
        request.query
        .strip()
    )

    if not provider:
        raise HTTPException(
            status_code=400,
            detail=(
                "Provider cannot "
                "be empty."
            ),
        )

    if not query:
        raise HTTPException(
            status_code=400,
            detail=(
                "Provider identity query "
                "cannot be empty."
            ),
        )

    subject = (
        await _get_subject(
            subject_id=subject_id,
            db=db,
        )
    )

    candidates = (
        await _discover_provider_candidates(
            provider=provider,
            query=query,
        )
    )

    if not candidates:
        return {
            "success": True,

            "resolved": False,

            "created": False,

            "subject_id": str(
                subject.id
            ),

            "provider":
                provider,

            "query":
                query,

            "reason":
                "NO_PROVIDER_CANDIDATES",

            "identity":
                None,

            "candidates":
                [],
        }

    exact_matches = [
        candidate
        for candidate
        in candidates
        if _is_exact_native_match(
            provider=provider,
            query=query,
            candidate=candidate,
        )
    ]

    if len(
        exact_matches
    ) == 1:

        identity, created = (
            await _persist_candidate(
                subject=subject,
                candidate=(
                    exact_matches[0]
                ),
                db=db,
            )
        )

        return {
            "success": True,

            "resolved": True,

            "created":
                created,

            "subject_id": str(
                subject.id
            ),

            "provider":
                provider,

            "query":
                query,

            "reason":
                "EXACT_PROVIDER_IDENTITY",

            "identity":
                _identity_payload(
                    identity
                ),

            "candidates":
                [],
        }

    return {
        "success": True,

        "resolved": False,

        "created": False,

        "subject_id": str(
            subject.id
        ),

        "provider":
            provider,

        "query":
            query,

        "reason":
            (
                "AMBIGUOUS_PROVIDER_IDENTITY"
            ),

        "identity":
            None,

        "candidates": [
            _candidate_payload(
                candidate
            )
            for candidate
            in candidates
        ],
    }


# =============================================================
# CORRELATED CANDIDATE CONFIRMATION
# =============================================================


@router.post(
    "/{subject_id}/identities/confirm-correlated",
)
async def confirm_correlated_identity(
    subject_id: UUID,
    request: ConfirmCorrelatedIdentityRequest,
    db: AsyncSession = Depends(
        get_db
    ),
) -> dict:
    provider = (
        request.provider
        .strip()
        .lower()
    )

    provider_user_id = (
        request.provider_user_id
        .strip()
    )

    discovery_query = (
        request.discovery_query
        .strip()
    )

    subject = (
        await _get_subject(
            subject_id=subject_id,
            db=db,
        )
    )

    candidates = (
        await _discover_provider_candidates(
            provider=provider,
            query=discovery_query,
        )
    )

    candidate = next(
        (
            item
            for item in candidates
            if item.provider_user_id
            == provider_user_id
        ),
        None,
    )

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "The correlated identity could not be "
                "re-verified with its discovery signal."
            ),
        )

    identity, created = (
        await _persist_candidate(
            subject=subject,
            candidate=candidate,
            db=db,
        )
    )

    return {
        "success": True,
        "resolved": True,
        "created": created,
        "identity": _identity_payload(
            identity
        ),
    }


# =============================================================
# EXPLICIT CANDIDATE CONFIRMATION
# =============================================================


@router.post(
    "/{subject_id}/identities",
)
async def link_subject_identity(
    subject_id: UUID,
    request: LinkDiscoveredIdentityRequest,
    db: AsyncSession = Depends(
        get_db
    ),
) -> dict:
    """
    Explicitly link one candidate after operator confirmation.

    Discovery is repeated before persistence so the client
    cannot fabricate provider IDs or profile metadata.
    """

    provider = (
        request.provider
        .strip()
        .lower()
    )

    provider_user_id = (
        request.provider_user_id
        .strip()
    )

    query = (
        request.query
        .strip()
    )

    if not provider:
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

    if not query:
        raise HTTPException(
            status_code=400,
            detail=(
                "Discovery query "
                "cannot be empty."
            ),
        )

    subject = (
        await _get_subject(
            subject_id=subject_id,
            db=db,
        )
    )

    candidates = (
        await _discover_provider_candidates(
            provider=provider,
            query=query,
        )
    )

    candidate = next(
        (
            item
            for item
            in candidates
            if (
                item.provider_user_id
                == provider_user_id
            )
        ),
        None,
    )

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "The requested provider "
                "identity was not found "
                "in verified discovery "
                "results."
            ),
        )

    identity, created = (
        await _persist_candidate(
            subject=subject,
            candidate=candidate,
            db=db,
        )
    )

    return {
        "success": True,

        "resolved": True,

        "created":
            created,

        "identity":
            _identity_payload(
                identity
            ),
    }


# =============================================================
# LIST LINKED PROVIDER IDENTITIES
# =============================================================


@router.get(
    "/{subject_id}/identities",
)
async def list_subject_identities(
    subject_id: UUID,
    db: AsyncSession = Depends(
        get_db
    ),
) -> dict:

    subject = (
        await _get_subject(
            subject_id=subject_id,
            db=db,
            load_identities=True,
        )
    )

    identities = sorted(
        subject.identities,
        key=lambda identity: (
            identity.provider.lower(),
            (
                identity.username
                or ""
            ).lower(),
        ),
    )

    return {
        "success": True,

        "subject_id": str(
            subject.id
        ),

        "count": len(
            identities
        ),

        "identities": [
            _identity_payload(
                identity
            )
            for identity
            in identities
        ],
    }