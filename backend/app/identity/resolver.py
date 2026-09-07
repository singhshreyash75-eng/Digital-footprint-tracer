from __future__ import annotations

import asyncio
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

import httpx

from app.core.config import settings
from app.identity.schemas import IdentityCandidate


class GitHubIdentityResolver:
    """
    GitHub identity resolver.

    Supports:
    - exact GitHub username resolution
    - general human-name discovery
    - case/whitespace normalization
    - deep human-name candidate retrieval
    - enriched public-profile scoring
    - exact display-name preservation
    """

    # Deep retrieval for general human-name searches.
    HUMAN_NAME_RESULTS_PER_QUERY = 100

    # Smaller window for username-like searches.
    USERNAME_RESULTS_PER_QUERY = 30

    # Maximum unique profiles enriched per search.
    MAX_PROFILES_TO_ENRICH = 120

    # Normal final limit for username-like searches.
    MAX_CANDIDATES = 15

    # Human-name candidate policy.
    MAX_EXACT_NAME_MATCHES = 25
    MAX_OTHER_NAME_CANDIDATES = 10

    def __init__(self) -> None:
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": (
                f"Bearer {settings.github_token}"
            ),
            "X-GitHub-Api-Version": "2026-03-10",
        }

    async def search(
        self,
        query: str,
    ) -> list[IdentityCandidate]:
        canonical_query = self._canonicalize_query(
            query
        )

        if not canonical_query:
            return []

        async with httpx.AsyncClient(
            base_url=settings.github_api_base_url,
            headers=self.headers,
            timeout=20.0,
        ) as client:
            candidates: list[IdentityCandidate] = []

            # =================================================
            # 1. Direct username resolution
            # =================================================

            exact_profile = await self._get_profile(
                client,
                canonical_query,
            )

            if exact_profile is not None:
                candidates.append(
                    self._build_exact_candidate(
                        profile=exact_profile,
                    )
                )

            # =================================================
            # 2. Query-aware GitHub search
            # =================================================

            search_queries = self._build_search_queries(
                canonical_query
            )

            search_results = await asyncio.gather(
                *[
                    self._search_users(
                        client=client,
                        query=search_query,
                    )
                    for search_query in search_queries
                ],
                return_exceptions=True,
            )

            # =================================================
            # 3. Normalize result pools
            # =================================================

            result_pools: list[
                list[dict[str, Any]]
            ] = []

            for result in search_results:
                if isinstance(result, Exception):
                    result_pools.append([])
                    continue

                result_pools.append(result)

            # =================================================
            # 4. Merge + deduplicate search pools
            # =================================================

            users = self._round_robin_users(
                result_pools
            )

            users = users[
                : self.MAX_PROFILES_TO_ENRICH
            ]

            # =================================================
            # 5. Fetch full public profiles
            # =================================================

            profiles = await asyncio.gather(
                *[
                    self._get_profile(
                        client,
                        str(user["login"]),
                    )
                    for user in users
                    if user.get("login")
                ],
                return_exceptions=True,
            )

            for profile in profiles:
                if isinstance(profile, Exception):
                    continue

                if not profile:
                    continue

                candidates.append(
                    self._build_candidate(
                        query=canonical_query,
                        profile=profile,
                    )
                )

            # =================================================
            # 6. Deduplicate candidates by GitHub login
            # =================================================

            deduplicated: dict[
                str,
                IdentityCandidate,
            ] = {}

            for candidate in candidates:
                if not candidate.username:
                    continue

                key = (
                    candidate.username
                    .strip()
                    .lower()
                )

                existing = deduplicated.get(key)

                if (
                    existing is None
                    or candidate.score > existing.score
                ):
                    deduplicated[key] = candidate

            ranked = list(
                deduplicated.values()
            )

            # =================================================
            # 7. Deterministic ranking
            # =================================================

            ranked.sort(
                key=lambda candidate: (
                    -candidate.score,
                    -(candidate.followers or 0),
                    -(candidate.public_repos or 0),
                    (
                        candidate.username
                        or ""
                    ).lower(),
                )
            )

            # =================================================
            # 8. Final recall-aware selection
            # =================================================

            return self._select_final_candidates(
                query=canonical_query,
                ranked=ranked,
            )

    # =========================================================
    # FINAL CANDIDATE SELECTION
    # =========================================================

    def _select_final_candidates(
        self,
        *,
        query: str,
        ranked: list[IdentityCandidate],
    ) -> list[IdentityCandidate]:
        """
        Preserve high recall for human-name searches.

        For a human-name query, exact public display-name
        matches are protected from the normal Top-N cutoff.

        This does NOT assert that all exact-name matches are the
        same human. The operator still chooses the intended
        identity from the candidate list.
        """

        normalized_query = self._normalize_text(
            query
        )

        if not normalized_query:
            return []

        # -----------------------------------------------------
        # Username / single-token mode
        # -----------------------------------------------------

        if " " not in normalized_query:
            return ranked[
                : self.MAX_CANDIDATES
            ]

        # -----------------------------------------------------
        # Human-name mode
        # -----------------------------------------------------

        exact_name_matches: list[
            IdentityCandidate
        ] = []

        other_candidates: list[
            IdentityCandidate
        ] = []

        for candidate in ranked:
            normalized_display_name = (
                self._normalize_text(
                    candidate.display_name
                    or ""
                )
            )

            if (
                normalized_display_name
                == normalized_query
            ):
                exact_name_matches.append(
                    candidate
                )
            else:
                other_candidates.append(
                    candidate
                )

        selected = (
            exact_name_matches[
                : self.MAX_EXACT_NAME_MATCHES
            ]
            + other_candidates[
                : self.MAX_OTHER_NAME_CANDIDATES
            ]
        )

        # Defensive final deduplication.
        final_candidates: list[
            IdentityCandidate
        ] = []

        seen: set[str] = set()

        for candidate in selected:
            identity_key = str(
                candidate.username
                or candidate.provider_user_id
            ).strip().lower()

            if not identity_key:
                continue

            if identity_key in seen:
                continue

            seen.add(identity_key)

            final_candidates.append(
                candidate
            )

        return final_candidates

    # =========================================================
    # QUERY NORMALIZATION
    # =========================================================

    @staticmethod
    def _canonicalize_query(
        query: str,
    ) -> str:
        """
        Normalize equivalent user input.

        Examples:

            Parth Sharma
            parth sharma
            PARTH SHARMA
            PaRtH ShArMa
              Parth    Sharma

        all resolve to:

            parth sharma
        """

        query = unicodedata.normalize(
            "NFKD",
            query,
        )

        query = (
            query
            .encode(
                "ascii",
                "ignore",
            )
            .decode("ascii")
        )

        query = query.lower()

        query = re.sub(
            r"\s+",
            " ",
            query,
        )

        return query.strip()

    # =========================================================
    # SEARCH QUERY GENERATION
    # =========================================================

    def _build_search_queries(
        self,
        query: str,
    ) -> list[str]:
        """
        Human-name searches use deep real-name retrieval.

        Username-like searches preserve direct/login-style
        behavior.
        """

        clean = self._canonicalize_query(
            query
        )

        if not clean:
            return []

        if " " in clean:
            return [
                f"{clean} in:fullname",
                clean,
            ]

        return [
            clean,
        ]

    # =========================================================
    # GITHUB USER SEARCH
    # =========================================================

    async def _search_users(
        self,
        *,
        client: httpx.AsyncClient,
        query: str,
    ) -> list[dict[str, Any]]:
        """
        Retrieve a bounded GitHub candidate pool.

        Human-name queries use up to 100 GitHub search results
        because legitimate profiles may appear significantly
        below the first page of highly ranked usernames.
        """

        base_query = query.replace(
            " in:fullname",
            "",
        ).strip()

        is_human_name = (
            " " in base_query
        )

        per_page = (
            self.HUMAN_NAME_RESULTS_PER_QUERY
            if is_human_name
            else self.USERNAME_RESULTS_PER_QUERY
        )

        response = await client.get(
            "/search/users",
            params={
                "q": query,
                "per_page": per_page,
                "page": 1,
            },
        )

        response.raise_for_status()

        data = response.json()

        items = data.get(
            "items",
            [],
        )

        if not isinstance(items, list):
            return []

        return [
            item
            for item in items
            if (
                isinstance(item, dict)
                and item.get("login")
            )
        ]

    # =========================================================
    # BALANCED SEARCH-POOL MERGE
    # =========================================================

    @staticmethod
    def _round_robin_users(
        result_pools: list[
            list[dict[str, Any]]
        ],
    ) -> list[dict[str, Any]]:
        """
        Merge multiple GitHub result pools while removing
        duplicate logins.
        """

        merged: list[
            dict[str, Any]
        ] = []

        seen: set[str] = set()

        max_length = max(
            (
                len(pool)
                for pool in result_pools
            ),
            default=0,
        )

        for index in range(max_length):
            for pool in result_pools:
                if index >= len(pool):
                    continue

                user = pool[index]

                login = str(
                    user.get("login")
                    or ""
                ).strip()

                if not login:
                    continue

                key = login.lower()

                if key in seen:
                    continue

                seen.add(key)

                merged.append(user)

        return merged

    # =========================================================
    # FULL PUBLIC PROFILE LOOKUP
    # =========================================================

    async def _get_profile(
        self,
        client: httpx.AsyncClient,
        username: str,
    ) -> dict[str, Any] | None:
        username = username.strip()

        if not username:
            return None

        if len(username) > 39:
            return None

        response = await client.get(
            f"/users/{username}"
        )

        if response.status_code == 404:
            return None

        if response.status_code in (
            401,
            403,
        ):
            response.raise_for_status()

        response.raise_for_status()

        return response.json()

    # =========================================================
    # EXACT USERNAME CANDIDATE
    # =========================================================

    def _build_exact_candidate(
        self,
        profile: dict[str, Any],
    ) -> IdentityCandidate:
        username = str(
            profile.get("login")
            or ""
        )

        provider_user_id = str(
            profile.get("id")
            or username
        )

        return IdentityCandidate(
            provider="github",
            provider_user_id=(
                provider_user_id
            ),
            username=username,
            display_name=(
                profile.get("name")
            ),
            profile_url=(
                profile.get("html_url")
            ),
            avatar_url=(
                profile.get("avatar_url")
            ),
            score=1.0,
            confidence_percent=100,
            match_type="EXACT_USERNAME",
            reasons=[
                "Exact GitHub username match",
                "GitHub account resolved directly",
            ],
            public_repos=(
                profile.get("public_repos")
            ),
            followers=(
                profile.get("followers")
            ),
            following=(
                profile.get("following")
            ),
            bio=profile.get("bio"),
            location=profile.get(
                "location"
            ),
            company=profile.get(
                "company"
            ),
            blog=profile.get("blog"),
            identifiers={
                "username": username,
                "github_id": (
                    provider_user_id
                ),
            },
        )

    # =========================================================
    # ENRICHED SEARCH CANDIDATE
    # =========================================================

    def _build_candidate(
        self,
        query: str,
        profile: dict[str, Any],
    ) -> IdentityCandidate:
        username = str(
            profile.get("login")
            or ""
        )

        provider_user_id = str(
            profile.get("id")
            or username
        )

        display_name = profile.get(
            "name"
        )

        bio = profile.get("bio")
        location = profile.get("location")
        company = profile.get("company")
        blog = profile.get("blog")

        score, reasons, match_type = (
            self._calculate_score(
                query=query,
                username=username,
                display_name=display_name,
                bio=bio,
                location=location,
                company=company,
                blog=blog,
            )
        )

        return IdentityCandidate(
            provider="github",
            provider_user_id=(
                provider_user_id
            ),
            username=username,
            display_name=display_name,
            profile_url=(
                profile.get("html_url")
            ),
            avatar_url=(
                profile.get("avatar_url")
            ),
            score=round(
                score,
                4,
            ),
            confidence_percent=round(
                score * 100
            ),
            match_type=match_type,
            reasons=reasons,
            public_repos=(
                profile.get("public_repos")
            ),
            followers=(
                profile.get("followers")
            ),
            following=(
                profile.get("following")
            ),
            bio=bio,
            location=location,
            company=company,
            blog=blog,
            identifiers={
                "username": username,
                "github_id": (
                    provider_user_id
                ),
            },
        )

    # =========================================================
    # PROFILE RELEVANCE SCORING
    # =========================================================

    def _calculate_score(
        self,
        query: str,
        username: str,
        display_name: str | None,
        bio: str | None,
        location: str | None,
        company: str | None,
        blog: str | None,
    ) -> tuple[
        float,
        list[str],
        str,
    ]:
        query_norm = self._normalize_text(
            query
        )

        username_norm = self._normalize_text(
            username
        )

        display_norm = self._normalize_text(
            display_name or ""
        )

        bio_norm = self._normalize_text(
            bio or ""
        )

        company_norm = self._normalize_text(
            company or ""
        )

        location_norm = self._normalize_text(
            location or ""
        )

        # -----------------------------------------------------
        # Base similarity
        # -----------------------------------------------------

        display_similarity = self._similarity(
            query_norm,
            display_norm,
        )

        username_similarity = self._similarity(
            query_norm,
            username_norm,
        )

        query_tokens = set(
            query_norm.split()
        )

        display_tokens = set(
            display_norm.split()
        )

        token_overlap = 0.0

        if query_tokens:
            token_overlap = (
                len(
                    query_tokens
                    & display_tokens
                )
                / len(query_tokens)
            )

        # -----------------------------------------------------
        # Context signals
        # -----------------------------------------------------

        bio_match = self._token_context_match(
            query_tokens,
            bio_norm,
        )

        company_match = (
            self._token_context_match(
                query_tokens,
                company_norm,
            )
        )

        location_match = (
            self._token_context_match(
                query_tokens,
                location_norm,
            )
        )

        # -----------------------------------------------------
        # Weighted score
        # -----------------------------------------------------

        score = (
            0.50 * display_similarity
            + 0.20 * username_similarity
            + 0.15 * token_overlap
            + 0.05 * bio_match
            + 0.05 * company_match
            + 0.05 * location_match
        )

        reasons: list[str] = []

        # -----------------------------------------------------
        # Exact display-name bonus
        # -----------------------------------------------------

        if (
            query_norm
            and display_norm
            and query_norm == display_norm
        ):
            score += 0.20

            reasons.append(
                "Exact public display-name match"
            )

        # -----------------------------------------------------
        # Display-name signals
        # -----------------------------------------------------

        if display_similarity >= 0.90:
            reasons.append(
                "Very strong display-name similarity"
            )

        elif display_similarity >= 0.75:
            reasons.append(
                "Strong display-name similarity"
            )

        elif display_similarity >= 0.60:
            reasons.append(
                "Moderate display-name similarity"
            )

        # -----------------------------------------------------
        # Username signals
        # -----------------------------------------------------

        if username_similarity >= 0.90:
            reasons.append(
                "Very strong username similarity"
            )

        elif username_similarity >= 0.75:
            reasons.append(
                "Strong username similarity"
            )

        elif username_similarity >= 0.55:
            reasons.append(
                "Partial username similarity"
            )

        # -----------------------------------------------------
        # Name-token signals
        # -----------------------------------------------------

        if token_overlap == 1.0:
            reasons.append(
                "All name tokens matched"
            )

        elif token_overlap > 0:
            reasons.append(
                "Partial name-token match"
            )

        # -----------------------------------------------------
        # Context
        # -----------------------------------------------------

        if bio_match > 0:
            reasons.append(
                "Name token appears in public bio"
            )

        if company_match > 0:
            reasons.append(
                "Name token appears in company context"
            )

        if location_match > 0:
            reasons.append(
                "Name token appears in location context"
            )

        # -----------------------------------------------------
        # Clamp
        # -----------------------------------------------------

        score = min(
            max(
                score,
                0.0,
            ),
            1.0,
        )

        # -----------------------------------------------------
        # Match classification
        # -----------------------------------------------------

        if score >= 0.85:
            match_type = (
                "STRONG_PROFILE_MATCH"
            )

        elif score >= 0.65:
            match_type = (
                "MODERATE_PROFILE_MATCH"
            )

        elif score >= 0.40:
            match_type = (
                "PARTIAL_PROFILE_MATCH"
            )

        else:
            match_type = (
                "SEARCH_RELEVANCE"
            )

        if not reasons:
            reasons.append(
                "GitHub search relevance"
            )

        return (
            score,
            list(
                dict.fromkeys(reasons)
            ),
            match_type,
        )

    # =========================================================
    # SCORING HELPERS
    # =========================================================

    @staticmethod
    def _token_context_match(
        query_tokens: set[str],
        context: str,
    ) -> float:
        if (
            not query_tokens
            or not context
        ):
            return 0.0

        context_tokens = set(
            context.split()
        )

        matched = (
            query_tokens
            & context_tokens
        )

        return (
            len(matched)
            / len(query_tokens)
        )

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
    def _similarity(
        left: str,
        right: str,
    ) -> float:
        if not left or not right:
            return 0.0

        return SequenceMatcher(
            None,
            left,
            right,
        ).ratio()