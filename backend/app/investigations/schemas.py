from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InvestigationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class InvestigationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    status: str
    created_at: datetime