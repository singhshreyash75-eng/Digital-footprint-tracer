from pydantic import BaseModel, Field


class IdentitySearchRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=200,
    )


class IdentityCandidate(BaseModel):
    username: str
    display_name: str | None = None
    profile_url: str
    avatar_url: str | None = None

    score: float = Field(
        ge=0.0,
        le=1.0,
    )

    confidence_percent: int = Field(
        ge=0,
        le=100,
    )

    match_type: str
    reasons: list[str] = Field(
        default_factory=list,
    )

    public_repos: int | None = None
    followers: int | None = None
    following: int | None = None

    bio: str | None = None
    location: str | None = None
    company: str | None = None
    blog: str | None = None


class IdentitySearchResponse(BaseModel):
    query: str
    candidates: list[IdentityCandidate]


class IdentitySelectRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=200,
    )

    provider: str = "github"

    username: str = Field(
        min_length=1,
        max_length=100,
    )


class IdentitySelectResponse(BaseModel):
    provider: str
    username: str
    selected: bool