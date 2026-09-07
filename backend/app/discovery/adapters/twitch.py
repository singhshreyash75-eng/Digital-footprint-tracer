from __future__ import annotations

import asyncio
import re
import unicodedata
from typing import Any
from urllib.parse import urlparse

from app.discovery.schemas import DiscoveryCandidate
from app.providers.username.twitch.client import (
    TwitchAPIError,
    TwitchClient,
)


class TwitchDiscoveryAdapter:
    """
    Twitch public identity discovery.

    Accepts:
      - bare broadcaster login
      - human-readable name queries
      - twitch.tv/<login> profile URLs

    Exact provider-native inputs use one direct search. General
    human-name queries use a small conservative variant set.
    """

    name = "twitch"
    provider_name = "twitch"

    MAX_RESULTS_PER_QUERY = 15
    MAX_CANDIDATES = 15
    MAX_SEARCH_VARIANTS = 3

    TWITCH_HOSTS = {
        "twitch.tv",
        "www.twitch.tv",
        "m.twitch.tv",
    }

    RESERVED_PATHS = {
        "",
        "directory",
        "downloads",
        "jobs",
        "p",
        "products",
        "settings",
        "subscriptions",
        "videos",
        "wallet",
    }

    def __init__(self) -> None:
        self.client = TwitchClient()

    async def search(
        self,
        query: str,
    ) -> list[DiscoveryCandidate]:
        raw_query = query.strip()

        if not raw_query:
            return []

        direct_login = self._extract_profile_login(
            raw_query
        )

        # Exact Twitch profile URL: search only the extracted
        # broadcaster login. This fixes URL input and avoids
        # unnecessary query expansion.
        if direct_login is not None:
            return await self._search_exact_login(
                direct_login,
                source="PROFILE_URL",
            )

        normalized_query = self._normalize_text(
            raw_query
        )

        if not normalized_query:
            return []

        # A simple single-token value is most likely a native
        # Twitch login. Try it directly first.
        if (
            " " not in normalized_query
            and re.fullmatch(
                r"[a-z0-9_]{1,25}",
                normalized_query,
            )
        ):
            exact = await self._search_exact_login(
                normalized_query,
                source="LOGIN",
            )

            if exact:
                return exact

        search_queries = self._build_search_queries(
            normalized_query
        )

        results = await asyncio.gather(
            *[
                self._search_query(
                    search_query
                )
                for search_query in search_queries
            ],
            return_exceptions=True,
        )

        candidates: list[
            DiscoveryCandidate
        ] = []

        for result in results:
            if isinstance(
                result,
                Exception,
            ):
                continue

            candidates.extend(result)

        candidates = self._deduplicate(
            candidates
        )

        candidates.sort(
            key=lambda candidate: (
                -candidate.confidence,
                (
                    candidate.username
                    or ""
                ).lower(),
            )
        )

        return candidates[
            : self.MAX_CANDIDATES
        ]

    async def _search_exact_login(
        self,
        login: str,
        *,
        source: str,
    ) -> list[DiscoveryCandidate]:
        normalized_login = (
            login.strip().lower()
        )

        if not normalized_login:
            return []

        try:
            payload = (
                await self.client.search_channels(
                    query=normalized_login,
                    first=10,
                    live_only=False,
                )
            )
        except TwitchAPIError:
            return []
        except Exception:
            return []

        exact_candidates: list[
            DiscoveryCandidate
        ] = []

        fallback_candidates: list[
            DiscoveryCandidate
        ] = []

        for item in payload.get(
            "data",
            [],
        ):
            candidate = self._build_candidate(
                original_query=normalized_login,
                item=item,
            )

            if candidate is None:
                continue

            if (
                self._normalize_handle(
                    candidate.username
                    or ""
                )
                == self._normalize_handle(
                    normalized_login
                )
            ):
                metadata = dict(
                    candidate.metadata
                    or {}
                )

                metadata[
                    "resolution_type"
                ] = source

                exact_candidates.append(
                    candidate.model_copy(
                        update={
                            "confidence": 1.0,
                            "match_type": (
                                "EXACT_LOGIN"
                            ),
                            "reasons": [
                                (
                                    "Exact Twitch "
                                    "broadcaster login match"
                                )
                            ],
                            "metadata": metadata,
                        }
                    )
                )
            else:
                fallback_candidates.append(
                    candidate
                )

        if exact_candidates:
            return self._deduplicate(
                exact_candidates
            )

        return self._deduplicate(
            fallback_candidates
        )[
            :5
        ]

    async def _search_query(
        self,
        query: str,
    ) -> list[DiscoveryCandidate]:
        try:
            payload = (
                await self.client.search_channels(
                    query=query,
                    first=(
                        self.MAX_RESULTS_PER_QUERY
                    ),
                    live_only=False,
                )
            )
        except TwitchAPIError:
            return []
        except Exception:
            return []

        candidates: list[
            DiscoveryCandidate
        ] = []

        for item in payload.get(
            "data",
            [],
        ):
            candidate = self._build_candidate(
                original_query=query,
                item=item,
            )

            if candidate is not None:
                candidates.append(candidate)

        return candidates

    def _build_candidate(
        self,
        *,
        original_query: str,
        item: dict[str, Any],
    ) -> DiscoveryCandidate | None:
        user_id = item.get("id")
        login = item.get(
            "broadcaster_login"
        )
        display_name = item.get(
            "display_name"
        )

        if not user_id or not login:
            return None

        normalized_query = self._normalize_text(
            original_query
        )

        normalized_login = self._normalize_handle(
            str(login)
        )

        normalized_display = self._normalize_text(
            str(display_name or "")
        )

        query_handle = self._normalize_handle(
            normalized_query
        )

        reasons: list[str] = []

        if (
            normalized_login
            and normalized_login
            == query_handle
        ):
            confidence = 1.0
            match_type = "EXACT_LOGIN"
            reasons.append(
                "Exact Twitch broadcaster login match"
            )

        elif (
            normalized_display
            and normalized_display
            == normalized_query
        ):
            confidence = 0.92
            match_type = "EXACT_DISPLAY_NAME"
            reasons.append(
                "Exact Twitch public display-name match"
            )

        elif (
            query_handle
            and normalized_login
            and (
                query_handle
                in normalized_login
                or normalized_login
                in query_handle
            )
        ):
            confidence = 0.82
            match_type = "LOGIN_SIMILARITY"
            reasons.append(
                "Twitch login strongly resembles the query"
            )

        elif (
            self._token_overlap(
                normalized_query,
                normalized_display,
            )
            >= 0.75
        ):
            confidence = 0.78
            match_type = "DISPLAY_NAME_SIMILARITY"
            reasons.append(
                "Twitch display name strongly resembles the query"
            )

        else:
            confidence = 0.65
            match_type = "CHANNEL_SEARCH_MATCH"
            reasons.append(
                "Twitch channel search returned this candidate"
            )

        profile_url = (
            f"https://www.twitch.tv/{login}"
        )

        return DiscoveryCandidate(
            provider="twitch",
            provider_user_id=str(user_id),
            username=str(login),
            display_name=(
                str(display_name)
                if display_name
                else str(login)
            ),
            profile_url=profile_url,
            confidence=confidence,
            match_type=match_type,
            reasons=reasons,
            identifiers={
                "twitch_user_id": str(
                    user_id
                ),
                "login": str(login),
                "profile_url": profile_url,
            },
            metadata={
                "discovery_source": (
                    "twitch_channel_search"
                ),
                "search_query": (
                    original_query
                ),
                "broadcaster_language": (
                    item.get(
                        "broadcaster_language"
                    )
                ),
                "game_id": item.get(
                    "game_id"
                ),
                "game_name": item.get(
                    "game_name"
                ),
                "is_live": item.get(
                    "is_live"
                ),
                "title": item.get(
                    "title"
                ),
                "started_at": item.get(
                    "started_at"
                ),
                "thumbnail_url": item.get(
                    "thumbnail_url"
                ),
                "match_type": match_type,
                "reasons": reasons,
            },
        )

    def _build_search_queries(
        self,
        query: str,
    ) -> list[str]:
        normalized = self._normalize_text(
            query
        )

        if not normalized:
            return []

        tokens = [
            token
            for token in normalized.split()
            if token
        ]

        variants: list[str] = [
            normalized,
        ]

        compact = "".join(tokens)

        if (
            compact
            and compact != normalized
        ):
            variants.append(compact)

        # One strongest name token is enough for recall here.
        # The previous adapter searched every token, multiplying
        # latency during cross-provider correlation.
        if len(tokens) > 1:
            longest = max(
                tokens,
                key=len,
            )

            if len(longest) >= 3:
                variants.append(longest)

        unique: list[str] = []
        seen: set[str] = set()

        for variant in variants:
            value = (
                variant.strip().lower()
            )

            if (
                not value
                or value in seen
            ):
                continue

            seen.add(value)
            unique.append(value)

        return unique[
            : self.MAX_SEARCH_VARIANTS
        ]

    @classmethod
    def _extract_profile_login(
        cls,
        value: str,
    ) -> str | None:
        raw = value.strip()

        if not raw.startswith(
            ("http://", "https://")
        ):
            return None

        try:
            parsed = urlparse(raw)
        except ValueError:
            return None

        host = (
            parsed.netloc
            .lower()
            .split(":")[0]
        )

        if host not in cls.TWITCH_HOSTS:
            return None

        parts = [
            part
            for part in parsed.path.split("/")
            if part
        ]

        if not parts:
            return None

        login = (
            parts[0]
            .strip()
            .lower()
        )

        if (
            login in cls.RESERVED_PATHS
            or not re.fullmatch(
                r"[a-z0-9_]{1,25}",
                login,
            )
        ):
            return None

        return login

    @staticmethod
    def _deduplicate(
        candidates: list[
            DiscoveryCandidate
        ],
    ) -> list[DiscoveryCandidate]:
        unique: dict[
            str,
            DiscoveryCandidate,
        ] = {}

        for candidate in candidates:
            key = str(
                candidate.provider_user_id
            ).strip()

            if not key:
                continue

            existing = unique.get(key)

            if (
                existing is None
                or candidate.confidence
                > existing.confidence
            ):
                unique[key] = candidate

        return list(unique.values())

    @staticmethod
    def _normalize_text(
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
            .decode("ascii")
        )

        value = value.lower()

        value = re.sub(
            r"[^a-z0-9\s_]",
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
            .decode("ascii")
        )

        value = value.lower()

        value = re.sub(
            r"[^a-z0-9_]",
            "",
            value,
        )

        return value

    @staticmethod
    def _token_overlap(
        left: str,
        right: str,
    ) -> float:
        left_tokens = set(
            left.split()
        )

        right_tokens = set(
            right.split()
        )

        if (
            not left_tokens
            or not right_tokens
        ):
            return 0.0

        return (
            len(
                left_tokens
                & right_tokens
            )
            / len(left_tokens)
        )
