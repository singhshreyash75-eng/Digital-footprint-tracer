from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.investigations.models import Investigation


async def create_investigation(
    db: AsyncSession,
    investigation: Investigation,
) -> Investigation:
    db.add(investigation)
    await db.commit()

    result = await db.execute(
        select(Investigation)
        .options(selectinload(Investigation.provider_runs))
        .where(Investigation.id == investigation.id)
    )

    return result.scalar_one()


async def get_investigation(
    db: AsyncSession,
    investigation_id: UUID,
) -> Investigation | None:
    result = await db.execute(
        select(Investigation)
        .options(selectinload(Investigation.provider_runs))
        .where(Investigation.id == investigation_id)
    )

    return result.scalar_one_or_none()