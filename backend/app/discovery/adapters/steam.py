from __future__ import annotations

import re
from typing import Any

import httpx

from app.core.config import settings
from app.discovery.schemas import DiscoveryCandidate

from .base import DiscoveryAdapter


STEAM_ID64_RE = re.compile(r"^\d{17}$")

STEAM_PROFILE_PREFIX = (
    "https://steamcommunity.com/profiles/"
)

STEAM_VANITY_PREFIX = (
    "https://steamcommunity.com/id/"
)


class SteamDiscoveryAdapter(
    DiscoveryAdapter
):
    provider_name = "steam"

    async def search(
        self,
        query: str,
    ) -> list[DiscoveryCandidate]:

        query = query.strip()

        if not query:
            return []

        async with httpx.AsyncClient(
            base_url=settings.steam_api_base_url,
            timeout=15.0,
        ) as client:

            steamid, resolution_type = (
                await self._resolve_identifier(
                    client,
                    query,
                )
            )

            if not steamid:
                return []

            profile = await self._get_profile(
                client,
                steamid,
            )

            if not profile:
                return []

            username = profile.get(
                "personaname"
            )

            profile_url = profile.get(
                "profileurl"
            )

            candidate = DiscoveryCandidate(
                provider="steam",
                provider_user_id=steamid,
                username=username,
                display_name=username,
                profile_url=profile_url,
                avatar_url=profile.get(
                    "avatarfull"
                ),
                confidence=1.0,
                match_type=(
                    "EXACT_IDENTIFIER_MATCH"
                ),
                reasons=[
                    (
                        "Steam profile resolved from "
                        f"{resolution_type.lower()}"
                    ),
                ],
                identifiers={
                    "steamid64": steamid,
                },
                metadata={
                    "discovery_source": (
                        "steam_identifier_resolution"
                    ),
                    "resolution_type": (
                        resolution_type
                    ),
                    "persona_state": profile.get(
                        "personastate"
                    ),
                    "profile_state": profile.get(
                        "profilestate"
                    ),
                    "community_visibility_state": (
                        profile.get(
                            "communityvisibilitystate"
                        )
                    ),
                    "last_logoff": profile.get(
                        "lastlogoff"
                    ),
                    "created_at": profile.get(
                        "timecreated"
                    ),
                    "country_code": profile.get(
                        "loccountrycode"
                    ),
                    "state_code": profile.get(
                        "locstatecode"
                    ),
                    "city_id": profile.get(
                        "loccityid"
                    ),
                },
            )

            return [candidate]

    async def _resolve_identifier(
        self,
        client: httpx.AsyncClient,
        value: str,
    ) -> tuple[str | None, str]:

        value = value.strip()

        # --------------------------------------------
        # SteamID64
        # --------------------------------------------
        if STEAM_ID64_RE.fullmatch(value):
            return value, "STEAMID64"

        # --------------------------------------------
        # Normalize http → https
        # --------------------------------------------
        if value.startswith("http://"):
            value = value.replace(
                "http://",
                "https://",
                1,
            )

        # --------------------------------------------
        # /profiles/<steamid>
        # --------------------------------------------
        if value.startswith(
            STEAM_PROFILE_PREFIX
        ):
            candidate = (
                value
                .rstrip("/")
                .removeprefix(
                    STEAM_PROFILE_PREFIX
                )
            )

            if STEAM_ID64_RE.fullmatch(
                candidate
            ):
                return candidate, "PROFILE_URL"

            return None, "INVALID_PROFILE_URL"

        # --------------------------------------------
        # /id/<vanity>
        # --------------------------------------------
        if value.startswith(
            STEAM_VANITY_PREFIX
        ):
            vanity = (
                value
                .rstrip("/")
                .removeprefix(
                    STEAM_VANITY_PREFIX
                )
            )

        else:
            # Treat a bare non-empty value as vanity.
            vanity = value.rstrip("/")

        if not vanity:
            return None, "EMPTY_IDENTIFIER"

        response = await client.get(
            "/ISteamUser/ResolveVanityURL/v1/",
            params={
                "key": settings.steam_api_key,
                "format": "json",
                "vanityurl": vanity,
                "url_type": 1,
            },
        )

        if response.status_code == 404:
            return None, "NOT_FOUND"

        response.raise_for_status()

        data: dict[str, Any] = (
            response.json()
        )

        steamid = (
            (data.get("response") or {})
            .get("steamid")
        )

        if steamid:
            return steamid, "VANITY"

        return None, "UNRESOLVED"

    async def _get_profile(
        self,
        client: httpx.AsyncClient,
        steamid: str,
    ) -> dict[str, Any] | None:

        response = await client.get(
            "/ISteamUser/GetPlayerSummaries/v2/",
            params={
                "key": settings.steam_api_key,
                "format": "json",
                "steamids": steamid,
            },
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()

        data: dict[str, Any] = (
            response.json()
        )

        players = (
            (data.get("response") or {})
            .get("players")
            or []
        )

        if not players:
            return None

        return players[0]