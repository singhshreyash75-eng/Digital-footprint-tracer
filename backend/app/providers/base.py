from abc import ABC, abstractmethod
from typing import Any

from app.investigations.models import TargetType
from app.providers.schemas import ProviderResult


class BaseProvider(ABC):
    name: str
    supported_target_types: set[TargetType]

    # Backward-compatible coarse capability metadata.
    capabilities: dict[str, bool] = {}

    # Fine-grained executable capabilities.
    capability_definitions: dict[
        str,
        dict[str, Any],
    ] = {}

    supported_identifiers: list[str] = []

    @abstractmethod
    async def execute(
        self,
        target: Any,
        context: dict[str, Any] | None = None,
    ) -> ProviderResult:
        """Execute the provider against a target."""
        raise NotImplementedError

    def get_capabilities(
        self,
    ) -> dict[str, bool]:
        return dict(self.capabilities)

    def get_capability_definitions(
        self,
    ) -> dict[str, dict[str, Any]]:
        return dict(
            self.capability_definitions
        )

    def get_supported_identifiers(
        self,
    ) -> list[str]:
        return list(
            self.supported_identifiers
        )