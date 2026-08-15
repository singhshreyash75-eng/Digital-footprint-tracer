from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.investigations import service
from app.investigations.schemas import (
    InvestigationCreate,
    InvestigationResponse,
)
from app.jobs.tasks import run_username_provider

router = APIRouter(
    prefix="/investigations",
    tags=["Investigations"],
)


@router.post(
    "",
    response_model=InvestigationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_investigation(
    data: InvestigationCreate,
    db: AsyncSession = Depends(get_db),
):
    investigation = await service.create_investigation(db, data)

    run_username_provider.delay(
        str(investigation.id),
        data.name.strip(),
    )

    return investigation


@router.get(
    "/{investigation_id}",
    response_model=InvestigationResponse,
)
async def get_investigation(
    investigation_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    investigation = await service.get_investigation(
        db,
        investigation_id,
    )

    if investigation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Investigation not found",
        )

    return investigation