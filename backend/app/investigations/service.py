from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.investigations import repository
from app.investigations.models import Investigation, Target
from app.investigations.schemas import InvestigationCreate


async def create_investigation(
    db: AsyncSession,
    data: InvestigationCreate,
) -> Investigation:

    name = data.name.strip()

    if not name:
        raise ValueError(
            "Investigation name cannot be empty."
        )

    investigation = Investigation(
        name=name,
    )

    for target_data in data.targets:
        value = target_data.value.strip()

        if not value:
            continue

        investigation.targets.append(
            Target(
                type=target_data.type,
                value=value,
                normalized_value=value.lower(),
            )
        )

    if not investigation.targets:
        raise ValueError(
            "Investigation must contain at least one valid target."
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