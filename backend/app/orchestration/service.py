import asyncio
from typing import Any

from app.capabilities.executor import (
    CapabilityExecutor,
)
from app.capabilities.planner import (
    CapabilityPlanner,
)
from app.investigations.models import (
    Subject,
    SubjectIdentity,
)
from app.providers.base import BaseProvider
from app.providers.registry import (
    provider_registry,
)
from app.providers.schemas import ProviderStatus

from .schemas import (
    ProviderInvestigationResult,
    SubjectInvestigationRequest,
    SubjectInvestigationResponse,
)


class ProviderOrchestrator:
    """
    Execute all requested providers for a selected Subject.

    Resolution strategy:

    1. If the Subject already has a provider-specific linked
       identity, use that identity.

    2. Otherwise, derive safe reusable identity signals from
       the selected Subject and attempt that provider.

    Provider failures are isolated. A NOT_FOUND, TIMEOUT,
    RATE_LIMITED, FAILED, or other provider-level result does
    not terminate the overall investigation.
    """

    def __init__(self) -> None:
        self.planner = CapabilityPlanner()
        self.executor = CapabilityExecutor()

    async def investigate(
        self,
        subject: Subject,
        request: SubjectInvestigationRequest,
    ) -> SubjectInvestigationResponse:

        identities_by_provider = {
            identity.provider.strip().lower(): identity
            for identity in subject.identities
        }

        providers = self._resolve_providers(
            request
        )

        tasks = [
            self._run_provider(
                subject=subject,
                identity=identities_by_provider.get(
                    provider.name.strip().lower()
                ),
                provider=provider,
                request=request,
            )
            for provider in providers
        ]

        results = await asyncio.gather(
            *tasks
        )

        return SubjectInvestigationResponse(
            subject_id=subject.id,
            provider_results=list(results),
            total_providers=len(results),
            executed_providers=sum(
                1
                for result in results
                if result.executed
            ),
        )

    def _resolve_providers(
        self,
        request: SubjectInvestigationRequest,
    ) -> list[BaseProvider]:

        if not request.providers:
            return provider_registry.all()

        requested_names = {
            name.strip().lower()
            for name in request.providers
        }

        return [
            provider
            for provider in provider_registry.all()
            if provider.name.strip().lower()
            in requested_names
        ]

    async def _run_provider(
        self,
        subject: Subject,
        identity: SubjectIdentity | None,
        provider: BaseProvider,
        request: SubjectInvestigationRequest,
    ) -> ProviderInvestigationResult:

        definitions = (
            provider.get_capability_definitions()
        )

        requested = (
            self._get_requested_capabilities(
                provider=provider,
                definitions=definitions,
                request=request,
            )
        )

        plan = self.planner.build_plan(
            subject=subject,
            provider=provider,
            requested=requested,
        )

        if not plan["executable"]:
            return ProviderInvestigationResult(
                provider=provider.name,
                status=ProviderStatus.SKIPPED,
                supported=True,
                executed=False,
                requested_capabilities=requested,
                executed_capabilities=[],
                observations=[],
                errors=[
                    {
                        "code": "UNSUPPORTED_CAPABILITY",
                        "message": (
                            "One or more requested "
                            "capabilities are unsupported."
                        ),
                        "plan": plan,
                    }
                ],
            )

        execution_target = (
            self._build_execution_target(
                subject=subject,
                identity=identity,
                provider=provider,
            )
        )

        try:
            execution = await self.executor.execute(
                subject=subject,
                provider=provider,
                capabilities=requested,
                provider_user_id=(
                    execution_target[
                        "provider_user_id"
                    ]
                ),
                username=(
                    execution_target[
                        "username"
                    ]
                ),
                identifiers=(
                    execution_target[
                        "identifiers"
                    ]
                ),
            )

        except Exception as exc:
            return ProviderInvestigationResult(
                provider=provider.name,
                status=ProviderStatus.FAILED,
                supported=True,
                executed=False,
                requested_capabilities=requested,
                executed_capabilities=[],
                observations=[],
                errors=[
                    {
                        "code":
                            "PROVIDER_EXECUTION_FAILED",
                        "message": str(exc),
                    }
                ],
            )

        status_value = execution.get(
            "provider_result_status",
            ProviderStatus.FAILED.value,
        )

        try:
            status = ProviderStatus(
                status_value
            )
        except ValueError:
            status = ProviderStatus.FAILED

        # A provider was actually attempted even when its
        # terminal result is NOT_FOUND/RATE_LIMITED/etc.
        #
        # The response schema's executed flag therefore
        # represents execution attempt, not only SUCCESS.
        executed = True

        return ProviderInvestigationResult(
            provider=provider.name,
            status=status,
            supported=True,
            executed=executed,
            requested_capabilities=execution.get(
                "requested_capabilities",
                requested,
            ),
            executed_capabilities=execution.get(
                "executed_capabilities",
                [],
            ),
            observations=execution.get(
                "observations",
                [],
            ),
            errors=execution.get(
                "errors",
                [],
            ),
        )

    def _build_execution_target(
        self,
        subject: Subject,
        identity: SubjectIdentity | None,
        provider: BaseProvider,
    ) -> dict[str, Any]:
        """
        Build provider-safe execution signals.

        A linked provider identity always wins.

        When none exists, reusable name-like signals from the
        selected Subject are supplied. Provider-specific IDs
        belonging to another provider are deliberately NOT
        forwarded as the target provider's canonical ID.
        """

        if identity is not None:
            return {
                "provider_user_id":
                    identity.provider_user_id,
                "username":
                    identity.username,
                "identifiers":
                    dict(
                        identity.identifiers
                        or {}
                    ),
            }

        fallback_username = (
            subject.username
            or subject.display_name
        )

        fallback_identifiers = (
            self._build_fallback_identifiers(
                subject=subject,
                provider=provider,
                fallback_username=(
                    fallback_username
                ),
            )
        )

        return {
            # Do not pass a GitHub/Steam/etc. canonical ID
            # to a different provider.
            "provider_user_id": None,

            "username": fallback_username,

            "identifiers":
                fallback_identifiers,
        }

    @staticmethod
    def _build_fallback_identifiers(
        subject: Subject,
        provider: BaseProvider,
        fallback_username: str | None,
    ) -> dict[str, Any]:
        """
        Preserve only reusable identifiers for a provider
        that does not yet have a linked SubjectIdentity.

        Provider-specific IDs from the selected source
        identity are intentionally excluded.
        """

        identifiers: dict[str, Any] = {}

        if fallback_username:
            identifiers["username"] = (
                fallback_username
            )

            identifiers["login"] = (
                fallback_username
            )

        subject_identifiers = dict(
            subject.identifiers or {}
        )

        reusable_keys = (
            "email",
            "website",
            "domain",
        )

        for key in reusable_keys:
            value = subject_identifiers.get(
                key
            )

            if value:
                identifiers[key] = value

        return identifiers

    @staticmethod
    def _get_requested_capabilities(
        provider: BaseProvider,
        definitions,
        request: SubjectInvestigationRequest,
    ) -> list[str]:

        overrides = (
            request.capability_overrides
        )

        requested = overrides.get(
            provider.name,
            [],
        )

        if not requested:
            normalized_overrides = {
                key.strip().lower(): value
                for key, value
                in overrides.items()
            }

            requested = (
                normalized_overrides.get(
                    provider.name.strip().lower(),
                    [],
                )
            )

        if requested:
            return list(requested)

        return list(
            definitions.keys()
        )