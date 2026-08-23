from app.capabilities.executor import CapabilityExecutor
from app.capabilities.planner import CapabilityPlanner
from app.investigations.models import (
    Subject,
    SubjectIdentity,
)
from app.providers.base import BaseProvider
from app.providers.registry import provider_registry

from .schemas import (
    ProviderInvestigationResult,
    SubjectInvestigationRequest,
    SubjectInvestigationResponse,
)


class ProviderOrchestrator:
    """
    Executes all applicable providers for a Subject.

    Provider identity matching is case-insensitive so that
    persisted identities and provider registry names cannot
    diverge due to casing.
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

        results: list[
            ProviderInvestigationResult
        ] = []

        for provider in providers:
            provider_key = (
                provider.name.strip().lower()
            )

            identity = identities_by_provider.get(
                provider_key
            )

            if identity is None:
                results.append(
                    ProviderInvestigationResult(
                        provider=provider.name,
                        supported=False,
                        executed=False,
                        requested_capabilities=[],
                        executed_capabilities=[],
                        observations=[],
                        errors=[
                            {
                                "code": (
                                    "IDENTITY_NOT_LINKED"
                                ),
                                "message": (
                                    "No identity for this "
                                    "provider is linked to "
                                    "the selected Subject."
                                ),
                            }
                        ],
                    )
                )
                continue

            result = await self._run_provider(
                subject=subject,
                identity=identity,
                provider=provider,
                request=request,
            )

            results.append(result)

        return SubjectInvestigationResponse(
            subject_id=subject.id,
            provider_results=results,
            total_providers=len(providers),
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

        providers: list[BaseProvider] = []

        requested_names = {
            name.strip().lower()
            for name in request.providers
        }

        for provider in provider_registry.all():
            if (
                provider.name.strip().lower()
                in requested_names
            ):
                providers.append(provider)

        return providers

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
            request.capability_overrides.get(
                provider.name,
                [],
            )
        )

        # Also support case-insensitive provider names
        # inside capability_overrides.
        if not requested:
            normalized_overrides = {
                key.strip().lower(): value
                for key, value
                in request.capability_overrides.items()
            }

            requested = normalized_overrides.get(
                provider.name.strip().lower(),
                [],
            )

        # No override = execute every capability
        # the provider advertises.
        if not requested:
            requested = list(
                definitions.keys()
            )

        # ---------------------------------------------------------
        # Build a provider-specific execution view.
        #
        # We preserve the existing Subject object while using the
        # linked SubjectIdentity as the source of truth for this
        # provider execution.
        # ---------------------------------------------------------
        execution_subject = subject

        execution_subject.provider = (
            identity.provider
        )

        execution_subject.provider_user_id = (
            identity.provider_user_id
        )

        execution_subject.username = (
            identity.username
        )

        execution_subject.display_name = (
            identity.display_name
        )

        execution_subject.profile_url = (
            identity.profile_url
        )

        execution_subject.confidence = (
            identity.confidence
        )

        execution_subject.identifiers = dict(
            identity.identifiers or {}
        )

        execution_subject.capabilities = (
            provider.get_capabilities()
        )

        plan = self.planner.build_plan(
            subject=execution_subject,
            provider=provider,
            requested=requested,
        )

        if not plan["executable"]:
            return ProviderInvestigationResult(
                provider=provider.name,
                supported=True,
                executed=False,
                requested_capabilities=requested,
                executed_capabilities=[],
                observations=[],
                errors=[
                    {
                        "code": (
                            "UNSUPPORTED_CAPABILITY"
                        ),
                        "message": (
                            "One or more requested "
                            "capabilities are unsupported."
                        ),
                        "plan": plan,
                    }
                ],
            )

        execution = await self.executor.execute(
            subject=execution_subject,
            provider=provider,
            capabilities=requested,
        )

        return ProviderInvestigationResult(
            provider=provider.name,
            supported=True,
            executed=True,
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