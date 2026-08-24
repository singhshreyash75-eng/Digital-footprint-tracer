import asyncio

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
    Runs all applicable providers for a Subject concurrently.

    Each SubjectIdentity is mapped to its corresponding provider.
    Each provider then executes only the capabilities it advertises.
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

        requested = self._get_requested_capabilities(
            provider,
            definitions,
            request,
        )

        execution_subject = self._build_execution_subject(
            subject,
            identity,
            provider,
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
            execution = await self.executor.execute(
                subject=execution_subject,
                provider=provider,
                capabilities=requested,
            )

        except Exception as exc:
            return ProviderInvestigationResult(
                provider=provider.name,
                supported=True,
                executed=False,
                requested_capabilities=requested,
                executed_capabilities=[],
                observations=[],
                errors=[
                    {
                        "code": "PROVIDER_EXECUTION_FAILED",
                        "message": str(exc),
                    }
                ],
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

    @staticmethod
    def _build_execution_subject(
        subject: Subject,
        identity: SubjectIdentity,
        provider: BaseProvider,
    ) -> Subject:

        # Preserve the existing Subject DB object while presenting
        # the selected provider identity to the current executor.
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

        return execution_subject