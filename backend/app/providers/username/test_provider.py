from typing import Any

from app.investigations.models import TargetType
from app.providers.base import BaseProvider
from app.providers.schemas import (
    ProviderObservation,
    ProviderResult,
    ProviderStatus,
)


class TestUsernameProvider(BaseProvider):
    name = "test_username"
    supported_target_types = {TargetType.USERNAME}

    async def execute(
        self,
        target: Any,
        context: dict[str, Any] | None = None,
    ) -> ProviderResult:
        return ProviderResult(
            provider_name=self.name,
            status=ProviderStatus.SUCCESS,
            observations=[
                ProviderObservation(
                    type="TEST_PROFILE",
                    source="test",
                    source_url="https://example.com",
                    data={"username": target.normalized_value},
                    confidence="HIGH",
                )
            ],
        )