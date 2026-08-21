from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class BlueprintSubject(BaseModel):
    subject_id: UUID

    provider: str
    provider_user_id: str

    username: str | None = None
    display_name: str | None = None
    profile_url: str | None = None

    confidence: float | None = None

    identifiers: dict[str, str] = Field(
        default_factory=dict
    )


class BlueprintSection(BaseModel):
    name: str

    observation_types: list[str] = Field(
        default_factory=list
    )

    observations: list[dict[str, Any]] = Field(
        default_factory=list
    )

    count: int = 0


class BlueprintCapabilities(BaseModel):
    available: dict[str, bool] = Field(
        default_factory=dict
    )


class SubjectBlueprint(BaseModel):
    subject: BlueprintSubject

    capabilities: BlueprintCapabilities

    sections: list[BlueprintSection] = Field(
        default_factory=list
    )

    total_observations: int = 0