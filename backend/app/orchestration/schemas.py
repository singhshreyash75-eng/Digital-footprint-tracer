from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ProviderExecutionRequest(BaseModel):
    provider: str
    capabilities: list[str] = Field(
        default_factory=list
    )


class SubjectInvestigationRequest(BaseModel):
    """
    Execute the selected subject across all providers that
    have a usable identity/capability path for that subject.

    If providers is empty, the orchestrator considers every
    registered provider.
    """

    providers: list[str] = Field(
        default_factory=list
    )

    capability_overrides: dict[
        str,
        list[str],
    ] = Field(
        default_factory=dict
    )


class ProviderInvestigationResult(BaseModel):
    provider: str

    supported: bool
    executed: bool

    requested_capabilities: list[str] = Field(
        default_factory=list
    )

    executed_capabilities: list[str] = Field(
        default_factory=list
    )

    observations: list[dict[str, Any]] = Field(
        default_factory=list
    )

    errors: list[dict[str, Any]] = Field(
        default_factory=list
    )


class SubjectInvestigationResponse(BaseModel):
    subject_id: UUID

    provider_results: list[
        ProviderInvestigationResult
    ] = Field(
        default_factory=list
    )

    total_providers: int
    executed_providers: int