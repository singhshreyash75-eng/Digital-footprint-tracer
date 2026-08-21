from datetime import datetime, timezone
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
from app.investigations.models import (
    ProviderRun,
    ProviderRunStatus,
    Subject,
)
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
        for capability in request.capabilities
        if capability.strip()
    ]

    if not requested:
        raise HTTPException(
            status_code=400,
            detail="At least one capability is required.",
        )

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
        for capability in request.capabilities
        if capability.strip()
    ]

    if not requested:
        raise HTTPException(
            status_code=400,
            detail="At least one capability is required.",
        )

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
                "message": (
                    "One or more capabilities "
                    "are unsupported."
                ),
                "plan": plan,
            },
        )

    executor = CapabilityExecutor()

    started_at = datetime.now(timezone.utc)

    execution_result = await executor.execute(
        subject=subject,
        provider=provider,
        capabilities=requested,
    )

    completed_at = datetime.now(timezone.utc)

    # ---------------------------------------------------------
    # Persist evidence against the selected Subject.
    # ---------------------------------------------------------
    status_value = execution_result.get(
        "provider_result_status",
        "FAILED",
    )

    try:
        provider_status = ProviderRunStatus(
            status_value
        )
    except ValueError:
        provider_status = (
            ProviderRunStatus.FAILED
        )

    errors = execution_result.get(
        "errors",
        [],
    )

    provider_run = ProviderRun(
        investigation_id=None,
        subject_id=subject.id,
        provider_name=provider.name,
        status=provider_status,
        result={
            "requested_capabilities": requested,
            "executed_capabilities": (
                execution_result.get(
                    "executed_capabilities",
                    [],
                )
            ),
            "observations": (
                execution_result.get(
                    "observations",
                    [],
                )
            ),
            "errors": errors,
        },
        error_code=(
            errors[0].get("code")
            if errors
            else None
        ),
        error_message=(
            errors[0].get("message")
            if errors
            else None
        ),
        started_at=started_at,
        completed_at=completed_at,
    )

    db.add(provider_run)

    try:
        await db.commit()

    except Exception as exc:
        await db.rollback()

        raise HTTPException(
            status_code=500,
            detail=(
                f"Failed to persist capability evidence: "
                f"{exc}"
            ),
        ) from exc

    return CapabilityExecutionResponse(
        subject_id=subject.id,
        provider=subject.provider,
        requested_capabilities=(
            execution_result[
                "requested_capabilities"
            ]
        ),
        executed_capabilities=(
            execution_result[
                "executed_capabilities"
            ]
        ),
        observations=execution_result[
            "observations"
        ],
        errors=execution_result[
            "errors"
        ],
    )