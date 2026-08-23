from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_db
from app.investigations.models import Subject
from app.orchestration.schemas import (
    SubjectInvestigationRequest,
    SubjectInvestigationResponse,
)
from app.orchestration.service import (
    ProviderOrchestrator,
)


router = APIRouter(
    prefix="/subjects",
    tags=["Orchestration"],
)


@router.post(
    "/{subject_id}/investigate",
    response_model=SubjectInvestigationResponse,
)
async def investigate_subject(
    subject_id: UUID,
    request: SubjectInvestigationRequest,
    db: AsyncSession = Depends(get_db),
) -> SubjectInvestigationResponse:

    result = await db.execute(
        select(Subject)
        .options(
            selectinload(
                Subject.identities
            )
        )
        .where(
            Subject.id == subject_id
        )
    )

    subject = (
        result.scalar_one_or_none()
    )

    if subject is None:
        raise HTTPException(
            status_code=404,
            detail="Subject not found.",
        )

    orchestrator = ProviderOrchestrator()

    return await orchestrator.investigate(
        subject=subject,
        request=request,
    )