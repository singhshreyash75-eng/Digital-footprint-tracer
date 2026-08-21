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
    MAX_CANDIDATES = 10

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
        query = query.strip()

        if not query:
            return []

        async with httpx.AsyncClient(
            base_url=settings.github_api_base_url,
            headers=self.headers,
            timeout=15.0,
        ) as client:

            candidates: list[
                IdentityCandidate
            ] = []

            # ---------------------------------------------------------
            # STEP 1: Direct username resolution.
            # ---------------------------------------------------------
            exact_profile = await self._get_profile(
                client,
                query,
            )

            if exact_profile is not None:
                candidates.append(
                    self._build_exact_candidate(
                        profile=exact_profile,
                    )
                )

            # ---------------------------------------------------------
            # STEP 2: GitHub user search.
            # ---------------------------------------------------------
            search_response = await client.get(
                "/search/users",
                params={
                    "q": query,
                    "per_page": self.MAX_CANDIDATES,
                },
            )

            search_response.raise_for_status()

            search_data = search_response.json()

            users = search_data.get(
                "items",
                [],
            )

            # ---------------------------------------------------------
            # STEP 3: Enrich users with full public profiles.
            # ---------------------------------------------------------
            profiles = await asyncio.gather(
                *[
                    self._get_profile(
                        client,
                        user["login"],
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
                        query=query,
                        profile=profile,
                    )
                )

            # ---------------------------------------------------------
            # STEP 4: Deduplicate by GitHub login.
            # ---------------------------------------------------------
            deduplicated: dict[
                str,
                IdentityCandidate,
            ] = {}

            for candidate in candidates:
                if not candidate.username:
                    continue

                key = candidate.username.lower()

                existing = deduplicated.get(key)

                if existing is None:
                    deduplicated[key] = candidate
                    continue

                if candidate.score > existing.score:
                    deduplicated[key] = candidate

            ranked = list(
                deduplicated.values()
            )

            # ---------------------------------------------------------
            # STEP 5: Rank by provider relevance.
            # ---------------------------------------------------------
            ranked.sort(
                key=lambda candidate: candidate.score,
                reverse=True,
            )

            return ranked

    async def _get_profile(
        self,
        client: httpx.AsyncClient,
        username: str,
    ) -> dict[str, Any] | None:

        if len(username) > 39:
            return None

        response = await client.get(
            f"/users/{username}"
        )

        if response.status_code == 404:
            return None

        if response.status_code in (401, 403):
            response.raise_for_status()

        response.raise_for_status()

        return response.json()

    def _build_exact_candidate(
        self,
        profile: dict[str, Any],
    ) -> IdentityCandidate:

        username = profile.get(
            "login",
            "",
        )

        provider_user_id = str(
            profile.get("id")
            or username
        )

        return IdentityCandidate(
            provider="github",
            provider_user_id=provider_user_id,

            username=username,
            display_name=profile.get("name"),
            profile_url=profile.get("html_url"),
            avatar_url=profile.get("avatar_url"),

            score=1.0,
            confidence_percent=100,
            match_type="EXACT_USERNAME",

            reasons=[
                "Exact GitHub username match",
                "GitHub account resolved directly",
            ],

            public_repos=profile.get(
                "public_repos"
            ),
            followers=profile.get(
                "followers"
            ),
            following=profile.get(
                "following"
            ),

            bio=profile.get("bio"),
            location=profile.get("location"),
            company=profile.get("company"),
            blog=profile.get("blog"),

            identifiers={
                "username": username,
                "github_id": provider_user_id,
            },
        )

    def _build_candidate(
        self,
        query: str,
        profile: dict[str, Any],
    ) -> IdentityCandidate:

        username = profile.get(
            "login",
            "",
        )

        provider_user_id = str(
            profile.get("id")
            or username
        )

        display_name = profile.get(
            "name"
        )

        bio = profile.get(
            "bio"
        )

        location = profile.get(
            "location"
        )

        company = profile.get(
            "company"
        )

        blog = profile.get(
            "blog"
        )

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
            provider_user_id=provider_user_id,

            username=username,
            display_name=display_name,
            profile_url=profile.get("html_url"),
            avatar_url=profile.get("avatar_url"),

            score=round(
                score,
                4,
            ),

            confidence_percent=round(
                score * 100
            ),

            match_type=match_type,
            reasons=reasons,

            public_repos=profile.get(
                "public_repos"
            ),
            followers=profile.get(
                "followers"
            ),
            following=profile.get(
                "following"
            ),

            bio=bio,
            location=location,
            company=company,
            blog=blog,

            identifiers={
                "username": username,
                "github_id": provider_user_id,
            },
        )

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

        # -------------------------------------------------------------
        # Base similarity signals
        # -------------------------------------------------------------
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

        # -------------------------------------------------------------
        # Context signals
        # -------------------------------------------------------------
        bio_match = self._token_context_match(
            query_tokens,
            bio_norm,
        )

        company_match = self._token_context_match(
            query_tokens,
            company_norm,
        )

        location_match = self._token_context_match(
            query_tokens,
            location_norm,
        )

        # -------------------------------------------------------------
        # Weighted score
        # -------------------------------------------------------------
        score = (
            0.50 * display_similarity
            + 0.20 * username_similarity
            + 0.15 * token_overlap
            + 0.05 * bio_match
            + 0.05 * company_match
            + 0.05 * location_match
        )

        reasons: list[str] = []

        # -------------------------------------------------------------
        # Exact display-name bonus
        # -------------------------------------------------------------
        if (
            query_norm
            and display_norm
            and query_norm == display_norm
        ):
            score += 0.20

            reasons.append(
                "Exact public display-name match"
            )

        # -------------------------------------------------------------
        # Name quality signals
        # -------------------------------------------------------------
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

        # -------------------------------------------------------------
        # Username signals
        # -------------------------------------------------------------
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

        # -------------------------------------------------------------
        # Token overlap
        # -------------------------------------------------------------
        if token_overlap == 1.0:
            reasons.append(
                "All name tokens matched"
            )

        elif token_overlap > 0:
            reasons.append(
                "Partial name-token match"
            )

        # -------------------------------------------------------------
        # Context
        # -------------------------------------------------------------
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

        # -------------------------------------------------------------
        # Clamp score
        # -------------------------------------------------------------
        score = min(
            max(score, 0.0),
            1.0,
        )

        # -------------------------------------------------------------
        # Match classification
        # -------------------------------------------------------------
        if score >= 0.85:
            match_type = "STRONG_PROFILE_MATCH"

        elif score >= 0.65:
            match_type = "MODERATE_PROFILE_MATCH"

        elif score >= 0.40:
            match_type = "PARTIAL_PROFILE_MATCH"

        else:
            match_type = "SEARCH_RELEVANCE"

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

    @staticmethod
    def _token_context_match(
        query_tokens: set[str],
        context: str,
    ) -> float:

        if not query_tokens or not context:
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