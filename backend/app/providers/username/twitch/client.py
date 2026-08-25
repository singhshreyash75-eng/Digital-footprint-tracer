import os
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


# Project root:
# <project>/.env
PROJECT_ROOT = Path(__file__).resolve().parents[5]

load_dotenv(
    PROJECT_ROOT / ".env"
)


class TwitchClient:
    BASE_URL = "https://api.twitch.tv/helix"
    TOKEN_URL = "https://id.twitch.tv/oauth2/token"

    def __init__(self) -> None:
        self.client_id = os.getenv(
            "TWITCH_CLIENT_ID"
        )

        self.client_secret = os.getenv(
            "TWITCH_CLIENT_SECRET"
        )

        if not self.client_id:
            raise RuntimeError(
                "TWITCH_CLIENT_ID is not configured."
            )

        if not self.client_secret:
            raise RuntimeError(
                "TWITCH_CLIENT_SECRET is not configured."
            )

        self._access_token: str | None = None

        self._token_expires_at: float = 0.0

    async def _get_access_token(self) -> str:
        now = time.time()

        if (
            self._access_token
            and now
            < self._token_expires_at - 60
        ):
            return self._access_token

        async with httpx.AsyncClient(
            timeout=20.0
        ) as client:

            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "client_credentials",
                },
            )

        if response.is_error:
            raise RuntimeError(
                "Failed to obtain Twitch app "
                "access token: "
                f"{response.status_code} "
                f"{response.text}"
            )

        payload = response.json()

        access_token = payload.get(
            "access_token"
        )

        expires_in = payload.get(
            "expires_in"
        )

        if not access_token:
            raise RuntimeError(
                "Twitch token response did not "
                "contain an access token."
            )

        if not isinstance(
            expires_in,
            (int, float),
        ):
            raise RuntimeError(
                "Twitch token response contained "
                "an invalid expires_in value."
            )

        self._access_token = access_token

        self._token_expires_at = (
            now + float(expires_in)
        )

        return access_token

    async def _get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        access_token = (
            await self._get_access_token()
        )

        headers = {
            "Authorization": (
                f"Bearer {access_token}"
            ),
            "Client-Id": self.client_id,
        }

        async with httpx.AsyncClient(
            timeout=20.0
        ) as client:

            response = await client.get(
                f"{self.BASE_URL}/{endpoint}",
                headers=headers,
                params=params or {},
            )

        if response.is_error:
            raise RuntimeError(
                "Twitch API request failed: "
                f"{response.status_code} "
                f"{response.text}"
            )

        return response.json()

    async def search_channels(
        self,
        query: str,
        first: int = 10,
        live_only: bool = False,
    ) -> dict[str, Any]:

        return await self._get(
            "search/channels",
            {
                "query": query,
                "first": first,
                "live_only": live_only,
            },
        )

    async def get_users_by_id(
        self,
        user_ids: list[str],
    ) -> dict[str, Any]:

        params = [
            ("id", user_id)
            for user_id in user_ids
        ]

        return await self._get(
            "users",
            params=params,
        )

    async def get_users_by_login(
        self,
        logins: list[str],
    ) -> dict[str, Any]:

        params = [
            ("login", login)
            for login in logins
        ]

        return await self._get(
            "users",
            params=params,
        )

    async def get_channels(
        self,
        broadcaster_ids: list[str],
    ) -> dict[str, Any]:

        params = [
            (
                "broadcaster_id",
                broadcaster_id,
            )
            for broadcaster_id
            in broadcaster_ids
        ]

        return await self._get(
            "channels",
            params=params,
        )

    async def get_streams(
        self,
        user_ids: list[str],
    ) -> dict[str, Any]:

        params = [
            ("user_id", user_id)
            for user_id in user_ids
        ]

        return await self._get(
            "streams",
            params=params,
        )

    async def get_videos(
        self,
        user_id: str,
        first: int = 10,
    ) -> dict[str, Any]:

        return await self._get(
            "videos",
            {
                "user_id": user_id,
                "first": first,
            },
        )