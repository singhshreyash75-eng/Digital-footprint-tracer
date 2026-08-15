from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProviderRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    provider_name: str
    status: str
    result: dict | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None


class InvestigationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str
    created_at: datetime
    provider_runs: list[ProviderRunResponse] = Field(
        default_factory=list
    )