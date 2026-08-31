import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[5]

load_dotenv(
    PROJECT_ROOT / ".env"
)


class StackExchangeAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        error_id: int | None = None,
        error_name: str | None = None,
        backoff: int | None = None,
    ) -> None:
        super().__init__(message)

        self.status_code = status_code
        self.error_id = error_id
        self.error_name = error_name
        self.backoff = backoff


class StackExchangeClient:
    BASE_URL = "https://api.stackexchange.com/2.3"

    DEFAULT_TIMEOUT = 20.0

    def __init__(self) -> None:
        self.api_key = os.getenv(
            "STACKEXCHANGE_API_KEY"
        )

        if not self.api_key:
            raise RuntimeError(
                "STACKEXCHANGE_API_KEY is not configured."
            )

    async def _get(
        self,
        endpoint: str,
        *,
        site: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        request_params = dict(
            params or {}
        )

        if site:
            request_params["site"] = site

        request_params["key"] = self.api_key

        try:
            async with httpx.AsyncClient(
                timeout=self.DEFAULT_TIMEOUT
            ) as client:
                response = await client.get(
                    f"{self.BASE_URL}/{endpoint}",
                    params=request_params,
                )

        except httpx.TimeoutException as exc:
            raise StackExchangeAPIError(
                (
                    "Stack Exchange API request "
                    f"timed out for /{endpoint}."
                )
            ) from exc

        except httpx.HTTPError as exc:
            raise StackExchangeAPIError(
                (
                    "Stack Exchange API request "
                    f"failed for /{endpoint}: {exc}"
                )
            ) from exc

        if response.status_code == 429:
            raise StackExchangeAPIError(
                (
                    "Stack Exchange API request "
                    "was rate limited."
                ),
                status_code=429,
            )

        if response.is_error:
            raise StackExchangeAPIError(
                (
                    "Stack Exchange API HTTP error: "
                    f"{response.status_code} "
                    f"{response.text}"
                ),
                status_code=response.status_code,
            )

        try:
            payload = response.json()

        except ValueError as exc:
            raise StackExchangeAPIError(
                "Stack Exchange API returned invalid JSON."
            ) from exc

        backoff = payload.get(
            "backoff"
        )

        if backoff is not None:
            try:
                backoff = int(backoff)
            except (TypeError, ValueError):
                backoff = None

        if "error_id" in payload:
            raise StackExchangeAPIError(
                (
                    "Stack Exchange API error: "
                    f"{payload.get('error_name', 'unknown')} "
                    f"({payload.get('error_id')})"
                ),
                status_code=response.status_code,
                error_id=payload.get(
                    "error_id"
                ),
                error_name=payload.get(
                    "error_name"
                ),
                backoff=backoff,
            )

        return payload

    async def search_users(
        self,
        *,
        site: str,
        query: str,
        pagesize: int = 20,
    ) -> dict[str, Any]:

        normalized_query = query.strip()

        if not normalized_query:
            return {
                "items": [],
                "has_more": False,
                "quota_remaining": None,
            }

        pagesize = max(
            1,
            min(pagesize, 100),
        )

        return await self._get(
            "users",
            site=site,
            params={
                "inname": normalized_query,
                "pagesize": pagesize,
                "order": "desc",
                "sort": "reputation",
            },
        )

    async def get_users(
        self,
        *,
        site: str,
        user_ids: list[int],
    ) -> dict[str, Any]:

        valid_ids = [
            int(value)
            for value in user_ids
        ]

        if not valid_ids:
            return {
                "items": [],
                "has_more": False,
            }

        ids = ";".join(
            str(value)
            for value in valid_ids
        )

        return await self._get(
            f"users/{ids}",
            site=site,
        )

    async def get_user_posts(
        self,
        *,
        site: str,
        user_id: int,
        pagesize: int = 20,
    ) -> dict[str, Any]:

        pagesize = max(
            1,
            min(pagesize, 100),
        )

        return await self._get(
            f"users/{user_id}/posts",
            site=site,
            params={
                "pagesize": pagesize,
                "order": "desc",
                "sort": "activity",
            },
        )

    async def get_user_badges(
        self,
        *,
        site: str,
        user_id: int,
        pagesize: int = 100,
    ) -> dict[str, Any]:

        pagesize = max(
            1,
            min(pagesize, 100),
        )

        return await self._get(
            f"users/{user_id}/badges",
            site=site,
            params={
                "pagesize": pagesize,
                "order": "desc",
                "sort": "rank",
            },
        )

    async def get_user_reputation(
        self,
        *,
        site: str,
        user_id: int,
        pagesize: int = 20,
    ) -> dict[str, Any]:

        pagesize = max(
            1,
            min(pagesize, 100),
        )

        return await self._get(
            f"users/{user_id}/reputation",
            site=site,
            params={
                "pagesize": pagesize,
                "order": "desc",
                "sort": "post_id",
            },
        )

    async def get_user_comments(
        self,
        *,
        site: str,
        user_id: int,
        pagesize: int = 20,
    ) -> dict[str, Any]:

        pagesize = max(
            1,
            min(pagesize, 100),
        )

        return await self._get(
            f"users/{user_id}/comments",
            site=site,
            params={
                "pagesize": pagesize,
                "order": "desc",
                "sort": "creation",
            },
        )

    async def get_associated_users(
        self,
        *,
        user_id: int,
    ) -> dict[str, Any]:

        return await self._get(
            f"users/{user_id}/associated"
        )