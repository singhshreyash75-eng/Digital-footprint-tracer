from abc import ABC, abstractmethod

from app.discovery.schemas import DiscoveryCandidate


class DiscoveryAdapter(ABC):
    provider_name: str

    @abstractmethod
    async def search(
        self,
        query: str,
    ) -> list[DiscoveryCandidate]:
        """
        Discover identities for this provider.

        Each adapter is responsible for understanding its
        provider's native discovery/identifier mechanisms and
        returning normalized DiscoveryCandidate objects.
        """
        raise NotImplementedError