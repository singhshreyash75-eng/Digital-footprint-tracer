from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

from app.discovery.schemas import DiscoveryCandidate
from app.providers.username.stackexchange.client import (
    StackExchangeAPIError,
    StackExchangeClient,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]

load_dotenv(PROJECT_ROOT / ".env")


DEFAULT_SITES = (
    "stackoverflow",
    "superuser",
    "serverfault",
    "askubuntu",
    "math",
    "mathoverflow",
    "security",
    "dba",
    "unix",
    "askdifferent",
    "android",
    "apple",
    "gaming",
    "webapps",
    "softwareengineering",
    "datascience",
    "ai",
    "devops",
)

SITE_USER_RE = re.compile(
    r"^(?P<site>[a-z0-9.-]+):(?P<user_id>\d+)$",
    re.IGNORECASE,
)


class StackExchangeDiscoveryAdapter:
    provider_name = "stackexchange"
    name = "stackexchange"

    def __init__(self) -> None:
        self.client = StackExchangeClient()

        configured_sites = os.getenv(
            "STACKEXCHANGE_DISCOVERY_SITES"
        )

        if configured_sites:
            self.sites = tuple(
                sorted(
                    {
                        site.strip().lower()
                        for site in configured_sites.split(",")
                        if site.strip()
                    }
                )
            )
        else:
            self.sites = DEFAULT_SITES

    async def search(
        self,
        query: str,
    ) -> list[DiscoveryCandidate]:
        value = query.strip()

        if not value:
            return []

        direct = await self._resolve_direct_identity(
            value
        )

        if direct is not None:
            return (
                [direct]
                if direct
                else []
            )

        # Human-name discovery remains broad, but site requests
        # are bounded by the client timeout and isolated.
        results = await asyncio.gather(
            *(
                self._search_site(
                    site=site,
                    query=value,
                )
                for site in self.sites
            ),
            return_exceptions=True,
        )

        candidates: list[DiscoveryCandidate] = []

        for site_results in results:
            if isinstance(site_results, Exception):
                continue

            candidates.extend(site_results)

        return self._deduplicate(candidates)

    async def _resolve_direct_identity(
        self,
        value: str,
    ) -> DiscoveryCandidate | list | None:
        match = SITE_USER_RE.fullmatch(value)

        if match:
            site = self._normalize_site(
                match.group("site")
            )

            if not site:
                return []

            return await self._candidate_from_site_user_id(
                site=site,
                user_id=int(
                    match.group("user_id")
                ),
                resolution_type="SITE_USER_ID",
            )

        if value.startswith(
            ("http://", "https://")
        ):
            parsed = urlparse(value)

            direct = self._parse_profile_url(parsed)

            if direct is None:
                return []

            site, user_id = direct

            return await self._candidate_from_site_user_id(
                site=site,
                user_id=user_id,
                resolution_type="PROFILE_URL",
            )

        return None

    def _parse_profile_url(
        self,
        parsed,
    ) -> tuple[str, int] | None:
        host = parsed.netloc.lower().split(":")[0]

        site = self._site_from_host(host)

        if not site:
            return None

        parts = [
            part
            for part in parsed.path.split("/")
            if part
        ]

        if len(parts) < 2:
            return None

        if parts[0].lower() not in {
            "users",
            "u",
        }:
            return None

        try:
            user_id = int(parts[1])
        except ValueError:
            return None

        return site, user_id

    @staticmethod
    def _site_from_host(
        host: str,
    ) -> str | None:
        host = host.removeprefix("www.")

        mapping = {
            "stackoverflow.com": "stackoverflow",
            "superuser.com": "superuser",
            "serverfault.com": "serverfault",
            "askubuntu.com": "askubuntu",
            "mathoverflow.net": "mathoverflow",
        }

        if host in mapping:
            return mapping[host]

        suffix = ".stackexchange.com"

        if host.endswith(suffix):
            return host[
                : -len(suffix)
            ]

        return None

    @staticmethod
    def _normalize_site(
        site: str,
    ) -> str | None:
        value = site.strip().lower()

        aliases = {
            "stackoverflow.com": "stackoverflow",
            "superuser.com": "superuser",
            "serverfault.com": "serverfault",
            "askubuntu.com": "askubuntu",
            "mathoverflow.net": "mathoverflow",
        }

        value = aliases.get(value, value)

        if not re.fullmatch(
            r"[a-z0-9.-]+",
            value,
        ):
            return None

        return value

    async def _candidate_from_site_user_id(
        self,
        *,
        site: str,
        user_id: int,
        resolution_type: str,
    ) -> DiscoveryCandidate | None:
        try:
            payload = await self.client.get_users(
                site=site,
                user_ids=[user_id],
            )
        except StackExchangeAPIError:
            return None

        items = payload.get("items") or []

        if not items:
            return None

        return self._candidate_from_item(
            site=site,
            item=items[0],
            confidence=1.0,
            match_type="EXACT_IDENTIFIER_MATCH",
            reasons=[
                (
                    "Stack Exchange profile resolved "
                    f"from {resolution_type.lower()}"
                )
            ],
        )

    async def _search_site(
        self,
        *,
        site: str,
        query: str,
    ) -> list[DiscoveryCandidate]:
        try:
            payload = await self.client.search_users(
                site=site,
                query=query,
                pagesize=12,
            )
        except StackExchangeAPIError:
            return []

        normalized_query = query.strip().lower()
        candidates: list[DiscoveryCandidate] = []

        for item in payload.get("items", []):
            display_name = str(
                item.get("display_name") or ""
            ).strip()

            normalized_display = display_name.lower()

            if normalized_display == normalized_query:
                confidence = 1.0
                match_type = "EXACT_DISPLAY_NAME"
                reasons = [
                    (
                        "Exact Stack Exchange "
                        "display name match"
                    )
                ]
            elif (
                normalized_query
                and normalized_query
                in normalized_display
            ):
                confidence = 0.85
                match_type = "DISPLAY_NAME_CONTAINS"
                reasons = [
                    (
                        "Stack Exchange display "
                        "name contains the query"
                    )
                ]
            else:
                confidence = 0.70
                match_type = "USER_SEARCH_MATCH"
                reasons = [
                    (
                        "Stack Exchange user search "
                        "returned this candidate"
                    )
                ]

            candidate = self._candidate_from_item(
                site=site,
                item=item,
                confidence=confidence,
                match_type=match_type,
                reasons=reasons,
            )

            if candidate is not None:
                candidates.append(candidate)

        return candidates

    @staticmethod
    def _candidate_from_item(
        *,
        site: str,
        item: dict,
        confidence: float,
        match_type: str,
        reasons: list[str],
    ) -> DiscoveryCandidate | None:
        user_id = item.get("user_id")

        if user_id is None:
            return None

        account_id = item.get("account_id")
        display_name = item.get("display_name")

        return DiscoveryCandidate(
            provider="stackexchange",
            provider_user_id=(
                f"{site}:{user_id}"
            ),
            username=display_name,
            display_name=display_name,
            profile_url=item.get("link"),
            avatar_url=item.get(
                "profile_image"
            ),
            confidence=confidence,
            match_type=match_type,
            reasons=reasons,
            identifiers={
                "site": site,
                "site_user_id": str(user_id),
                "account_id": (
                    str(account_id)
                    if account_id is not None
                    else ""
                ),
            },
            metadata={
                "discovery_source": (
                    "stackexchange_users"
                ),
                "site": site,
                "site_user_id": user_id,
                "account_id": account_id,
                "reputation": item.get(
                    "reputation"
                ),
                "question_count": item.get(
                    "question_count"
                ),
                "answer_count": item.get(
                    "answer_count"
                ),
                "badge_counts": item.get(
                    "badge_counts"
                ),
                "creation_date": item.get(
                    "creation_date"
                ),
                "last_access_date": item.get(
                    "last_access_date"
                ),
                "user_type": item.get(
                    "user_type"
                ),
                "match_type": match_type,
                "reasons": reasons,
            },
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

            if (
                existing is None
                or candidate.confidence
                > existing.confidence
            ):
                unique[key] = candidate

        return list(unique.values())
