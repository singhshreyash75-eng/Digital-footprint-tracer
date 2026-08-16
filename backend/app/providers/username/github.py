from __future__ import annotations

import asyncio
from typing import Any

import httpx

from app.core.config import settings
from app.investigations.models import TargetType
from app.providers.base import BaseProvider
from app.providers.schemas import (
    ProviderObservation,
    ProviderResult,
    ProviderStatus,
)


class GitHubProvider(BaseProvider):
    name = "github"
    supported_target_types = {TargetType.USERNAME}

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {settings.github_token}",
            "X-GitHub-Api-Version": "2026-03-10",
        }

    async def _get(
        self,
        client: httpx.AsyncClient,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        required: bool = False,
    ) -> Any | None:
        try:
            response = await client.get(
                path,
                params=params,
            )

            if response.status_code == 404:
                return None

            if response.status_code in (401, 403):
                if required:
                    response.raise_for_status()
                return None

            response.raise_for_status()
            return response.json()

        except httpx.HTTPError:
            if required:
                raise
            return None

    async def execute(
        self,
        target: Any,
        context: dict[str, Any] | None = None,
    ) -> ProviderResult:
        username = target.normalized_value

        async with httpx.AsyncClient(
            base_url=settings.github_api_base_url,
            headers=self._headers(),
            timeout=15.0,
            follow_redirects=False,
        ) as client:

            try:
                # -------------------------------------------------
                # Required: public target profile
                # -------------------------------------------------
                profile = await self._get(
                    client,
                    f"/users/{username}",
                    required=True,
                )

                if profile is None:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.NOT_FOUND,
                    )

                # -------------------------------------------------
                # Optional enrichment
                # -------------------------------------------------
                (
                    repositories_raw,
                    organizations_raw,
                    gists_raw,
                    events_raw,
                ) = await asyncio.gather(
                    self._get(
                        client,
                        f"/users/{username}/repos",
                        params={
                            "type": "all",
                            "sort": "updated",
                            "direction": "desc",
                            "per_page": 100,
                            "page": 1,
                        },
                    ),
                    self._get(
                        client,
                        f"/users/{username}/orgs",
                        params={
                            "per_page": 100,
                            "page": 1,
                        },
                    ),
                    self._get(
                        client,
                        f"/users/{username}/gists",
                        params={
                            "per_page": 100,
                            "page": 1,
                        },
                    ),
                    self._get(
                        client,
                        f"/users/{username}/events/public",
                        params={
                            "per_page": 100,
                            "page": 1,
                        },
                    ),
                )

                repositories_raw = repositories_raw or []
                organizations_raw = organizations_raw or []
                gists_raw = gists_raw or []
                events_raw = events_raw or []

                repositories = self._normalize_repositories(
                    repositories_raw
                )
                organizations = self._normalize_organizations(
                    organizations_raw
                )
                gists = self._normalize_gists(
                    gists_raw
                )
                events = self._normalize_events(
                    events_raw
                )

                observations = [
                    ProviderObservation(
                        type="GITHUB_PROFILE",
                        source="github",
                        source_url=profile.get(
                            "html_url"
                        ),
                        data={
                            "login": profile.get("login"),
                            "name": profile.get("name"),
                            "bio": profile.get("bio"),
                            "company": profile.get("company"),
                            "location": profile.get("location"),
                            "blog": profile.get("blog"),
                            "twitter_username": profile.get(
                                "twitter_username"
                            ),
                            "public_repos": profile.get(
                                "public_repos"
                            ),
                            "public_gists": profile.get(
                                "public_gists"
                            ),
                            "followers": profile.get(
                                "followers"
                            ),
                            "following": profile.get(
                                "following"
                            ),
                            "created_at": profile.get(
                                "created_at"
                            ),
                            "updated_at": profile.get(
                                "updated_at"
                            ),
                            "profile_url": profile.get(
                                "html_url"
                            ),
                        },
                        confidence="HIGH",
                    ),
                    ProviderObservation(
                        type="GITHUB_REPOSITORIES",
                        source="github",
                        source_url=(
                            f"https://github.com/"
                            f"{username}?tab=repositories"
                        ),
                        data={
                            "count": len(repositories),
                            "repositories": repositories,
                        },
                        confidence="HIGH",
                    ),
                    ProviderObservation(
                        type="GITHUB_ORGANIZATIONS",
                        source="github",
                        source_url=(
                            f"https://github.com/"
                            f"{username}"
                        ),
                        data={
                            "count": len(organizations),
                            "organizations": organizations,
                        },
                        confidence="HIGH",
                    ),
                    ProviderObservation(
                        type="GITHUB_GISTS",
                        source="github",
                        source_url=(
                            f"https://gist.github.com/"
                            f"{username}"
                        ),
                        data={
                            "count": len(gists),
                            "gists": gists,
                        },
                        confidence="HIGH",
                    ),
                    ProviderObservation(
                        type="GITHUB_PUBLIC_ACTIVITY",
                        source="github",
                        source_url=(
                            f"https://github.com/"
                            f"{username}"
                        ),
                        data={
                            "count": len(events),
                            "events": events,
                        },
                        confidence="MEDIUM",
                    ),
                ]

                return ProviderResult(
                    provider_name=self.name,
                    status=ProviderStatus.SUCCESS,
                    observations=observations,
                    raw_data={
                        "profile": profile,
                        "repositories": repositories_raw,
                        "organizations": organizations_raw,
                        "gists": gists_raw,
                        "public_events": events_raw,
                    },
                )

            except httpx.TimeoutException:
                return ProviderResult(
                    provider_name=self.name,
                    status=ProviderStatus.TIMEOUT,
                    error_code="GITHUB_TIMEOUT",
                    error_message=(
                        "GitHub request timed out."
                    ),
                )

            except httpx.HTTPStatusError as exc:
                status_code = (
                    exc.response.status_code
                    if exc.response is not None
                    else None
                )

                if status_code == 401:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.FAILED,
                        error_code="GITHUB_AUTH_FAILED",
                        error_message=(
                            "GitHub token authentication failed."
                        ),
                    )

                if status_code == 403:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.RATE_LIMITED,
                        error_code=(
                            "GITHUB_FORBIDDEN_OR_RATE_LIMITED"
                        ),
                        error_message=(
                            "GitHub rejected the request."
                        ),
                    )

                return ProviderResult(
                    provider_name=self.name,
                    status=ProviderStatus.FAILED,
                    error_code="GITHUB_HTTP_ERROR",
                    error_message=str(exc),
                )

            except httpx.HTTPError as exc:
                return ProviderResult(
                    provider_name=self.name,
                    status=ProviderStatus.FAILED,
                    error_code="GITHUB_HTTP_ERROR",
                    error_message=str(exc),
                )

            except Exception as exc:
                return ProviderResult(
                    provider_name=self.name,
                    status=ProviderStatus.FAILED,
                    error_code="GITHUB_PROVIDER_EXCEPTION",
                    error_message=str(exc),
                )

    @staticmethod
    def _normalize_repositories(
        repositories: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []

        for repo in repositories:
            license_data = repo.get("license") or {}

            normalized.append(
                {
                    "name": repo.get("name"),
                    "full_name": repo.get("full_name"),
                    "private": repo.get("private"),
                    "fork": repo.get("fork"),
                    "html_url": repo.get("html_url"),
                    "description": repo.get(
                        "description"
                    ),
                    "language": repo.get("language"),
                    "topics": repo.get(
                        "topics",
                        [],
                    ),
                    "default_branch": repo.get(
                        "default_branch"
                    ),
                    "stargazers_count": repo.get(
                        "stargazers_count"
                    ),
                    "watchers_count": repo.get(
                        "watchers_count"
                    ),
                    "forks_count": repo.get(
                        "forks_count"
                    ),
                    "open_issues_count": repo.get(
                        "open_issues_count"
                    ),
                    "archived": repo.get(
                        "archived"
                    ),
                    "disabled": repo.get(
                        "disabled"
                    ),
                    "visibility": repo.get(
                        "visibility"
                    ),
                    "license": {
                        "key": license_data.get("key"),
                        "name": license_data.get("name"),
                        "spdx_id": license_data.get(
                            "spdx_id"
                        ),
                    },
                    "created_at": repo.get(
                        "created_at"
                    ),
                    "updated_at": repo.get(
                        "updated_at"
                    ),
                    "pushed_at": repo.get(
                        "pushed_at"
                    ),
                }
            )

        return normalized

    @staticmethod
    def _normalize_organizations(
        organizations: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            {
                "login": org.get("login"),
                "id": org.get("id"),
                "avatar_url": org.get(
                    "avatar_url"
                ),
                "html_url": (
                    f"https://github.com/"
                    f"{org.get('login')}"
                )
                if org.get("login")
                else None,
            }
            for org in organizations
        ]

    @staticmethod
    def _normalize_gists(
        gists: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []

        for gist in gists:
            files = gist.get("files") or {}

            normalized.append(
                {
                    "id": gist.get("id"),
                    "html_url": gist.get(
                        "html_url"
                    ),
                    "description": gist.get(
                        "description"
                    ),
                    "public": gist.get("public"),
                    "created_at": gist.get(
                        "created_at"
                    ),
                    "updated_at": gist.get(
                        "updated_at"
                    ),
                    "files": [
                        {
                            "filename": filename,
                            "language": details.get(
                                "language"
                            ),
                            "type": details.get(
                                "type"
                            ),
                            "size": details.get(
                                "size"
                            ),
                        }
                        for filename, details in files.items()
                    ],
                }
            )

        return normalized

    @staticmethod
    def _normalize_events(
        events: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []

        for event in events:
            repo = event.get("repo") or {}
            payload = event.get("payload") or {}

            normalized.append(
                {
                    "id": event.get("id"),
                    "type": event.get("type"),
                    "created_at": event.get(
                        "created_at"
                    ),
                    "public": event.get("public"),
                    "repository": {
                        "name": repo.get("name"),
                        "url": repo.get("url"),
                    },
                    "action": payload.get("action"),
                    "ref": payload.get("ref"),
                }
            )

        return normalized