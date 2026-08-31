import asyncio

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
    Runs all applicable providers for a Subject concurrently.

    Each provider receives its own selected SubjectIdentity
    data and never mutates the shared Subject object.

    Provider failures are isolated. One provider returning
    NOT_FOUND, RATE_LIMITED, TIMEOUT, or FAILED does not
    terminate the overall investigation.
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
            self._run_provider_if_applicable(
                subject=subject,
                identity=(
                    identities_by_provider.get(
                        provider.name.strip().lower()
                    )
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

    async def _run_provider_if_applicable(
        self,
        subject: Subject,
        identity: SubjectIdentity | None,
        provider: BaseProvider,
        request: SubjectInvestigationRequest,
    ) -> ProviderInvestigationResult:

        if identity is None:
            return ProviderInvestigationResult(
                provider=provider.name,
                status=ProviderStatus.SKIPPED,
                supported=False,
                executed=False,
                requested_capabilities=[],
                executed_capabilities=[],
                observations=[],
                errors=[
                    {
                        "code": "IDENTITY_NOT_LINKED",
                        "message": (
                            "No identity for this provider "
                            "is linked to the selected Subject."
                        ),
                    }
                ],
            )

        return await self._run_provider(
            subject=subject,
            identity=identity,
            provider=provider,
            request=request,
        )

    async def _run_provider(
        self,
        subject: Subject,
        identity: SubjectIdentity,
        provider: BaseProvider,
        request: SubjectInvestigationRequest,
    ) -> ProviderInvestigationResult:

        definitions = (
            provider.get_capability_definitions()
        )

        requested = (
            self._get_requested_capabilities(
                provider,
                definitions,
                request,
            )
        )

        # -----------------------------------------------------
        # IMPORTANT:
        #
        # Do NOT mutate the shared SQLAlchemy Subject object.
        #
        # The selected provider identity is passed explicitly
        # into the planner/executor.
        # -----------------------------------------------------

        plan_subject = subject

        plan = self.planner.build_plan(
            subject=plan_subject,
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

        try:
            execution = (
                await self.executor.execute(
                    subject=plan_subject,
                    provider=provider,
                    capabilities=requested,
                    provider_user_id=(
                        identity.provider_user_id
                    ),
                    username=identity.username,
                    identifiers=dict(
                        identity.identifiers or {}
                    ),
                )
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
                        "code": (
                            "PROVIDER_EXECUTION_FAILED"
                        ),
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

        # "executed" now means that the provider actually
        # completed its requested capability execution successfully.
        executed = (
            status == ProviderStatus.SUCCESS
        )

        return ProviderInvestigationResult(
            provider=provider.name,
            status=status,
            supported=True,
            executed=executed,
            requested_capabilities=(
                execution[
                    "requested_capabilities"
                ]
            ),
            executed_capabilities=(
                execution[
                    "executed_capabilities"
                ]
            ),
            observations=execution[
                "observations"
            ],
            errors=execution[
                "errors"
            ],
        )

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

            requested = normalized_overrides.get(
                provider.name.strip().lower(),
                [],
            )

        if requested:
            return list(requested)

        return list(
            definitions.keys()
        )