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

        providers = provider_registry.for_target_type(
            "USERNAME"
        )

        if not providers:
            investigation.status = InvestigationStatus.FAILED
            investigation.error_message = (
                "No providers support USERNAME targets."
            )
            investigation.completed_at = datetime.now(
                timezone.utc
            )
            db.commit()

            return {
                "investigation_id": investigation_id,
                "target_id": target_id,
                "status": "FAILED",
                "providers": [],
            }

        investigation.status = InvestigationStatus.RUNNING
        investigation.started_at = datetime.now(
            timezone.utc
        )

        db.commit()

        provider_results: list[dict[str, Any]] = []

        # ---------------------------------------------------------
        # Run every provider applicable to this target type.
        # ---------------------------------------------------------
        for provider in providers:
            provider_run = ProviderRun(
                investigation_id=investigation_uuid,
                provider_name=provider.name,
                status=ProviderRunStatus.PENDING,
            )

            db.add(provider_run)
            db.commit()
            db.refresh(provider_run)

            try:
                provider_run.status = ProviderRunStatus.RUNNING
                provider_run.started_at = datetime.now(
                    timezone.utc
                )

                db.commit()

                target = SimpleNamespace(
                    id=target_uuid,
                    investigation_id=investigation_uuid,
                    normalized_value=username,
                )

                result = asyncio.run(
                    provider.execute(target)
                )

                provider_run.status = ProviderRunStatus(
                    result.status.value
                )

                provider_run.result = {
                    "observations": [
                        {
                            "type": observation.type,
                            "source": observation.source,
                            "source_url": observation.source_url,
                            "data": observation.data,
                            "confidence": observation.confidence,
                        }
                        for observation in result.observations
                    ],
                    "raw_data": result.raw_data,
                }

                provider_run.error_code = result.error_code
                provider_run.error_message = result.error_message
                provider_run.completed_at = datetime.now(
                    timezone.utc
                )

                db.commit()

                provider_results.append(
                    {
                        "provider": provider.name,
                        "status": result.status.value,
                        "provider_run_id": str(
                            provider_run.id
                        ),
                    }
                )

            except Exception as exc:
                provider_run.status = ProviderRunStatus.FAILED
                provider_run.error_code = "PROVIDER_EXCEPTION"
                provider_run.error_message = str(exc)
                provider_run.completed_at = datetime.now(
                    timezone.utc
                )

                db.commit()

                provider_results.append(
                    {
                        "provider": provider.name,
                        "status": "FAILED",
                        "provider_run_id": str(
                            provider_run.id
                        ),
                    }
                )

        # ---------------------------------------------------------
        # Aggregate overall investigation status.
        # ---------------------------------------------------------
        statuses = [
            item["status"]
            for item in provider_results
        ]

        successful = any(
            status == ProviderRunStatus.SUCCESS.value
            for status in statuses
        )

        not_found_only = (
            bool(statuses)
            and all(
                status
                == ProviderRunStatus.NOT_FOUND.value
                for status in statuses
            )
        )

        failed = any(
            status
            in {
                ProviderRunStatus.FAILED.value,
                ProviderRunStatus.TIMEOUT.value,
                ProviderRunStatus.RATE_LIMITED.value,
            }
            for status in statuses
        )

        if successful and failed:
            investigation.status = InvestigationStatus.PARTIAL

        elif successful:
            investigation.status = InvestigationStatus.COMPLETED

        elif not_found_only:
            investigation.status = InvestigationStatus.PARTIAL

        elif failed:
            investigation.status = InvestigationStatus.FAILED

        else:
            investigation.status = InvestigationStatus.PARTIAL

        investigation.completed_at = datetime.now(
            timezone.utc
        )

        db.commit()

        return {
            "investigation_id": investigation_id,
            "target_id": target_id,
            "status": investigation.status.value,
            "providers": provider_results,
        }