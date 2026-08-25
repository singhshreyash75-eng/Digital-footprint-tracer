import asyncio

from app.discovery.adapters.base import (
    DiscoveryAdapter,
)
from app.discovery.adapters.github import (
    GitHubDiscoveryAdapter,
)
from app.discovery.adapters.steam import (
    SteamDiscoveryAdapter,
)
from app.discovery.adapters.twitch import (
    TwitchDiscoveryAdapter,
)

from .scoring import DiscoveryScorer
from .schemas import DiscoveryCandidate


class DiscoveryEngine:
    """
    Provider-neutral discovery orchestrator.

    Providers implement DiscoveryAdapter.
    The engine combines, normalizes, deduplicates,
    and ranks candidates.

    Discovery is resilient and concurrent:
    one provider failing should not prevent
    other providers from returning candidates.
    """

    def __init__(
        self,
        adapters: list[DiscoveryAdapter] | None = None,
    ) -> None:

        self.adapters = adapters or [
            GitHubDiscoveryAdapter(),
            SteamDiscoveryAdapter(),
            TwitchDiscoveryAdapter(),
        ]

        self.scorer = DiscoveryScorer()

    async def search(
        self,
        query: str,
    ) -> list[DiscoveryCandidate]:

        if not query.strip():
            return []

        # ---------------------------------------------------------
        # Run provider discovery concurrently.
        # ---------------------------------------------------------
        tasks = [
            self._search_adapter(
                adapter,
                query,
            )
            for adapter in self.adapters
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=False,
        )

        candidates: list[
            DiscoveryCandidate
        ] = []

        for provider_candidates in results:
            candidates.extend(
                provider_candidates
            )

        # ---------------------------------------------------------
        # Remove duplicate identities.
        # ---------------------------------------------------------
        candidates = self._deduplicate(
            candidates
        )

        # ---------------------------------------------------------
        # Score and rank the combined candidate set.
        # ---------------------------------------------------------
        return self.scorer.rank(
            candidates,
            query,
        )

    @staticmethod
    async def _search_adapter(
        adapter: DiscoveryAdapter,
        query: str,
    ) -> list[DiscoveryCandidate]:
        """
        Execute one provider's discovery adapter
        without allowing its failure to break discovery
        for all other providers.
        """

        try:
            return await adapter.search(
                query
            )

        except Exception:
            # Provider discovery is intentionally isolated.
            # A failure here should not affect other providers.
            return []

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
                candidate.provider.strip().lower(),
                candidate.provider_user_id,
            )

            existing = unique.get(
                key
            )

            if existing is None:
                unique[key] = candidate
                continue

            # Keep the stronger candidate when the same
            # provider identity appears more than once.
            if (
                candidate.confidence
                > existing.confidence
            ):
                unique[key] = candidate

        return list(
            unique.values()
        )