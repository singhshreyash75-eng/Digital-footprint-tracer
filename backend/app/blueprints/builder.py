from typing import Any

from app.investigations.models import (
    ProviderRun,
    Subject,
)

from .sections import build_sections
from .schemas import (
    BlueprintCapabilities,
    BlueprintSubject,
    SubjectBlueprint,
)


class BlueprintBuilder:

    def build(
        self,
        subject: Subject,
        provider_runs: list[ProviderRun],
    ) -> SubjectBlueprint:

        observations: list[
            dict[str, Any]
        ] = []

        for provider_run in provider_runs:
            if provider_run.subject_id != subject.id:
                continue

            if provider_run.provider_name != subject.provider:
                continue

            if not provider_run.result:
                continue

            run_observations = (
                provider_run.result.get(
                    "observations",
                    [],
                )
            )

            if not isinstance(
                run_observations,
                list,
            ):
                continue

            observations.extend(
                run_observations
            )

        sections = build_sections(
            observations
        )

        return SubjectBlueprint(
            subject=BlueprintSubject(
                subject_id=subject.id,
                provider=subject.provider,
                provider_user_id=(
                    subject.provider_user_id
                ),
                username=subject.username,
                display_name=(
                    subject.display_name
                ),
                profile_url=subject.profile_url,
                confidence=subject.confidence,
                identifiers=dict(
                    subject.identifiers or {}
                ),
            ),
            capabilities=BlueprintCapabilities(
                available=dict(
                    subject.capabilities or {}
                )
            ),
            sections=sections,
            total_observations=len(
                observations
            ),
        )