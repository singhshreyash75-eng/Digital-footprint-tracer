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


class TwitchAPIError(RuntimeError):
    """
    Structured Twitch API failure.

    status_code:
        HTTP status returned by Twitch, when available.
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code


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
            and now < self._token_expires_at - 60
        ):
            return self._access_token

        try:
            async with httpx.AsyncClient(
                timeout=20.0
            ) as client:
                response = await client.post(
                    self.TOKEN_URL,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": (
                            "client_credentials"
                        ),
                    },
                )

        except httpx.TimeoutException as exc:
            raise TwitchAPIError(
                "Twitch token request timed out.",
            ) from exc

        except httpx.HTTPError as exc:
            raise TwitchAPIError(
                f"Twitch token request failed: {exc}",
            ) from exc

        if response.is_error:
            raise TwitchAPIError(
                (
                    "Failed to obtain Twitch app "
                    "access token: "
                    f"{response.status_code}"
                ),
                status_code=response.status_code,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise TwitchAPIError(
                "Twitch token response was not valid JSON."
            ) from exc

        access_token = payload.get(
            "access_token"
        )

        expires_in = payload.get(
            "expires_in"
        )

        if not access_token:
            raise TwitchAPIError(
                "Twitch token response did not "
                "contain an access token."
            )

        if not isinstance(
            expires_in,
            (int, float),
        ):
            raise TwitchAPIError(
                "Twitch token response contained "
                "an invalid expires_in value."
            )

        self._access_token = str(
            access_token
        )

        self._token_expires_at = (
            now + float(expires_in)
        )

        return self._access_token

    async def _get(
        self,
        endpoint: str,
        params: Any = None,
    ) -> dict[str, Any]:

        access_token = (
            await self._get_access_token()
        )

        for attempt in range(2):
            headers = {
                "Authorization": (
                    f"Bearer {access_token}"
                ),
                "Client-Id": self.client_id,
            }

            try:
                async with httpx.AsyncClient(
                    timeout=20.0
                ) as client:
                    response = await client.get(
                        f"{self.BASE_URL}/{endpoint}",
                        headers=headers,
                        params=params,
                    )

            except httpx.TimeoutException as exc:
                raise TwitchAPIError(
                    (
                        "Twitch API request timed out "
                        f"for /{endpoint}."
                    ),
                ) from exc

            except httpx.HTTPError as exc:
                raise TwitchAPIError(
                    (
                        "Twitch API request failed "
                        f"for /{endpoint}: {exc}"
                    ),
                ) from exc

            # -------------------------------------------------
            # Access token expired/revoked.
            #
            # App access tokens cannot be refreshed; obtain a
            # new one through client credentials and retry once.
            # -------------------------------------------------
            if (
                response.status_code == 401
                and attempt == 0
            ):
                self._access_token = None
                self._token_expires_at = 0.0

                access_token = (
                    await self._get_access_token()
                )

                continue

            if response.is_error:
                try:
                    payload = response.json()

                    message = payload.get(
                        "message"
                    ) or payload.get(
                        "error"
                    )

                except ValueError:
                    message = None

                detail = (
                    str(message)
                    if message
                    else response.text
                )

                raise TwitchAPIError(
                    (
                        "Twitch API request failed: "
                        f"{response.status_code} "
                        f"{detail}"
                    ),
                    status_code=response.status_code,
                )

            try:
                return response.json()
            except ValueError as exc:
                raise TwitchAPIError(
                    (
                        "Twitch API returned an "
                        "invalid JSON response."
                    ),
                ) from exc

        raise TwitchAPIError(
            "Twitch API authentication retry failed.",
            status_code=401,
        )

    async def search_channels(
        self,
        query: str,
        first: int = 10,
        live_only: bool = False,
    ) -> dict[str, Any]:

        normalized_query = query.strip()

        if not normalized_query:
            return {
                "data": [],
                "pagination": {},
            }

        first = max(
            1,
            min(first, 100),
        )

        return await self._get(
            "search/channels",
            {
                "query": normalized_query,
                "first": first,
                "live_only": live_only,
            },
        )

    async def get_users_by_id(
        self,
        user_ids: list[str],
    ) -> dict[str, Any]:

        valid_ids = [
            str(value).strip()
            for value in user_ids
            if str(value).strip()
        ]

        if not valid_ids:
            return {
                "data": []
            }

        params = [
            ("id", user_id)
            for user_id in valid_ids
        ]

        return await self._get(
            "users",
            params=params,
        )

    async def get_users_by_login(
        self,
        logins: list[str],
    ) -> dict[str, Any]:

        valid_logins = [
            str(value).strip()
            for value in logins
            if str(value).strip()
        ]

        if not valid_logins:
            return {
                "data": []
            }

        params = [
            ("login", login)
            for login in valid_logins
        ]

        return await self._get(
            "users",
            params=params,
        )

    async def get_channels(
        self,
        broadcaster_ids: list[str],
    ) -> dict[str, Any]:

        valid_ids = [
            str(value).strip()
            for value in broadcaster_ids
            if str(value).strip()
        ]

        if not valid_ids:
            return {
                "data": []
            }

        params = [
            (
                "broadcaster_id",
                broadcaster_id,
            )
            for broadcaster_id in valid_ids
        ]

        return await self._get(
            "channels",
            params=params,
        )

    async def get_streams(
        self,
        user_ids: list[str],
    ) -> dict[str, Any]:

        valid_ids = [
            str(value).strip()
            for value in user_ids
            if str(value).strip()
        ]

        if not valid_ids:
            return {
                "data": []
            }

        params = [
            ("user_id", user_id)
            for user_id in valid_ids
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

        normalized_user_id = (
            str(user_id).strip()
        )

        if not normalized_user_id:
            return {
                "data": []
            }

        first = max(
            1,
            min(first, 100),
        )

        return await self._get(
            "videos",
            {
                "user_id": normalized_user_id,
                "first": first,
            },
        )