from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from app.discovery.engine import DiscoveryEngine
from app.discovery.schemas import DiscoveryCandidate
from app.identity.correlation import (
    CorrelationResult,
    CrossProviderIdentityCorrelator,
)


@dataclass
class ProviderCorrelation:
    provider: str

    candidates: list[
        CorrelationResult
    ] = field(
        default_factory=list
    )

    auto_link_candidate: (
        CorrelationResult | None
    ) = None


@dataclass
class IdentityResolutionResult:
    anchor: DiscoveryCandidate
    signals: list[str]

    discovered_candidates: list[
        DiscoveryCandidate
    ]

    providers: dict[
        str,
        ProviderCorrelation,
    ]


class CrossProviderIdentityResolutionService:
    """
    Fast conservative cross-provider correlation.

    The previous implementation could run up to eight global
    DiscoveryEngine searches. Each global search fans out to
    every provider, so one identity selection could generate
    dozens of remote API calls.

    This version keeps the same evidence/scoring model while:
      - limiting global signals
      - prioritizing the human query and anchor username
      - removing redundant normalized variants
      - preserving discovery-query provenance
      - applying a hard timeout to each global signal
    """

    PROVIDERS = (
        "github",
        "steam",
        "twitch",
        "stackexchange",
    )

    MAX_SIGNALS = 3
    MAX_RESULTS_PER_PROVIDER = 8
    SIGNAL_TIMEOUT_SECONDS = 12.0

    def __init__(self) -> None:
        self.engine = DiscoveryEngine()
        self.correlator = (
            CrossProviderIdentityCorrelator()
        )

    async def resolve(
        self,
        *,
        anchor: DiscoveryCandidate,
        original_query: str,
    ) -> IdentityResolutionResult:
        signals = self.build_signals(
            anchor=anchor,
            original_query=original_query,
        )

        search_results = await asyncio.gather(
            *[
                self._search_signal(
                    signal
                )
                for signal in signals
            ],
            return_exceptions=False,
        )

        discovered: list[
            DiscoveryCandidate
        ] = []

        for result in search_results:
            discovered.extend(result)

        discovered = self._deduplicate(
            discovered
        )

        discovered = self._deduplicate(
            [
                anchor,
                *discovered,
            ]
        )

        correlated = (
            self.correlator.correlate(
                anchor=anchor,
                candidates=discovered,
            )
        )

        grouped: dict[
            str,
            ProviderCorrelation,
        ] = {
            provider: ProviderCorrelation(
                provider=provider
            )
            for provider in self.PROVIDERS
        }

        for result in correlated:
            provider = (
                result
                .candidate
                .provider
                .strip()
                .lower()
            )

            if provider not in grouped:
                grouped[
                    provider
                ] = ProviderCorrelation(
                    provider=provider
                )

            grouped[
                provider
            ].candidates.append(
                result
            )

        anchor_provider = (
            anchor
            .provider
            .strip()
            .lower()
        )

        if anchor_provider not in grouped:
            grouped[
                anchor_provider
            ] = ProviderCorrelation(
                provider=anchor_provider
            )

        for group in grouped.values():
            group.candidates.sort(
                key=lambda result: (
                    -result.score,
                    (
                        result
                        .candidate
                        .username
                        or ""
                    ).lower(),
                )
            )

            group.candidates = (
                group.candidates[
                    : self.MAX_RESULTS_PER_PROVIDER
                ]
            )

            auto_candidates = [
                result
                for result
                in group.candidates
                if result.auto_link
            ]

            if len(auto_candidates) == 1:
                group.auto_link_candidate = (
                    auto_candidates[0]
                )

        return IdentityResolutionResult(
            anchor=anchor,
            signals=signals,
            discovered_candidates=discovered,
            providers=grouped,
        )

    def build_signals(
        self,
        *,
        anchor: DiscoveryCandidate,
        original_query: str,
    ) -> list[str]:
        """
        Keep only high-value, non-redundant signals.

        Typical result:
          Shreyash Singh
          shreyashsingh
          singhshreyash75-eng

        We intentionally do not search every punctuation and
        whitespace variation globally. Individual adapters may
        still perform provider-specific normalization.
        """

        signals: list[str] = []

        original = (
            original_query.strip()
        )

        display_name = (
            anchor.display_name
            or ""
        ).strip()

        username = (
            anchor.username
            or ""
        ).strip()

        if original:
            signals.append(original)

            normalized_original = (
                self._normalize_words(
                    original
                )
            )

            tokens = (
                normalized_original.split()
            )

            if len(tokens) > 1:
                compact = "".join(tokens)

                if compact:
                    signals.append(compact)

        # Display name is useful only if it is materially
        # different from the original human query.
        if (
            display_name
            and self._comparison_key(
                display_name
            )
            != self._comparison_key(
                original
            )
        ):
            signals.append(display_name)

        if (
            username
            and self._comparison_key(
                username
            )
            not in {
                self._comparison_key(
                    original
                ),
                self._comparison_key(
                    display_name
                ),
            }
        ):
            signals.append(username)

        metadata = dict(
            anchor.metadata
            or {}
        )

        # A public linked profile/website path may expose a
        # reusable handle. Only use it if there is still room.
        if len(signals) < self.MAX_SIGNALS:
            for key in (
                "blog",
                "website",
                "website_url",
            ):
                value = metadata.get(key)

                if not value:
                    continue

                for extracted in (
                    self._signals_from_url(
                        str(value)
                    )
                ):
                    signals.append(extracted)

                    if (
                        len(
                            self._unique_signals(
                                signals
                            )
                        )
                        >= self.MAX_SIGNALS
                    ):
                        break

                if (
                    len(
                        self._unique_signals(
                            signals
                        )
                    )
                    >= self.MAX_SIGNALS
                ):
                    break

        return self._unique_signals(
            signals
        )[
            : self.MAX_SIGNALS
        ]

    async def _search_signal(
        self,
        signal: str,
    ) -> list[
        DiscoveryCandidate
    ]:
        try:
            candidates = (
                await asyncio.wait_for(
                    self.engine.search(
                        signal
                    ),
                    timeout=(
                        self.SIGNAL_TIMEOUT_SECONDS
                    ),
                )
            )
        except (
            asyncio.TimeoutError,
            Exception,
        ):
            return []

        enriched: list[
            DiscoveryCandidate
        ] = []

        for candidate in candidates:
            metadata = dict(
                candidate.metadata
                or {}
            )

            metadata[
                "correlation_discovery_query"
            ] = signal

            enriched.append(
                candidate.model_copy(
                    update={
                        "metadata": metadata,
                    }
                )
            )

        return enriched

    @staticmethod
    def _deduplicate(
        candidates: list[
            DiscoveryCandidate
        ],
    ) -> list[
        DiscoveryCandidate
    ]:
        unique: dict[
            tuple[str, str],
            DiscoveryCandidate,
        ] = {}

        for candidate in candidates:
            provider = (
                candidate
                .provider
                .strip()
                .lower()
            )

            provider_user_id = (
                candidate
                .provider_user_id
                .strip()
            )

            if (
                not provider
                or not provider_user_id
            ):
                continue

            key = (
                provider,
                provider_user_id,
            )

            existing = unique.get(key)

            if (
                existing is None
                or candidate.confidence
                > existing.confidence
            ):
                unique[key] = candidate

        return list(unique.values())

    @staticmethod
    def _normalize_words(
        value: str,
    ) -> str:
        value = (
            value
            .strip()
            .lower()
        )

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
    def _comparison_key(
        value: str,
    ) -> str:
        return re.sub(
            r"[^a-z0-9]",
            "",
            value.strip().lower(),
        )

    @staticmethod
    def _signals_from_url(
        value: str,
    ) -> list[str]:
        value = value.strip()

        if not value.startswith(
            ("http://", "https://")
        ):
            return []

        try:
            parsed = urlparse(value)
        except ValueError:
            return []

        parts = [
            part
            for part in parsed.path.split("/")
            if part
        ]

        if not parts:
            return []

        final_part = parts[-1].strip()

        return (
            [final_part]
            if final_part
            else []
        )

    @staticmethod
    def _unique_signals(
        signals: list[str],
    ) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()

        for signal in signals:
            clean = signal.strip()

            if not clean:
                continue

            key = clean.lower()

            if key in seen:
                continue

            seen.add(key)
            unique.append(clean)

        return unique
