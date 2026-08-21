from .schemas import DiscoveryCandidate


class DiscoveryScorer:
    """
    Cross-provider ranking layer.

    Provider-specific resolvers should do the detailed
    relevance calculation. This scorer performs only the
    final discovery-level adjustments.
    """

    def score(
        self,
        candidate: DiscoveryCandidate,
        query: str,
    ) -> float:

        query_normalized = (
            query.strip().lower()
        )

        username = (
            candidate.username or ""
        ).lower()

        display_name = (
            candidate.display_name or ""
        ).lower()

        score = candidate.confidence

        if username == query_normalized:
            score += 0.05

        elif (
            query_normalized
            and query_normalized in username
        ):
            score += 0.02

        if display_name == query_normalized:
            score += 0.05

        return min(
            max(score, 0.0),
            1.0,
        )

    def rank(
        self,
        candidates: list[DiscoveryCandidate],
        query: str,
    ) -> list[DiscoveryCandidate]:

        scored: list[
            DiscoveryCandidate
        ] = []

        for candidate in candidates:
            candidate.confidence = round(
                self.score(
                    candidate,
                    query,
                ),
                4,
            )

            scored.append(candidate)

        return sorted(
            scored,
            key=lambda item: item.confidence,
            reverse=True,
        )