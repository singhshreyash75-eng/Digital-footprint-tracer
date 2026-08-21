from dataclasses import dataclass
from typing import Any

from app.investigations.models import Subject
from app.providers.base import BaseProvider


@dataclass
class ExecutionTarget:
    normalized_value: str


class CapabilityExecutor:
    """
    Executes provider collection and filters the resulting
    observations according to the requested capability set.
    """

    async def execute(
        self,
        subject: Subject,
        provider: BaseProvider,
        capabilities: list[str],
    ) -> dict[str, Any]:

        definitions = (
            provider.get_capability_definitions()
        )

        requested_observation_types: set[str] = set()

        for capability in capabilities:
            definition = definitions.get(
                capability
            )

            if definition is None:
                continue

            requested_observation_types.update(
                definition.get(
                    "observation_types",
                    [],
                )
            )

        target_value = self._resolve_execution_identifier(
            subject
        )

        target = ExecutionTarget(
            normalized_value=target_value
        )

        result = await provider.execute(
            target,
            context={
                "subject_id": str(subject.id),
                "requested_capabilities": capabilities,
            },
        )

        observations = []

        for observation in result.observations:
            if (
                observation.type
                in requested_observation_types
            ):
                observations.append(
                    {
                        "type": observation.type,
                        "source": observation.source,
                        "source_url": observation.source_url,
                        "data": observation.data,
                        "confidence": observation.confidence,
                    }
                )

        executed_capabilities = [
            capability
            for capability in capabilities
            if capability in definitions
        ]

        errors = []

        if result.error_code:
            errors.append(
                {
                    "code": result.error_code,
                    "message": result.error_message,
                }
            )

        return {
            "provider_result_status": (
                result.status.value
            ),
            "requested_capabilities": capabilities,
            "executed_capabilities": (
                executed_capabilities
            ),
            "observations": observations,
            "errors": errors,
        }

    @staticmethod
    def _resolve_execution_identifier(
        subject: Subject,
    ) -> str:

        identifiers = (
            subject.identifiers or {}
        )

        preferred_keys = (
            "steamid64",
            "username",
            "profile_url",
            "vanity_url",
        )

        for key in preferred_keys:
            value = identifiers.get(key)

            if value:
                return value

        if subject.username:
            return subject.username

        return subject.provider_user_id