from dataclasses import dataclass, field
from typing import Any

from app.investigations.models import Subject
from app.providers.base import BaseProvider
from app.providers.schemas import ProviderStatus


@dataclass
class ExecutionTarget:
    """
    Normalized execution target passed to a provider.

    normalized_value:
        Existing provider-compatible execution identifier.

    provider_user_id:
        Canonical provider identity ID.

    username:
        Provider username/login when available.

    identifiers:
        Provider-specific identifiers.
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
        *,
        provider_user_id: str | None = None,
        username: str | None = None,
        identifiers: dict[str, Any] | None = None,
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

        effective_provider_user_id = (
            provider_user_id
            or subject.provider_user_id
        )

        effective_username = (
            username
            if username is not None
            else subject.username
        )

        effective_identifiers = dict(
            identifiers
            if identifiers is not None
            else (
                subject.identifiers
                or {}
            )
        )

        target_value = (
            self._resolve_execution_identifier(
                subject=subject,
                provider_user_id=(
                    effective_provider_user_id
                ),
                username=effective_username,
                identifiers=effective_identifiers,
            )
        )

        target = ExecutionTarget(
            normalized_value=target_value,
            provider_user_id=(
                effective_provider_user_id
            ),
            username=effective_username,
            identifiers=effective_identifiers,
        )

        result = await provider.execute(
            target,
            context={
                "subject_id": str(subject.id),

                "provider": provider.name,

                "provider_user_id": (
                    effective_provider_user_id
                ),

                "username": (
                    effective_username
                ),

                "identifiers": (
                    effective_identifiers
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
        provider_user_id: str | None,
        username: str | None,
        identifiers: dict[str, Any],
    ) -> str:
        """
        Preserve the existing provider-compatible identifier
        resolution while allowing provider-specific identity
        data to be supplied explicitly.

        Provider-specific identifiers remain preferred where
        they already exist, preserving GitHub/Steam behavior.
        """

        preferred_keys = (
            "steamid64",
            "github_id",
            "twitch_user_id",
            "channel_id",
            "username",
            "login",
            "profile_url",
            "vanity_url",
        )

        for key in preferred_keys:
            value = identifiers.get(key)

            if value:
                return str(value)

        if username:
            return str(username)

        if provider_user_id:
            return str(provider_user_id)

        if subject.username:
            return str(subject.username)

        if subject.provider_user_id:
            return str(
                subject.provider_user_id
            )

        raise ValueError(
            "Unable to resolve execution identifier."
        )