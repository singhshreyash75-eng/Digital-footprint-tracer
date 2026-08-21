from typing import Any

from pydantic import BaseModel, Field


class DiscoveryRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=255,
    )


class DiscoveryCandidate(BaseModel):
    provider: str
    provider_user_id: str

    username: str | None = None
    display_name: str | None = None
    profile_url: str | None = None
    avatar_url: str | None = None

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )

    match_type: str = "SEARCH_RELEVANCE"

    reasons: list[str] = Field(
        default_factory=list
    )

    identifiers: dict[str, str] = Field(
        default_factory=dict
    )

    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class DiscoveryResponse(BaseModel):
    query: str
    candidates: list[DiscoveryCandidate]
    total: int