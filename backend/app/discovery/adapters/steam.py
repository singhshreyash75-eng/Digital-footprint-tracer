from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.discovery.schemas import DiscoveryCandidate

from .base import DiscoveryAdapter


STEAM_ID64_RE = re.compile(r"^\d{17}$")
STEAM_PROFILE_HOSTS = {
    "steamcommunity.com",
    "www.steamcommunity.com",
}


class SteamDiscoveryAdapter(DiscoveryAdapter):
    provider_name = "steam"

    async def search(
        self,
        query: str,
    ) -> list[DiscoveryCandidate]:
        value = query.strip()

        if not value:
            return []

        async with httpx.AsyncClient(
            base_url=settings.steam_api_base_url,
            timeout=10.0,
        ) as client:
            try:
                steamid, resolution_type = (
                    await self._resolve_identifier(
                        client,
                        value,
                    )
                )
            except httpx.HTTPError:
                return []

            if not steamid:
                return []

            try:
                profile = await self._get_profile(
                    client,
                    steamid,
                )
            except httpx.HTTPError:
                return []

            if not profile:
                return []

            username = profile.get("personaname")
            profile_url = profile.get("profileurl")

            return [
                DiscoveryCandidate(
                    provider="steam",
                    provider_user_id=steamid,
                    username=username,
                    display_name=username,
                    profile_url=profile_url,
                    avatar_url=profile.get("avatarfull"),
                    confidence=1.0,
                    match_type="EXACT_IDENTIFIER_MATCH",
                    reasons=[
                        (
                            "Steam profile resolved from "
                            f"{resolution_type.lower()}"
                        )
                    ],
                    identifiers={
                        "steamid64": steamid,
                        **(
                            {
                                "vanity_url": value,
                            }
                            if resolution_type == "VANITY"
                            else {}
                        ),
                    },
                    metadata={
                        "discovery_source": (
                            "steam_identifier_resolution"
                        ),
                        "resolution_type": resolution_type,
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
            ]

    async def _resolve_identifier(
        self,
        client: httpx.AsyncClient,
        value: str,
    ) -> tuple[str | None, str]:
        value = value.strip()

        if STEAM_ID64_RE.fullmatch(value):
            return value, "STEAMID64"

        if value.isdigit():
            # A bare numeric SteamID64 must contain exactly
            # 17 digits. Do not reinterpret arbitrary numbers
            # as vanity names.
            return None, "INVALID_STEAMID64"

        normalized_url = value

        if normalized_url.startswith("http://"):
            normalized_url = (
                "https://"
                + normalized_url[len("http://"):]
            )

        if normalized_url.startswith(
            ("https://", "http://")
        ):
            parsed = urlparse(normalized_url)

            if parsed.netloc.lower() not in STEAM_PROFILE_HOSTS:
                return None, "INVALID_PROFILE_HOST"

            parts = [
                part
                for part in parsed.path.split("/")
                if part
            ]

            if len(parts) < 2:
                return None, "INVALID_PROFILE_URL"

            kind = parts[0].lower()
            identifier = parts[1].strip()

            if kind == "profiles":
                if STEAM_ID64_RE.fullmatch(identifier):
                    return identifier, "PROFILE_URL"

                return None, "INVALID_PROFILE_URL"

            if kind == "id":
                if not identifier:
                    return None, "INVALID_VANITY_URL"

                return await self._resolve_vanity(
                    client,
                    identifier,
                )

            return None, "INVALID_PROFILE_URL"

        return await self._resolve_vanity(
            client,
            value.rstrip("/"),
        )

    async def _resolve_vanity(
        self,
        client: httpx.AsyncClient,
        vanity: str,
    ) -> tuple[str | None, str]:
        vanity = vanity.strip()

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

        data: dict[str, Any] = response.json()
        payload = data.get("response") or {}

        steamid = payload.get("steamid")

        if steamid and STEAM_ID64_RE.fullmatch(
            str(steamid)
        ):
            return str(steamid), "VANITY"

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

        data: dict[str, Any] = response.json()

        players = (
            (data.get("response") or {})
            .get("players")
            or []
        )

        if not players:
            return None

        return players[0]
