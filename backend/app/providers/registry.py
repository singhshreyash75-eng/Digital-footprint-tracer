from app.investigations.models import TargetType
from app.providers.base import BaseProvider
from app.providers.username.github import GitHubProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}

    def register(self, provider: BaseProvider) -> None:
        if provider.name in self._providers:
            raise ValueError(
                f"Provider '{provider.name}' is already registered."
            )

        self._providers[provider.name] = provider

    def get(self, name: str) -> BaseProvider | None:
        return self._providers.get(name)

    def all(self) -> list[BaseProvider]:
        return list(self._providers.values())

    def for_target_type(
        self,
        target_type: TargetType,
    ) -> list[BaseProvider]:
        return [
            provider
            for provider in self._providers.values()
            if target_type in provider.supported_target_types
        ]


provider_registry = ProviderRegistry()
provider_registry.register(GitHubProvider())