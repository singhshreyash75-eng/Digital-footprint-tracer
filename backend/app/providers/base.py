from abc import ABC, abstractmethod
from typing import Any

from app.investigations.models import TargetType
from app.providers.schemas import ProviderResult


class BaseProvider(ABC):
    name: str
    supported_target_types: set[TargetType]

    @abstractmethod
    async def execute(
        self,
        target: Any,
        context: dict[str, Any] | None = None,
    ) -> ProviderResult:
        """Execute the provider against a target."""
        raise NotImplementedError