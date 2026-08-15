import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import UUID

from app.db.sync_session import SessionLocal
from app.investigations.models import (
    Investigation,
    InvestigationStatus,
    ProviderRun,
    ProviderRunStatus,
)
from app.jobs.celery_app import celery_app
from app.providers.registry import provider_registry
from app.providers.username.test_provider import TestUsernameProvider


@celery_app.task(name="run_username_provider")
def run_username_provider(
    investigation_id: str,
    target_id: str,
    username: str,
) -> dict[str, Any]:
    investigation_uuid = UUID(investigation_id)
    target_uuid = UUID(target_id)

    with SessionLocal() as db:
        investigation = db.get(
            Investigation,
            investigation_uuid,
        )

        if investigation is None:
            raise ValueError("Investigation not found")

        provider = provider_registry.get("test_username")

        if provider is None:
            provider = TestUsernameProvider()
            provider_registry.register(provider)

        investigation.status = InvestigationStatus.RUNNING

        provider_run = ProviderRun(
            investigation_id=investigation_uuid,
            provider_name=provider.name,
            status=ProviderRunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
        )

        db.add(provider_run)
        db.commit()
        db.refresh(provider_run)

        try:
            target = SimpleNamespace(
                id=target_uuid,
                investigation_id=investigation_uuid,
                normalized_value=username,
            )

            result = asyncio.run(provider.execute(target))

            provider_run.status = ProviderRunStatus(result.status.value)
            provider_run.result = {
                "observations": [
                    {
                        "type": obs.type,
                        "source": obs.source,
                        "source_url": obs.source_url,
                        "data": obs.data,
                        "confidence": obs.confidence,
                    }
                    for obs in result.observations
                ],
                "raw_data": result.raw_data,
            }
            provider_run.error_code = result.error_code
            provider_run.error_message = result.error_message
            provider_run.completed_at = datetime.now(timezone.utc)

            investigation.status = (
                InvestigationStatus.COMPLETED
                if result.status.value == "SUCCESS"
                else InvestigationStatus.PARTIAL
            )
            investigation.completed_at = datetime.now(timezone.utc)

            db.commit()

            return {
                "investigation_id": investigation_id,
                "target_id": target_id,
                "provider": provider.name,
                "status": result.status.value,
                "provider_run_id": str(provider_run.id),
            }

        except Exception as exc:
            provider_run.status = ProviderRunStatus.FAILED
            provider_run.error_message = str(exc)
            provider_run.completed_at = datetime.now(timezone.utc)

            investigation.status = InvestigationStatus.FAILED
            investigation.error_message = str(exc)
            investigation.completed_at = datetime.now(timezone.utc)

            db.commit()
            raise