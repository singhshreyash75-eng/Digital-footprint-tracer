from dataclasses import dataclass, field
from typing import Any

from app.investigations.models import Subject
from app.providers.base import BaseProvider


@dataclass
class ExecutionTarget:
    """
    Normalized execution target passed to a provider.

    normalized_value preserves the existing provider-specific
    execution behavior.

    provider_user_id is the canonical provider identity and is
    available to providers that require the provider's immutable ID.
    """

    normalized_value: str
    provider_user_id: str | None = None
    username: str | None = None
    identifiers: dict[str, Any] = field(
        default_factory=dict
    )


class CapabilityExecutor:

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
                definition.observation_types
            )

        target_value = (
            self._resolve_execution_identifier(
                subject
            )
        )

        target = ExecutionTarget(
            normalized_value=target_value,
            provider_user_id=(
                subject.provider_user_id
            ),
            username=subject.username,
            identifiers=dict(
                subject.identifiers or {}
            ),
        )

        result = await provider.execute(
            target,
            context={
                "subject_id": str(subject.id),

                "provider": provider.name,

                "provider_user_id": (
                    subject.provider_user_id
                ),

                "username": (
                    subject.username
                ),

                "identifiers": dict(
                    subject.identifiers or {}
                ),

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
                        "source_url": (
                            observation.source_url
                        ),
                        "data": observation.data,
                        "confidence": (
                            observation.confidence
                        ),
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
                return str(value)

        if subject.username:
            return subject.username

        return subject.provider_user_id