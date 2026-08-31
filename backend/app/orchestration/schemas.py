from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.providers.schemas import ProviderStatus


class ProviderExecutionRequest(BaseModel):
    provider: str

    capabilities: list[str] = Field(
        default_factory=list
    )


class SubjectInvestigationRequest(BaseModel):
    """
    Execute the selected Subject across all registered
    providers that have a usable identity/capability path.

    If providers is empty, every registered provider
    is considered.
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

    status: ProviderStatus

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