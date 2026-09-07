from uuid import UUID

from pydantic import BaseModel, Field


class IdentityCandidate(BaseModel):
    """
    Public identity candidate returned by discovery.
    """

    provider: str
    provider_user_id: str

    username: str | None = None
    display_name: str | None = None

    profile_url: str | None = None
    avatar_url: str | None = None

    score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    confidence_percent: int = Field(
        default=0,
        ge=0,
        le=100,
    )

    match_type: str = (
        "SEARCH_RELEVANCE"
    )

    reasons: list[str] = Field(
        default_factory=list
    )

    public_repos: int | None = None
    followers: int | None = None
    following: int | None = None

    bio: str | None = None
    location: str | None = None
    company: str | None = None
    blog: str | None = None

    identifiers: dict[
        str,
        str,
    ] = Field(
        default_factory=dict
    )


class IdentitySearchRequest(
    BaseModel
):
    query: str = Field(
        min_length=1,
        max_length=255,
    )


class IdentitySearchResponse(
    BaseModel
):
    query: str

    candidates: list[
        IdentityCandidate
    ] = Field(
        default_factory=list
    )


class IdentitySelectRequest(
    BaseModel
):
    """
    Select an anchor identity.

    Backend re-runs discovery and verifies the selected
    provider identity before creating the Subject.
    """

    query: str = Field(
        min_length=1,
        max_length=255,
    )

    provider: str = Field(
        min_length=1,
        max_length=100,
    )

    provider_user_id: str = Field(
        min_length=1,
        max_length=255,
    )


class CorrelatedIdentity(
    BaseModel
):
    provider: str

    provider_user_id: str

    username: str | None = None

    display_name: str | None = None

    profile_url: str | None = None

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    confidence_percent: int = Field(
        ge=0,
        le=100,
    )

    reasons: list[str] = Field(
        default_factory=list
    )

    identifiers: dict[
        str,
        str,
    ] = Field(
        default_factory=dict
    )

    auto_linked: bool = False


class IdentitySelectResponse(
    BaseModel
):
    subject_id: UUID

    provider: str

    provider_user_id: str

    username: str | None = None

    display_name: str | None = None

    profile_url: str | None = None

    confidence: float | None = None

    identifiers: dict[
        str,
        str,
    ]

    capabilities: dict[
        str,
        bool,
    ]

    selected: bool = True

    linked_identities: list[
        CorrelatedIdentity
    ] = Field(
        default_factory=list
    )

    possible_identities: list[
        CorrelatedIdentity
    ] = Field(
        default_factory=list
    )


class SubjectResponse(
    BaseModel
):
    subject_id: UUID

    provider: str

    provider_user_id: str

    username: str | None = None

    display_name: str | None = None

    profile_url: str | None = None

    confidence: float | None = None

    identifiers: dict[
        str,
        str,
    ]

    capabilities: dict[
        str,
        bool,
    ]

    linked_identities: list[
        CorrelatedIdentity
    ] = Field(
        default_factory=list
    )


class SubjectCapabilitiesResponse(
    BaseModel
):
    subject_id: UUID

    provider: str

    provider_user_id: str

    capabilities: dict[
        str,
        bool,
    ]

    supported_identifiers: list[
        str
    ]