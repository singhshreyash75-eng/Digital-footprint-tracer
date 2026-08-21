from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.blueprints.builder import BlueprintBuilder
from app.blueprints.schemas import SubjectBlueprint
from app.db.session import get_db
from app.investigations.models import (
    ProviderRun,
    Subject,
)


router = APIRouter(
    prefix="/subjects",
    tags=["Subjects"],
)


@router.get(
    "/{subject_id}/blueprint",
    response_model=SubjectBlueprint,
)
async def get_subject_blueprint(
    subject_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SubjectBlueprint:

    subject_result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id
        )
    )

    subject = (
        subject_result.scalar_one_or_none()
    )

    if subject is None:
        raise HTTPException(
            status_code=404,
            detail="Subject not found.",
        )

    runs_result = await db.execute(
        select(ProviderRun).where(
            ProviderRun.subject_id == subject.id,
            ProviderRun.provider_name == subject.provider,
        )
    )

    provider_runs = list(
        runs_result.scalars().all()
    )

    builder = BlueprintBuilder()

    return builder.build(
        subject=subject,
        provider_runs=provider_runs,
    )