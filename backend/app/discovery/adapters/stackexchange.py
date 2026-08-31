import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from app.discovery.schemas import (
    DiscoveryCandidate,
)
from app.providers.username.stackexchange.client import (
    StackExchangeAPIError,
    StackExchangeClient,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]

load_dotenv(
    PROJECT_ROOT / ".env"
)


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


class StackExchangeDiscoveryAdapter:

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
                        for site in (
                            configured_sites.split(",")
                        )
                        if site.strip()
                    }
                )
            )
        else:
            self.sites = DEFAULT_SITES

    async def _search_site(
        self,
        *,
        site: str,
        query: str,
    ) -> list[DiscoveryCandidate]:

        try:
            payload = (
                await self.client.search_users(
                    site=site,
                    query=query,
                    pagesize=20,
                )
            )

        except StackExchangeAPIError:
            return []

        candidates: list[
            DiscoveryCandidate
        ] = []

        normalized_query = (
            query.strip().lower()
        )

        for item in payload.get(
            "items",
            [],
        ):

            user_id = item.get(
                "user_id"
            )

            display_name = item.get(
                "display_name"
            )

            account_id = item.get(
                "account_id"
            )

            profile_url = item.get(
                "link"
            )

            if user_id is None:
                continue

            normalized_display = (
                str(
                    display_name or ""
                )
                .strip()
                .lower()
            )

            if (
                normalized_display
                == normalized_query
            ):
                confidence = 1.0
                match_type = (
                    "EXACT_DISPLAY_NAME"
                )
                reasons = [
                    (
                        "Exact Stack Exchange "
                        "display name match"
                    )
                ]

            elif normalized_query in (
                normalized_display
            ):
                confidence = 0.85
                match_type = (
                    "DISPLAY_NAME_CONTAINS"
                )
                reasons = [
                    (
                        "Stack Exchange display "
                        "name contains the query"
                    )
                ]

            else:
                confidence = 0.70
                match_type = (
                    "USER_SEARCH_MATCH"
                )
                reasons = [
                    (
                        "Stack Exchange user search "
                        "returned this candidate"
                    )
                ]

            provider_user_id = (
                f"{site}:{user_id}"
            )

            candidates.append(
                DiscoveryCandidate(
                    provider="stackexchange",
                    provider_user_id=(
                        provider_user_id
                    ),
                    username=display_name,
                    display_name=display_name,
                    profile_url=profile_url,
                    confidence=confidence,
                    identifiers={
                        "site": site,
                        "site_user_id": str(
                            user_id
                        ),
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
                        "site_user_id": (
                            user_id
                        ),
                        "account_id": (
                            account_id
                        ),
                        "reputation": (
                            item.get(
                                "reputation"
                            )
                        ),
                        "question_count": (
                            item.get(
                                "question_count"
                            )
                        ),
                        "answer_count": (
                            item.get(
                                "answer_count"
                            )
                        ),
                        "badge_counts": (
                            item.get(
                                "badge_counts"
                            )
                        ),
                        "creation_date": (
                            item.get(
                                "creation_date"
                            )
                        ),
                        "last_access_date": (
                            item.get(
                                "last_access_date"
                            )
                        ),
                        "user_type": (
                            item.get(
                                "user_type"
                            )
                        ),
                        "match_type": match_type,
                        "reasons": reasons,
                    },
                )
            )

        return candidates

    async def search(
        self,
        query: str,
    ) -> list[DiscoveryCandidate]:

        normalized_query = (
            query.strip()
        )

        if not normalized_query:
            return []

        results = await asyncio.gather(
            *(
                self._search_site(
                    site=site,
                    query=normalized_query,
                )
                for site in self.sites
            )
        )

        candidates: list[
            DiscoveryCandidate
        ] = []

        for site_results in results:
            candidates.extend(
                site_results
            )

        return self._deduplicate(
            candidates
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
                candidate.provider_user_id,
                str(
                    candidate.identifiers.get(
                        "site",
                        "",
                    )
                ),
            )

            existing = unique.get(
                key
            )

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