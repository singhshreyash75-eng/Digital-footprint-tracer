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

    async def execute(
        self,
        target: Any,
        context: dict[str, Any] | None = None,
    ) -> ProviderResult:
        username = target.normalized_value

        async with httpx.AsyncClient(
            base_url=settings.github_api_base_url,
            headers=self._headers(),
            timeout=10.0,
            follow_redirects=False,
        ) as client:
            try:
                # 1. Target profile
                user_response = await client.get(
                    f"/users/{username}"
                )

                if user_response.status_code == 404:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.NOT_FOUND,
                    )

                if user_response.status_code == 401:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.FAILED,
                        error_code="GITHUB_AUTH_FAILED",
                        error_message="GitHub token authentication failed.",
                    )

                if user_response.status_code == 403:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.RATE_LIMITED,
                        error_code="GITHUB_FORBIDDEN_OR_RATE_LIMITED",
                        error_message="GitHub rejected the request.",
                    )

                user_response.raise_for_status()
                user_data = user_response.json()

                # 2. Target's public repositories
                repos_response = await client.get(
                    f"/users/{username}/repos",
                    params={
                        "type": "all",
                        "sort": "updated",
                        "per_page": 100,
                    },
                )

                repos_response.raise_for_status()
                repos_data = repos_response.json()

                target_repositories = [
                    {
                        "name": repo.get("name"),
                        "full_name": repo.get("full_name"),
                        "private": repo.get("private"),
                        "html_url": repo.get("html_url"),
                        "description": repo.get("description"),
                        "language": repo.get("language"),
                        "default_branch": repo.get("default_branch"),
                        "stargazers_count": repo.get("stargazers_count"),
                        "forks_count": repo.get("forks_count"),
                        "updated_at": repo.get("updated_at"),
                    }
                    for repo in repos_data
                ]

                observation = ProviderObservation(
                    type="GITHUB_PROFILE",
                    source="github",
                    source_url=user_data.get("html_url"),
                    data={
                        "login": user_data.get("login"),
                        "name": user_data.get("name"),
                        "bio": user_data.get("bio"),
                        "company": user_data.get("company"),
                        "location": user_data.get("location"),
                        "blog": user_data.get("blog"),
                        "twitter_username": user_data.get(
                            "twitter_username"
                        ),
                        "public_repos": user_data.get("public_repos"),
                        "followers": user_data.get("followers"),
                        "following": user_data.get("following"),
                        "created_at": user_data.get("created_at"),
                        "updated_at": user_data.get("updated_at"),
                        "repositories": target_repositories,
                    },
                    confidence="HIGH",
                )

                return ProviderResult(
                    provider_name=self.name,
                    status=ProviderStatus.SUCCESS,
                    observations=[observation],
                    raw_data={
                        "user": user_data,
                        "repositories": repos_data,
                    },
                )

            except httpx.TimeoutException:
                return ProviderResult(
                    provider_name=self.name,
                    status=ProviderStatus.TIMEOUT,
                    error_code="GITHUB_TIMEOUT",
                    error_message="GitHub request timed out.",
                )

            except httpx.HTTPError as exc:
                return ProviderResult(
                    provider_name=self.name,
                    status=ProviderStatus.FAILED,
                    error_code="GITHUB_HTTP_ERROR",
                    error_message=str(exc),
                )