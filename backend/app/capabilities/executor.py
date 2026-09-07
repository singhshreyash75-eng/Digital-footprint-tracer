from dataclasses import dataclass, field
from typing import Any

from app.investigations.models import Subject
from app.providers.base import BaseProvider


@dataclass
class ExecutionTarget:
    """
    Provider-safe execution target.

    normalized_value:
        The exact identifier format expected by the provider.

    provider_user_id:
        Canonical ID belonging to the provider currently
        being executed.

    username:
        Provider login/username when available.

    identifiers:
        Provider-scoped identifiers.

    Provider IDs must never leak across providers.
    """

    normalized_value: str

    provider_user_id: str | None = None

    username: str | None = None

    identifiers: dict[str, Any] = field(
        default_factory=dict
    )


class CapabilityExecutor:
    """
    Execute provider capabilities using provider-aware
    identifier resolution.

    Important invariant:

        GitHub       -> username/login
        Steam        -> steamid64 / vanity
        Twitch       -> twitch_user_id
        StackExchange -> site + site_user_id

    A canonical ID belonging to one provider is never silently
    reused by another provider.
    """

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

        # =====================================================
        # NORMALIZE EXPLICIT PROVIDER INPUT
        # =====================================================

        effective_provider_user_id = (
            self._clean_value(
                provider_user_id
            )
        )

        effective_username = (
            self._clean_value(
                username
            )
        )

        # An explicitly supplied dictionary, including {},
        # must remain authoritative.
        #
        # Falling back to Subject.identifiers here could leak
        # identifiers belonging to another provider.
        if identifiers is not None:
            effective_identifiers = dict(
                identifiers
            )
        else:
            effective_identifiers = {}

            # Subject identifiers are safe only when executing
            # the provider from which the Subject originated.
            if (
                subject.provider
                .strip()
                .lower()
                ==
                provider.name
                .strip()
                .lower()
            ):
                effective_identifiers = dict(
                    subject.identifiers
                    or {}
                )

        effective_identifiers = {
            str(key): value
            for key, value
            in effective_identifiers.items()
            if (
                value is not None
                and str(value).strip()
            )
        }

        # Username may safely fall back to Subject.username only
        # for the Subject's anchor provider.
        if (
            effective_username is None
            and subject.provider
            .strip()
            .lower()
            ==
            provider.name
            .strip()
            .lower()
        ):
            effective_username = (
                self._clean_value(
                    subject.username
                )
            )

        # Canonical provider ID may safely fall back to Subject
        # only for the Subject's anchor provider.
        if (
            effective_provider_user_id is None
            and subject.provider
            .strip()
            .lower()
            ==
            provider.name
            .strip()
            .lower()
        ):
            effective_provider_user_id = (
                self._clean_value(
                    subject.provider_user_id
                )
            )

        # =====================================================
        # PROVIDER-AWARE IDENTIFIER RESOLUTION
        # =====================================================

        target_value = (
            self._resolve_execution_identifier(
                provider_name=(
                    provider.name
                ),
                provider_user_id=(
                    effective_provider_user_id
                ),
                username=(
                    effective_username
                ),
                identifiers=(
                    effective_identifiers
                ),
            )
        )

        target = ExecutionTarget(
            normalized_value=(
                target_value
            ),

            provider_user_id=(
                effective_provider_user_id
            ),

            username=(
                effective_username
            ),

            identifiers=(
                effective_identifiers
            ),
        )

        # =====================================================
        # PROVIDER EXECUTION
        # =====================================================

        result = await provider.execute(
            target,
            context={
                "subject_id": str(
                    subject.id
                ),

                "provider": (
                    provider.name
                ),

                "provider_user_id": (
                    effective_provider_user_id
                ),

                "username": (
                    effective_username
                ),

                "identifiers": (
                    effective_identifiers
                ),

                "requested_capabilities": (
                    capabilities
                ),
            },
        )

        # =====================================================
        # OBSERVATIONS
        # =====================================================

        observations: list[
            dict[str, Any]
        ] = []

        for observation in result.observations:
            if (
                observation.type
                not in requested_observation_types
            ):
                continue

            observations.append(
                {
                    "type": (
                        observation.type
                    ),

                    "source": (
                        observation.source
                    ),

                    "source_url": (
                        observation.source_url
                    ),

                    "data": (
                        observation.data
                    ),

                    "confidence": (
                        observation.confidence
                    ),
                }
            )

        # =====================================================
        # EXECUTED CAPABILITIES
        # =====================================================

        executed_capabilities = [
            capability
            for capability in capabilities
            if capability in definitions
        ]

        # =====================================================
        # ERRORS
        # =====================================================

        errors: list[
            dict[str, Any]
        ] = []

        if result.error_code:
            errors.append(
                {
                    "code": (
                        result.error_code
                    ),

                    "message": (
                        result.error_message
                    ),
                }
            )

        return {
            "provider_result_status": (
                result.status.value
            ),

            "requested_capabilities": (
                capabilities
            ),

            "executed_capabilities": (
                executed_capabilities
            ),

            "observations": (
                observations
            ),

            "errors": (
                errors
            ),
        }

    # =========================================================
    # PROVIDER-AWARE TARGET RESOLUTION
    # =========================================================

    @classmethod
    def _resolve_execution_identifier(
        cls,
        *,
        provider_name: str,
        provider_user_id: str | None,
        username: str | None,
        identifiers: dict[str, Any],
    ) -> str:
        """
        Resolve the execution target according to the provider's
        actual identifier contract.

        There is intentionally no generic global identifier
        priority list here.
        """

        provider = (
            provider_name
            .strip()
            .lower()
        )

        # -----------------------------------------------------
        # GitHub
        #
        # GitHubProvider calls:
        #
        #     /users/{target.normalized_value}
        #
        # Therefore normalized_value MUST be a GitHub login,
        # not the numeric github_id.
        # -----------------------------------------------------

        if provider == "github":
            value = cls._first_value(
                identifiers,
                (
                    "username",
                    "login",
                ),
            )

            value = (
                value
                or username
            )

            if value:
                return value

            raise ValueError(
                "Unable to resolve GitHub username/login."
            )

        # -----------------------------------------------------
        # Steam
        #
        # Prefer Steam's canonical SteamID64. If discovery has
        # supplied a vanity identifier, it may be used as a
        # provider-native fallback.
        # -----------------------------------------------------

        if provider == "steam":
            value = cls._first_value(
                identifiers,
                (
                    "steamid64",
                    "vanity_url",
                    "profile_url",
                ),
            )

            if value:
                return value

            if provider_user_id:
                return provider_user_id

            if username:
                return username

            raise ValueError(
                "Unable to resolve Steam identity."
            )

        # -----------------------------------------------------
        # Twitch
        #
        # Current TwitchProvider performs get_users_by_id().
        # Therefore it requires a real Twitch canonical user ID.
        # A GitHub/Steam/etc. username must not be substituted.
        # -----------------------------------------------------

        if provider == "twitch":
            value = cls._first_value(
                identifiers,
                (
                    "twitch_user_id",
                ),
            )

            value = (
                value
                or provider_user_id
            )

            if value:
                return value

            raise ValueError(
                "Unable to resolve Twitch user ID."
            )

        # -----------------------------------------------------
        # Stack Exchange
        #
        # StackExchangeProvider resolves site + site_user_id
        # from identifiers/context. normalized_value is not the
        # authoritative identity, but it still needs a valid
        # provider-safe value for ExecutionTarget.
        # -----------------------------------------------------

        if provider == "stackexchange":
            site = cls._clean_value(
                identifiers.get(
                    "site"
                )
            )

            site_user_id = (
                cls._clean_value(
                    identifiers.get(
                        "site_user_id"
                    )
                )
            )

            if (
                site
                and site_user_id
            ):
                return (
                    f"{site}:"
                    f"{site_user_id}"
                )

            # A linked StackExchange identity may already use
            # provider_user_id = "site:user_id".
            if (
                provider_user_id
                and ":"
                in provider_user_id
            ):
                return provider_user_id

            raise ValueError(
                "Unable to resolve Stack Exchange "
                "site and site user ID."
            )

        # -----------------------------------------------------
        # Future providers
        #
        # Conservative generic fallback: explicitly supplied
        # username/login first, then provider-specific canonical
        # ID. Never inspect foreign Subject identifiers here.
        # -----------------------------------------------------

        value = cls._first_value(
            identifiers,
            (
                "username",
                "login",
            ),
        )

        value = (
            value
            or username
            or provider_user_id
        )

        if value:
            return value

        raise ValueError(
            f"Unable to resolve execution identifier "
            f"for provider '{provider_name}'."
        )

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _first_value(
        identifiers: dict[str, Any],
        keys: tuple[str, ...],
    ) -> str | None:

        for key in keys:
            value = (
                identifiers.get(
                    key
                )
            )

            normalized = (
                CapabilityExecutor
                ._clean_value(
                    value
                )
            )

            if normalized:
                return normalized

        return None

    @staticmethod
    def _clean_value(
        value: Any,
    ) -> str | None:

        if value is None:
            return None

        normalized = str(
            value
        ).strip()

        if not normalized:
            return None

        return normalized