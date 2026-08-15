from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.investigations import repository
from app.investigations.models import Investigation, Target
from app.investigations.schemas import InvestigationCreate


async def create_investigation(
    db: AsyncSession,
    data: InvestigationCreate,
) -> Investigation:
    investigation = Investigation(
        name=data.name.strip(),
    )

    for target_data in data.targets:
        value = target_data.value.strip()

        investigation.targets.append(
            Target(
                type=target_data.type,
                value=value,
                normalized_value=value.lower(),
            )
        )

    return await repository.create_investigation(
        db,
        investigation,
    )


async def get_investigation(
    db: AsyncSession,
    investigation_id: UUID,
) -> Investigation | None:
    return await repository.get_investigation(
        db,
        investigation_id,
    )