from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.investigations.models import (
    ProviderRunStatus,
    TargetType,
)


class TargetCreate(BaseModel):
    type: TargetType
    value: str = Field(
        min_length=1,
        max_length=500,
    )


class TargetResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    type: TargetType
    value: str
    normalized_value: str
    created_at: datetime


class ProviderRunResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    provider_name: str
    status: ProviderRunStatus
    result: dict | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None


class InvestigationCreate(BaseModel):
    name: str = Field(
        min_length=1,
        max_length=255,
    )

    targets: list[TargetCreate] = Field(
        min_length=1
    )


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True
    )

    id: UUID
    name: str
    status: str
    created_at: datetime

    targets: list[TargetResponse] = Field(
        default_factory=list
    )

    provider_runs: list[ProviderRunResponse] = Field(
        default_factory=list
    )