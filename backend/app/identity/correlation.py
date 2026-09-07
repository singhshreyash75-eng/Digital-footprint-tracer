from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from app.discovery.schemas import DiscoveryCandidate


@dataclass
class CorrelationResult:
    candidate: DiscoveryCandidate
    score: float
    reasons: list[str]
    auto_link: bool


class CrossProviderIdentityCorrelator:
    """
    Correlate provider-native discovery candidates against
    the operator-selected anchor identity.

    Important:

    This class NEVER converts one provider's canonical ID into
    another provider's ID.

    Correlation is based only on reusable public signals such
    as:

    - display name
    - username/login similarity
    - public URLs
    - public location
    - public company
    - public bio

    Provider-native IDs remain provider-scoped.
    """

    AUTO_LINK_THRESHOLD = 0.92

    MINIMUM_ACCEPTABLE_SCORE = 0.60

    def correlate(
        self,
        *,
        anchor: DiscoveryCandidate,
        candidates: list[DiscoveryCandidate],
    ) -> list[CorrelationResult]:

        results: list[CorrelationResult] = []

        anchor_provider = (
            anchor.provider
            .strip()
            .lower()
        )

        for candidate in candidates:
            candidate_provider = (
                candidate.provider
                .strip()
                .lower()
            )

            # The selected anchor is already known.
            if (
                candidate_provider
                == anchor_provider
                and candidate.provider_user_id
                == anchor.provider_user_id
            ):
                continue

            score, reasons = self._score(
                anchor=anchor,
                candidate=candidate,
            )

            if (
                score
                < self.MINIMUM_ACCEPTABLE_SCORE
            ):
                continue

            results.append(
                CorrelationResult(
                    candidate=candidate,
                    score=score,
                    reasons=reasons,
                    auto_link=(
                        score
                        >= self.AUTO_LINK_THRESHOLD
                        and self._has_strong_evidence(
                            anchor=anchor,
                            candidate=candidate,
                        )
                    ),
                )
            )

        results.sort(
            key=lambda result: (
                -result.score,
                result.candidate.provider.lower(),
                (
                    result.candidate.username
                    or ""
                ).lower(),
            )
        )

        return results

    def best_by_provider(
        self,
        *,
        anchor: DiscoveryCandidate,
        candidates: list[DiscoveryCandidate],
    ) -> dict[str, CorrelationResult]:
        """
        Return the strongest acceptable candidate for each
        provider other than the selected anchor provider.
        """

        correlated = self.correlate(
            anchor=anchor,
            candidates=candidates,
        )

        best: dict[
            str,
            CorrelationResult,
        ] = {}

        for result in correlated:
            provider = (
                result.candidate.provider
                .strip()
                .lower()
            )

            if provider not in best:
                best[provider] = result

        return best

    def _score(
        self,
        *,
        anchor: DiscoveryCandidate,
        candidate: DiscoveryCandidate,
    ) -> tuple[float, list[str]]:

        reasons: list[str] = []

        anchor_name = self._normalize(
            anchor.display_name
            or ""
        )

        candidate_name = self._normalize(
            candidate.display_name
            or ""
        )

        anchor_username = self._normalize_handle(
            anchor.username
            or ""
        )

        candidate_username = self._normalize_handle(
            candidate.username
            or ""
        )

        name_similarity = self._similarity(
            anchor_name,
            candidate_name,
        )

        username_similarity = self._similarity(
            anchor_username,
            candidate_username,
        )

        score = 0.0

        # -----------------------------------------------------
        # Public display name
        # -----------------------------------------------------

        if (
            anchor_name
            and candidate_name
        ):
            score += (
                0.45
                * name_similarity
            )

            if (
                anchor_name
                == candidate_name
            ):
                reasons.append(
                    "Exact public display-name match"
                )

            elif name_similarity >= 0.85:
                reasons.append(
                    "Strong public display-name similarity"
                )

        # -----------------------------------------------------
        # Username/login similarity
        # -----------------------------------------------------

        if (
            anchor_username
            and candidate_username
        ):
            score += (
                0.25
                * username_similarity
            )

            if (
                anchor_username
                == candidate_username
            ):
                reasons.append(
                    "Exact reusable username match"
                )

            elif username_similarity >= 0.80:
                reasons.append(
                    "Strong username similarity"
                )

        # -----------------------------------------------------
        # Cross-linked public URLs
        # -----------------------------------------------------

        shared_url = self._shared_url_signal(
            anchor,
            candidate,
        )

        if shared_url:
            score += 0.25

            reasons.append(
                "Shared public profile or website signal"
            )

        # -----------------------------------------------------
        # Public contextual metadata
        # -----------------------------------------------------

        context_score, context_reasons = (
            self._context_score(
                anchor=anchor,
                candidate=candidate,
            )
        )

        score += (
            0.05
            * context_score
        )

        reasons.extend(
            context_reasons
        )

        score = min(
            max(
                score,
                0.0,
            ),
            1.0,
        )

        return (
            round(
                score,
                4,
            ),
            list(
                dict.fromkeys(
                    reasons
                )
            ),
        )

    def _has_strong_evidence(
        self,
        *,
        anchor: DiscoveryCandidate,
        candidate: DiscoveryCandidate,
    ) -> bool:
        """
        Exact display name alone is NOT sufficient for
        automatic cross-provider linking.

        Auto-link requires at least one stronger independent
        signal.
        """

        anchor_username = (
            self._normalize_handle(
                anchor.username
                or ""
            )
        )

        candidate_username = (
            self._normalize_handle(
                candidate.username
                or ""
            )
        )

        if (
            anchor_username
            and candidate_username
            and anchor_username
            == candidate_username
        ):
            return True

        if self._shared_url_signal(
            anchor,
            candidate,
        ):
            return True

        return False

    def _context_score(
        self,
        *,
        anchor: DiscoveryCandidate,
        candidate: DiscoveryCandidate,
    ) -> tuple[
        float,
        list[str],
    ]:

        reasons: list[str] = []

        comparisons = (
            (
                "location",
                "Matching public location",
            ),
            (
                "company",
                "Matching public company",
            ),
            (
                "bio",
                "Similar public biography signal",
            ),
        )

        scores: list[float] = []

        for key, reason in comparisons:
            left = self._metadata_value(
                anchor,
                key,
            )

            right = self._metadata_value(
                candidate,
                key,
            )

            if (
                not left
                or not right
            ):
                continue

            similarity = self._similarity(
                self._normalize(left),
                self._normalize(right),
            )

            scores.append(
                similarity
            )

            if similarity >= 0.85:
                reasons.append(
                    reason
                )

        if not scores:
            return 0.0, reasons

        return (
            max(scores),
            reasons,
        )

    def _shared_url_signal(
        self,
        anchor: DiscoveryCandidate,
        candidate: DiscoveryCandidate,
    ) -> bool:

        anchor_urls = self._collect_urls(
            anchor
        )

        candidate_urls = self._collect_urls(
            candidate
        )

        if not anchor_urls:
            return False

        if not candidate_urls:
            return False

        return bool(
            anchor_urls
            & candidate_urls
        )

    def _collect_urls(
        self,
        candidate: DiscoveryCandidate,
    ) -> set[str]:

        values: list[Any] = [
            candidate.profile_url,
            candidate.metadata.get(
                "blog"
            ),
            candidate.metadata.get(
                "website"
            ),
            candidate.metadata.get(
                "website_url"
            ),
        ]

        identifiers = (
            candidate.identifiers
            or {}
        )

        values.extend(
            [
                identifiers.get(
                    "profile_url"
                ),
                identifiers.get(
                    "website"
                ),
            ]
        )

        urls: set[str] = set()

        for value in values:
            if not value:
                continue

            normalized = (
                str(value)
                .strip()
                .lower()
                .rstrip("/")
            )

            if normalized:
                urls.add(
                    normalized
                )

        return urls

    @staticmethod
    def _metadata_value(
        candidate: DiscoveryCandidate,
        key: str,
    ) -> str:

        value = (
            candidate.metadata.get(
                key
            )
        )

        if value is None:
            return ""

        return str(
            value
        ).strip()

    @staticmethod
    def _normalize(
        value: str,
    ) -> str:

        value = unicodedata.normalize(
            "NFKD",
            value,
        )

        value = (
            value
            .encode(
                "ascii",
                "ignore",
            )
            .decode(
                "ascii"
            )
        )

        value = value.lower()

        value = re.sub(
            r"[^a-z0-9\s]",
            " ",
            value,
        )

        value = re.sub(
            r"\s+",
            " ",
            value,
        )

        return value.strip()

    @staticmethod
    def _normalize_handle(
        value: str,
    ) -> str:

        value = unicodedata.normalize(
            "NFKD",
            value,
        )

        value = (
            value
            .encode(
                "ascii",
                "ignore",
            )
            .decode(
                "ascii"
            )
        )

        value = value.lower()

        value = re.sub(
            r"[^a-z0-9]",
            "",
            value,
        )

        return value

    @staticmethod
    def _similarity(
        left: str,
        right: str,
    ) -> float:

        if (
            not left
            or not right
        ):
            return 0.0

        return SequenceMatcher(
            None,
            left,
            right,
        ).ratio()