from abc import ABC, abstractmethod
from typing import Any

from app.investigations.models import TargetType
from app.providers.schemas import ProviderResult


class BaseProvider(ABC):
    name: str
    supported_target_types: set[TargetType]

    # Every provider exposes the same metadata shape,
    # but the values are provider-specific.
    capabilities: dict[str, bool] = {}

    supported_identifiers: list[str] = []

    @abstractmethod
    async def execute(
        self,
        target: Any,
        context: dict[str, Any] | None = None,
    ) -> ProviderResult:
        """Execute the provider against a target."""
        raise NotImplementedError

    def get_capabilities(self) -> dict[str, bool]:
        return dict(self.capabilities)

    def get_supported_identifiers(self) -> list[str]:
        return list(self.supported_identifiers)