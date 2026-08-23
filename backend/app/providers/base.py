from abc import ABC, abstractmethod
from typing import Any

from app.investigations.models import TargetType
from app.providers.contracts.capability import (
    CapabilityDefinition,
)
from app.providers.schemas import ProviderResult


class BaseProvider(ABC):
    name: str
    supported_target_types: set[TargetType]

    capabilities: dict[str, bool] = {}

    capability_definitions: dict[
        str,
        CapabilityDefinition,
    ] = {}

    supported_identifiers: list[str] = []

    @abstractmethod
    async def execute(
        self,
        target: Any,
        context: dict[str, Any] | None = None,
    ) -> ProviderResult:
        raise NotImplementedError

    def get_capabilities(
        self,
    ) -> dict[str, bool]:
        return dict(
            self.capabilities
        )

    def get_capability_definitions(
        self,
    ) -> dict[str, CapabilityDefinition]:
        return dict(
            self.capability_definitions
        )

    def get_supported_identifiers(
        self,
    ) -> list[str]:
        return list(
            self.supported_identifiers
        )