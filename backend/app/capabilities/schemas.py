from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CapabilityRequest(BaseModel):
    capabilities: list[str] = Field(
        min_length=1,
        max_length=50,
    )


class CapabilityPlanItem(BaseModel):
    capability: str
    supported: bool
    requires_auth: bool = False
    description: str | None = None


class CapabilityPlanResponse(BaseModel):
    subject_id: UUID
    provider: str
    requested: list[str]
    plan: list[CapabilityPlanItem]
    executable: bool


class CapabilityExecutionResponse(BaseModel):
    subject_id: UUID
    provider: str
    requested_capabilities: list[str]
    executed_capabilities: list[str]
    observations: list[dict[str, Any]]
    errors: list[dict[str, Any]]