from uuid import UUID

from pydantic import BaseModel, Field


class IdentityCandidate(BaseModel):
    """
    Normalized identity candidate returned by provider-specific
    identity resolvers.

    This preserves rich discovery metadata while also providing
    the common provider identity fields required by the Subject
    architecture.
    """

    provider: str
    provider_user_id: str

    username: str | None = None
    display_name: str | None = None
    profile_url: str | None = None
    avatar_url: str | None = None

    # Discovery relevance / confidence
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

    match_type: str = "SEARCH_RELEVANCE"

    reasons: list[str] = Field(
        default_factory=list
    )

    # Public profile enrichment
    public_repos: int | None = None
    followers: int | None = None
    following: int | None = None

    bio: str | None = None
    location: str | None = None
    company: str | None = None
    blog: str | None = None

    # Normalized identifiers used later by Subject selection.
    identifiers: dict[str, str] = Field(
        default_factory=dict
    )


class IdentitySearchRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=255,
    )


class IdentitySearchResponse(BaseModel):
    query: str
    candidates: list[IdentityCandidate] = Field(
        default_factory=list
    )


class IdentitySelectRequest(BaseModel):
    provider: str = Field(
        min_length=1,
        max_length=100,
    )

    username: str = Field(
        min_length=1,
        max_length=255,
    )

    provider_user_id: str | None = Field(
        default=None,
        max_length=255,
    )

    display_name: str | None = Field(
        default=None,
        max_length=255,
    )

    profile_url: str | None = Field(
        default=None,
        max_length=1000,
    )

    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    identifiers: dict[str, str] = Field(
        default_factory=dict
    )


class IdentitySelectResponse(BaseModel):
    subject_id: UUID

    provider: str
    provider_user_id: str

    username: str | None = None
    display_name: str | None = None
    profile_url: str | None = None

    confidence: float | None = None

    identifiers: dict[str, str]
    capabilities: dict[str, bool]

    selected: bool = True


class SubjectResponse(BaseModel):
    subject_id: UUID

    provider: str
    provider_user_id: str

    username: str | None = None
    display_name: str | None = None
    profile_url: str | None = None

    confidence: float | None = None

    identifiers: dict[str, str]
    capabilities: dict[str, bool]


class SubjectCapabilitiesResponse(BaseModel):
    subject_id: UUID

    provider: str
    provider_user_id: str

    capabilities: dict[str, bool]
    supported_identifiers: list[str]