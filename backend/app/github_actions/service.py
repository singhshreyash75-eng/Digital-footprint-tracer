from __future__ import annotations

import base64
import posixpath
from typing import Any

import httpx

from app.core.config import settings


class GitHubActionError(Exception):
    """Expected error raised by the authorized GitHub action layer."""


class GitHubActionService:
    def __init__(self) -> None:
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {settings.github_token}",
            "X-GitHub-Api-Version": "2026-03-10",
        }

    def _ensure_enabled(self) -> None:
        if not settings.github_actions_enabled:
            raise GitHubActionError(
                "GitHub actions are disabled. "
                "Enable GITHUB_ACTIONS_ENABLED=true "
                "for an authorized local test."
            )

    @staticmethod
    def _validate_repository_parts(
        owner: str,
        repo: str,
    ) -> tuple[str, str]:
        owner = owner.strip()
        repo = repo.strip()

        if not owner:
            raise GitHubActionError(
                "Repository owner cannot be empty."
            )

        if not repo:
            raise GitHubActionError(
                "Repository name cannot be empty."
            )

        if "/" in owner or "/" in repo:
            raise GitHubActionError(
                "Invalid repository owner or name."
            )

        return owner, repo

    @staticmethod
    def _validate_file_path(
        path: str,
    ) -> str:
        path = path.strip().lstrip("/")

        if not path:
            raise GitHubActionError(
                "File path cannot be empty."
            )

        normalized = posixpath.normpath(path)

        if normalized in {"", ".", ".."}:
            raise GitHubActionError(
                "Invalid file path."
            )

        if normalized.startswith("../"):
            raise GitHubActionError(
                "Path traversal is not allowed."
            )

        # Keep workflow mutation out of Sprint 4.
        if normalized.startswith(
            ".github/workflows/"
        ):
            raise GitHubActionError(
                "Workflow-file writes are disabled in Sprint 4."
            )

        return normalized

    async def _get_authenticated_user(
        self,
        client: httpx.AsyncClient,
    ) -> dict[str, Any]:
        response = await client.get(
            "/user"
        )

        if response.status_code == 401:
            raise GitHubActionError(
                "GitHub authentication failed."
            )

        if response.status_code == 403:
            raise GitHubActionError(
                "GitHub rejected the authenticated-user request."
            )

        response.raise_for_status()

        return response.json()

    async def get_repository_capabilities(
        self,
        owner: str,
        repo: str,
    ) -> dict[str, Any]:
        self._ensure_enabled()

        owner, repo = self._validate_repository_parts(
            owner,
            repo,
        )

        async with httpx.AsyncClient(
            base_url=settings.github_api_base_url,
            headers=self.headers,
            timeout=15.0,
        ) as client:

            authenticated_user = (
                await self._get_authenticated_user(
                    client
                )
            )

            response = await client.get(
                f"/repos/{owner}/{repo}"
            )

            if response.status_code == 404:
                return {
                    "owner": owner,
                    "repo": repo,
                    "exists": False,
                    "authenticated_user": authenticated_user.get(
                        "login"
                    ),
                    "can_read": False,
                    "can_write": False,
                    "can_maintain": False,
                    "can_admin": False,
                    "action_write_allowed": False,
                    "reason": (
                        "Repository was not found or "
                        "is not accessible by the authenticated token."
                    ),
                }

            if response.status_code == 401:
                raise GitHubActionError(
                    "GitHub authentication failed."
                )

            if response.status_code == 403:
                raise GitHubActionError(
                    "GitHub rejected the repository permission check."
                )

            response.raise_for_status()

            data = response.json()

            permissions = (
                data.get("permissions") or {}
            )

            can_read = bool(
                permissions.get("pull")
            )

            can_write = bool(
                permissions.get("push")
            )

            can_maintain = bool(
                permissions.get("maintain")
            )

            can_admin = bool(
                permissions.get("admin")
            )

            return {
                "owner": (
                    data.get("owner") or {}
                ).get(
                    "login",
                    owner,
                ),
                "repo": data.get(
                    "name",
                    repo,
                ),
                "exists": True,
                "authenticated_user": authenticated_user.get(
                    "login"
                ),
                "can_read": can_read,
                "can_write": can_write,
                "can_maintain": can_maintain,
                "can_admin": can_admin,
                "action_write_allowed": can_write,
                "reason": (
                    "Authenticated token has repository "
                    "write capability."
                    if can_write
                    else
                    "Authenticated token does not have "
                    "repository write capability."
                ),
            }

    async def write_file(
        self,
        *,
        owner: str,
        repo: str,
        path: str,
        content: str,
        message: str,
        branch: str | None = None,
        sha: str | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        self._ensure_enabled()

        if not confirm:
            raise GitHubActionError(
                "Explicit confirmation is required."
            )

        owner, repo = self._validate_repository_parts(
            owner,
            repo,
        )

        path = self._validate_file_path(
            path
        )

        message = message.strip()

        if not message:
            raise GitHubActionError(
                "Commit message cannot be empty."
            )

        capabilities = (
            await self.get_repository_capabilities(
                owner,
                repo,
            )
        )

        if not capabilities["exists"]:
            raise GitHubActionError(
                "Repository does not exist or is inaccessible."
            )

        if not capabilities["can_write"]:
            raise GitHubActionError(
                "Authenticated token does not have "
                "repository write permission."
            )

        encoded_content = base64.b64encode(
            content.encode("utf-8")
        ).decode("ascii")

        payload: dict[str, Any] = {
            "message": message,
            "content": encoded_content,
        }

        if branch:
            payload["branch"] = branch.strip()

        # GitHub requires the current blob SHA when updating
        # an existing file.
        if sha:
            payload["sha"] = sha.strip()

        async with httpx.AsyncClient(
            base_url=settings.github_api_base_url,
            headers=self.headers,
            timeout=15.0,
        ) as client:

            response = await client.put(
                f"/repos/{owner}/{repo}/contents/{path}",
                json=payload,
            )

            if response.status_code == 401:
                raise GitHubActionError(
                    "GitHub authentication failed."
                )

            if response.status_code == 403:
                raise GitHubActionError(
                    "GitHub rejected the repository write request."
                )

            if response.status_code == 409:
                raise GitHubActionError(
                    "GitHub reported a content conflict."
                )

            if response.status_code == 422:
                raise GitHubActionError(
                    "GitHub rejected the file write request."
                )

            response.raise_for_status()

            data = response.json()

            commit = data.get(
                "commit"
            ) or {}

            file_data = data.get(
                "content"
            ) or {}

            return {
                "action": "WRITE_FILE",
                "repository": f"{owner}/{repo}",
                "path": path,
                "commit": {
                    "sha": commit.get("sha"),
                    "url": commit.get("html_url"),
                },
                "content": {
                    "sha": file_data.get("sha"),
                    "path": file_data.get("path"),
                    "url": file_data.get("html_url"),
                },
            }

    async def create_repository(
        self,
        *,
        name: str,
        description: str | None = None,
        private: bool = True,
        homepage: str | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        self._ensure_enabled()

        if not confirm:
            raise GitHubActionError(
                "Explicit confirmation is required."
            )

        name = name.strip()

        if not name:
            raise GitHubActionError(
                "Repository name cannot be empty."
            )

        async with httpx.AsyncClient(
            base_url=settings.github_api_base_url,
            headers=self.headers,
            timeout=15.0,
        ) as client:

            authenticated_user = (
                await self._get_authenticated_user(
                    client
                )
            )

            payload: dict[str, Any] = {
                "name": name,
                "private": private,
            }

            if description:
                payload["description"] = (
                    description.strip()
                )

            if homepage:
                payload["homepage"] = (
                    homepage.strip()
                )

            response = await client.post(
                "/user/repos",
                json=payload,
            )

            if response.status_code == 401:
                raise GitHubActionError(
                    "GitHub authentication failed."
                )

            if response.status_code == 403:
                raise GitHubActionError(
                    "GitHub rejected repository creation. "
                    "Check the token's Administration: write "
                    "permission and account policy."
                )

            if response.status_code == 422:
                raise GitHubActionError(
                    "GitHub rejected repository creation, "
                    "possibly because the repository name already exists."
                )

            response.raise_for_status()

            data = response.json()

            return {
                "action": "CREATE_REPOSITORY",
                "authenticated_user": authenticated_user.get(
                    "login"
                ),
                "repository": {
                    "name": data.get("name"),
                    "full_name": data.get(
                        "full_name"
                    ),
                    "private": data.get(
                        "private"
                    ),
                    "html_url": data.get(
                        "html_url"
                    ),
                },
            }