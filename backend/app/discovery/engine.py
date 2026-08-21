from app.discovery.adapters.base import (
    DiscoveryAdapter,
)
from app.discovery.adapters.github import (
    GitHubDiscoveryAdapter,
)
from app.discovery.adapters.steam import (
    SteamDiscoveryAdapter,
)

from .scoring import DiscoveryScorer
from .schemas import DiscoveryCandidate


class DiscoveryEngine:
    """
    Provider-neutral discovery orchestrator.

    Providers implement DiscoveryAdapter.
    The engine combines, normalizes, deduplicates,
    and ranks their candidates.
    """

    def __init__(
        self,
        adapters: list[DiscoveryAdapter] | None = None,
    ) -> None:

        self.adapters = adapters or [
            GitHubDiscoveryAdapter(),
            SteamDiscoveryAdapter(),
        ]

        self.scorer = DiscoveryScorer()

    async def search(
        self,
        query: str,
    ) -> list[DiscoveryCandidate]:

        candidates: list[
            DiscoveryCandidate
        ] = []

        for adapter in self.adapters:
            try:
                provider_candidates = (
                    await adapter.search(query)
                )

            except Exception:
                # Discovery should be resilient:
                # one provider failing shouldn't destroy
                # results from every other provider.
                continue

            candidates.extend(
                provider_candidates
            )

        candidates = self._deduplicate(
            candidates
        )

        return self.scorer.rank(
            candidates,
            query,
        )

    @staticmethod
    def _deduplicate(
        candidates: list[DiscoveryCandidate],
    ) -> list[DiscoveryCandidate]:

        unique: dict[
            tuple[str, str],
            DiscoveryCandidate,
        ] = {}

        for candidate in candidates:

            key = (
                candidate.provider,
                candidate.provider_user_id,
            )

            existing = unique.get(key)

            if existing is None:
                unique[key] = candidate
                continue

            if (
                candidate.confidence
                > existing.confidence
            ):
                unique[key] = candidate

        return list(
            unique.values()
        )