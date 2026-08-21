from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.capabilities.executor import (
    CapabilityExecutor,
)
from app.capabilities.planner import (
    CapabilityPlanner,
)
from app.capabilities.schemas import (
    CapabilityExecutionResponse,
    CapabilityPlanResponse,
    CapabilityRequest,
)
from app.db.session import get_db
from app.investigations.models import Subject
from app.providers.registry import provider_registry


router = APIRouter(
    prefix="/subjects",
    tags=["Capabilities"],
)


@router.post(
    "/{subject_id}/capabilities/plan",
    response_model=CapabilityPlanResponse,
)
async def plan_capabilities(
    subject_id: UUID,
    request: CapabilityRequest,
    db: AsyncSession = Depends(get_db),
) -> CapabilityPlanResponse:

    result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id
        )
    )

    subject = result.scalar_one_or_none()

    if subject is None:
        raise HTTPException(
            status_code=404,
            detail="Subject not found.",
        )

    provider = provider_registry.get(
        subject.provider
    )

    if provider is None:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Provider '{subject.provider}' "
                "is not registered."
            ),
        )

    requested = [
        capability.strip()
        for capability
        in request.capabilities
        if capability.strip()
    ]

    planner = CapabilityPlanner()

    plan = planner.build_plan(
        subject=subject,
        provider=provider,
        requested=requested,
    )

    return CapabilityPlanResponse(
        **plan
    )


@router.post(
    "/{subject_id}/capabilities/execute",
    response_model=CapabilityExecutionResponse,
)
async def execute_capabilities(
    subject_id: UUID,
    request: CapabilityRequest,
    db: AsyncSession = Depends(get_db),
) -> CapabilityExecutionResponse:

    result = await db.execute(
        select(Subject).where(
            Subject.id == subject_id
        )
    )

    subject = result.scalar_one_or_none()

    if subject is None:
        raise HTTPException(
            status_code=404,
            detail="Subject not found.",
        )

    provider = provider_registry.get(
        subject.provider
    )

    if provider is None:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Provider '{subject.provider}' "
                "is not registered."
            ),
        )

    requested = [
        capability.strip()
        for capability
        in request.capabilities
        if capability.strip()
    ]

    planner = CapabilityPlanner()

    plan = planner.build_plan(
        subject=subject,
        provider=provider,
        requested=requested,
    )

    if not plan["executable"]:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "One or more capabilities are unsupported.",
                "plan": plan,
            },
        )

    executor = CapabilityExecutor()

    result = await executor.execute(
        subject=subject,
        provider=provider,
        capabilities=requested,
    )

    return CapabilityExecutionResponse(
        subject_id=subject.id,
        provider=subject.provider,
        requested_capabilities=(
            result["requested_capabilities"]
        ),
        executed_capabilities=(
            result["executed_capabilities"]
        ),
        observations=result["observations"],
        errors=result["errors"],
    )