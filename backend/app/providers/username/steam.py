from __future__ import annotations

import re
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


STEAM_ID64_RE = re.compile(r"^\d{17}$")


class SteamProvider(BaseProvider):
    name = "steam"
    supported_target_types = {TargetType.USERNAME}

    # Coarse provider-level capabilities.
    capabilities = {
        "discover": True,
        "read": True,
        "write": False,
        "create": False,
        "history": True,
        "enrich": True,
    }

    # Identifiers accepted by this provider.
    supported_identifiers = [
        "steamid64",
        "profile_url",
        "vanity_url",
        "vanity_name",
    ]

    # Fine-grained capabilities used by the Sprint 6
    # capability planner/executor.
    capability_definitions = {
        "profile.read": {
            "description": (
                "Read public Steam profile information."
            ),
            "requires_auth": False,
            "observation_types": [
                "STEAM_PROFILE",
            ],
        },
        "games.read": {
            "description": (
                "Read publicly available owned-game information."
            ),
            "requires_auth": False,
            "observation_types": [
                "STEAM_OWNED_GAMES",
            ],
        },
        "history.read": {
            "description": (
                "Read publicly available recently played games."
            ),
            "requires_auth": False,
            "observation_types": [
                "STEAM_RECENTLY_PLAYED",
            ],
        },
        "level.read": {
            "description": (
                "Read Steam account level information."
            ),
            "requires_auth": False,
            "observation_types": [
                "STEAM_LEVEL",
            ],
        },
        "badges.read": {
            "description": (
                "Read Steam badge information."
            ),
            "requires_auth": False,
            "observation_types": [
                "STEAM_BADGES",
            ],
        },
        "security.read": {
            "description": (
                "Read publicly available Steam ban-status information."
            ),
            "requires_auth": False,
            "observation_types": [
                "STEAM_BAN_STATUS",
            ],
        },
        "friends.read": {
            "description": (
                "Read publicly available Steam friend information."
            ),
            "requires_auth": False,
            "observation_types": [
                "STEAM_FRIENDS",
            ],
        },
        "analytics.read": {
            "description": (
                "Return DFT-derived Steam activity metrics."
            ),
            "requires_auth": False,
            "observation_types": [
                "STEAM_DERIVED_METRICS",
            ],
        },
    }

    def _base_params(
        self,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "key": settings.steam_api_key,
            "format": "json",
        }

        if extra:
            params.update(extra)

        return params

    async def _request(
        self,
        client: httpx.AsyncClient,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        response = await client.get(
            path,
            params=self._base_params(params),
        )

        if response.status_code == 404:
            return None

        response.raise_for_status()
        return response.json()

    async def _resolve_identifier(
        self,
        client: httpx.AsyncClient,
        value: str,
    ) -> tuple[str | None, str]:
        value = value.strip()

        if STEAM_ID64_RE.fullmatch(value):
            return value, "STEAMID64"

        if value.startswith("http://"):
            value = value.replace(
                "http://",
                "https://",
                1,
            )

        profile_prefix = (
            "https://steamcommunity.com/profiles/"
        )
        vanity_prefix = (
            "https://steamcommunity.com/id/"
        )

        if value.startswith(profile_prefix):
            candidate = value.rstrip("/").removeprefix(
                profile_prefix
            )

            if STEAM_ID64_RE.fullmatch(candidate):
                return candidate, "PROFILE_URL"

            return None, "INVALID_PROFILE_URL"

        if value.startswith(vanity_prefix):
            vanity = value.rstrip("/").removeprefix(
                vanity_prefix
            )
        else:
            vanity = value.rstrip("/")

        if not vanity:
            return None, "EMPTY_IDENTIFIER"

        response = await self._request(
            client,
            "/ISteamUser/ResolveVanityURL/v1/",
            params={
                "vanityurl": vanity,
                "url_type": 1,
            },
        )

        steamid = (
            (response or {}).get("response") or {}
        ).get("steamid")

        if steamid:
            return steamid, "VANITY"

        return None, "UNRESOLVED"

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _game_record(
        game: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "appid": game.get("appid"),
            "name": game.get("name"),
            "playtime_forever": game.get(
                "playtime_forever"
            ),
            "playtime_2weeks": game.get(
                "playtime_2weeks"
            ),
            "last_played": game.get(
                "rtime_last_played"
            ),
            "img_icon_url": game.get(
                "img_icon_url"
            ),
        }

    @classmethod
    def _derive_metrics(
        cls,
        owned_games: list[dict[str, Any]],
        recent_games: list[dict[str, Any]],
    ) -> dict[str, Any]:
        total_forever_minutes = sum(
            cls._safe_int(
                game.get("playtime_forever")
            )
            for game in owned_games
        )

        recent_minutes = sum(
            cls._safe_int(
                game.get("playtime_2weeks")
            )
            for game in recent_games
        )

        top_games = sorted(
            owned_games,
            key=lambda game: cls._safe_int(
                game.get("playtime_forever")
            ),
            reverse=True,
        )[:10]

        return {
            "owned_game_count": len(owned_games),
            "recent_game_count": len(recent_games),
            "total_playtime_minutes": (
                total_forever_minutes
            ),
            "total_playtime_hours": round(
                total_forever_minutes / 60,
                2,
            ),
            "recent_playtime_minutes": recent_minutes,
            "recent_playtime_hours": round(
                recent_minutes / 60,
                2,
            ),
            "top_played_games": [
                {
                    "appid": game.get("appid"),
                    "name": game.get("name"),
                    "playtime_forever": game.get(
                        "playtime_forever"
                    ),
                }
                for game in top_games
            ],
        }

    async def execute(
        self,
        target: Any,
        context: dict[str, Any] | None = None,
    ) -> ProviderResult:
        raw_value = target.normalized_value

        async with httpx.AsyncClient(
            base_url=settings.steam_api_base_url,
            timeout=15.0,
            follow_redirects=False,
        ) as client:
            try:
                steamid, resolution_type = (
                    await self._resolve_identifier(
                        client,
                        raw_value,
                    )
                )

                if not steamid:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.NOT_FOUND,
                        error_code=(
                            "STEAM_PROFILE_NOT_RESOLVED"
                        ),
                        error_message=(
                            "The supplied Steam identifier "
                            "could not be resolved."
                        ),
                    )

                # -----------------------------
                # Core profile
                # -----------------------------
                profile_response = await self._request(
                    client,
                    "/ISteamUser/GetPlayerSummaries/v2/",
                    params={
                        "steamids": steamid,
                    },
                )

                players = (
                    (profile_response or {}).get(
                        "response"
                    )
                    or {}
                ).get("players") or []

                if not players:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.NOT_FOUND,
                        error_code=(
                            "STEAM_PROFILE_NOT_FOUND"
                        ),
                        error_message=(
                            "Steam did not return a "
                            "profile for this identifier."
                        ),
                    )

                profile = players[0]

                observations: list[
                    ProviderObservation
                ] = []

                endpoint_errors: list[
                    dict[str, Any]
                ] = []

                # -----------------------------
                # Owned games
                # -----------------------------
                owned_response = None

                try:
                    owned_response = await self._request(
                        client,
                        "/IPlayerService/GetOwnedGames/v1/",
                        params={
                            "steamid": steamid,
                            "include_appinfo": "true",
                            "include_played_free_games": "true",
                        },
                    )
                except httpx.HTTPError as exc:
                    endpoint_errors.append(
                        {
                            "capability": "owned_games",
                            "error": str(exc),
                        }
                    )

                owned_data = (
                    (owned_response or {}).get(
                        "response"
                    )
                    or {}
                )

                owned_games = (
                    owned_data.get("games") or []
                )

                # -----------------------------
                # Recently played
                # -----------------------------
                recent_response = None

                try:
                    recent_response = await self._request(
                        client,
                        "/IPlayerService/GetRecentlyPlayedGames/v1/",
                        params={
                            "steamid": steamid,
                        },
                    )
                except httpx.HTTPError as exc:
                    endpoint_errors.append(
                        {
                            "capability": "recently_played",
                            "error": str(exc),
                        }
                    )

                recent_data = (
                    (recent_response or {}).get(
                        "response"
                    )
                    or {}
                )

                recent_games = (
                    recent_data.get("games") or []
                )

                # -----------------------------
                # Level
                # -----------------------------
                level_response = None

                try:
                    level_response = await self._request(
                        client,
                        "/IPlayerService/GetSteamLevel/v1/",
                        params={
                            "steamid": steamid,
                        },
                    )
                except httpx.HTTPError as exc:
                    endpoint_errors.append(
                        {
                            "capability": "steam_level",
                            "error": str(exc),
                        }
                    )

                level_data = (
                    (level_response or {}).get(
                        "response"
                    )
                    or {}
                )

                # -----------------------------
                # Badges
                # -----------------------------
                badges_response = None

                try:
                    badges_response = await self._request(
                        client,
                        "/IPlayerService/GetBadges/v1/",
                        params={
                            "steamid": steamid,
                        },
                    )
                except httpx.HTTPError as exc:
                    endpoint_errors.append(
                        {
                            "capability": "badges",
                            "error": str(exc),
                        }
                    )

                badges_data = (
                    (badges_response or {}).get(
                        "response"
                    )
                    or {}
                )

                # -----------------------------
                # Ban status
                # -----------------------------
                bans_response = None

                try:
                    bans_response = await self._request(
                        client,
                        "/ISteamUser/GetPlayerBans/v1/",
                        params={
                            "steamids": steamid,
                        },
                    )
                except httpx.HTTPError as exc:
                    endpoint_errors.append(
                        {
                            "capability": "ban_status",
                            "error": str(exc),
                        }
                    )

                ban_players = (
                    (bans_response or {}).get(
                        "players"
                    )
                    or []
                )

                ban_data = (
                    ban_players[0]
                    if ban_players
                    else {}
                )

                # -----------------------------
                # Friends
                # -----------------------------
                friends_response = None

                try:
                    friends_response = await self._request(
                        client,
                        "/ISteamUser/GetFriendList/v1/",
                        params={
                            "steamid": steamid,
                            "relationship": "friend",
                        },
                    )
                except httpx.HTTPError as exc:
                    endpoint_errors.append(
                        {
                            "capability": "friends",
                            "error": str(exc),
                        }
                    )

                friends_data = (
                    (friends_response or {}).get(
                        "friendslist"
                    )
                    or {}
                )

                friends = (
                    friends_data.get("friends")
                    or []
                )

                # -----------------------------
                # Observations
                # -----------------------------
                observations.append(
                    ProviderObservation(
                        type="STEAM_PROFILE",
                        source="steam",
                        source_url=profile.get(
                            "profileurl"
                        ),
                        data={
                            "steamid": profile.get(
                                "steamid"
                            ),
                            "personaname": profile.get(
                                "personaname"
                            ),
                            "profile_url": profile.get(
                                "profileurl"
                            ),
                            "avatar": profile.get(
                                "avatar"
                            ),
                            "avatar_medium": profile.get(
                                "avatarmedium"
                            ),
                            "avatar_full": profile.get(
                                "avatarfull"
                            ),
                            "persona_state": profile.get(
                                "personastate"
                            ),
                            "community_visibility_state": (
                                profile.get(
                                    "communityvisibilitystate"
                                )
                            ),
                            "profile_state": profile.get(
                                "profilestate"
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
                        confidence="HIGH",
                    )
                )

                observations.append(
                    ProviderObservation(
                        type="STEAM_OWNED_GAMES",
                        source="steam",
                        source_url=(
                            "https://steamcommunity.com/"
                            f"profiles/{steamid}/games/"
                        ),
                        data={
                            "game_count": owned_data.get(
                                "game_count",
                                len(owned_games),
                            ),
                            "games": [
                                self._game_record(game)
                                for game in owned_games
                            ],
                        },
                        confidence="HIGH",
                    )
                )

                observations.append(
                    ProviderObservation(
                        type="STEAM_RECENTLY_PLAYED",
                        source="steam",
                        source_url=(
                            "https://steamcommunity.com/"
                            f"profiles/{steamid}/"
                        ),
                        data={
                            "total_count": recent_data.get(
                                "total_count",
                                len(recent_games),
                            ),
                            "games": [
                                self._game_record(game)
                                for game in recent_games
                            ],
                        },
                        confidence="HIGH",
                    )
                )

                observations.append(
                    ProviderObservation(
                        type="STEAM_LEVEL",
                        source="steam",
                        source_url=(
                            "https://steamcommunity.com/"
                            f"profiles/{steamid}/"
                        ),
                        data={
                            "steam_level": level_data.get(
                                "player_level"
                            ),
                        },
                        confidence="HIGH",
                    )
                )

                observations.append(
                    ProviderObservation(
                        type="STEAM_BADGES",
                        source="steam",
                        source_url=(
                            "https://steamcommunity.com/"
                            f"profiles/{steamid}/badges/"
                        ),
                        data={
                            "badge_count": badges_data.get(
                                "badge_count"
                            ),
                            "player_xp": badges_data.get(
                                "player_xp"
                            ),
                            "badges": badges_data.get(
                                "badges",
                                [],
                            ),
                        },
                        confidence="HIGH",
                    )
                )

                observations.append(
                    ProviderObservation(
                        type="STEAM_BAN_STATUS",
                        source="steam",
                        source_url=(
                            "https://steamcommunity.com/"
                            f"profiles/{steamid}/"
                        ),
                        data={
                            "vac_banned": ban_data.get(
                                "VACBanned"
                            ),
                            "number_of_vac_bans": (
                                ban_data.get(
                                    "NumberOfVACBans"
                                )
                            ),
                            "days_since_last_ban": (
                                ban_data.get(
                                    "DaysSinceLastBan"
                                )
                            ),
                            "number_of_game_bans": (
                                ban_data.get(
                                    "NumberOfGameBans"
                                )
                            ),
                            "economy_ban": ban_data.get(
                                "EconomyBan"
                            ),
                            "community_banned": (
                                ban_data.get(
                                    "CommunityBanned"
                                )
                            ),
                        },
                        confidence="HIGH",
                    )
                )

                observations.append(
                    ProviderObservation(
                        type="STEAM_FRIENDS",
                        source="steam",
                        source_url=(
                            "https://steamcommunity.com/"
                            f"profiles/{steamid}/friends/"
                        ),
                        data={
                            "friend_count": len(
                                friends
                            ),
                            "friends": friends,
                        },
                        confidence="HIGH",
                    )
                )

                derived_metrics = self._derive_metrics(
                    owned_games,
                    recent_games,
                )

                observations.append(
                    ProviderObservation(
                        type="STEAM_DERIVED_METRICS",
                        source="steam",
                        source_url=(
                            "https://steamcommunity.com/"
                            f"profiles/{steamid}/"
                        ),
                        data=derived_metrics,
                        confidence="DERIVED",
                    )
                )

                return ProviderResult(
                    provider_name=self.name,
                    status=ProviderStatus.SUCCESS,
                    observations=observations,
                    raw_data={
                        "resolution": {
                            "input": raw_value,
                            "steamid": steamid,
                            "resolution_type": (
                                resolution_type
                            ),
                        },
                        "profile": profile,
                        "owned_games": owned_response,
                        "recently_played": recent_response,
                        "steam_level": level_response,
                        "badges": badges_response,
                        "ban_status": bans_response,
                        "friends": friends_response,
                        "endpoint_errors": endpoint_errors,
                    },
                )

            except httpx.TimeoutException:
                return ProviderResult(
                    provider_name=self.name,
                    status=ProviderStatus.TIMEOUT,
                    error_code="STEAM_TIMEOUT",
                    error_message=(
                        "Steam API request timed out."
                    ),
                )

            except httpx.HTTPStatusError as exc:
                status_code = (
                    exc.response.status_code
                    if exc.response is not None
                    else None
                )

                if status_code == 429:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.RATE_LIMITED,
                        error_code=(
                            "STEAM_RATE_LIMITED"
                        ),
                        error_message=(
                            "Steam API rate limit was reached."
                        ),
                    )

                if status_code == 403:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.RATE_LIMITED,
                        error_code="STEAM_403",
                        error_message=(
                            "Steam rejected the request. "
                            "This may indicate API restrictions "
                            "or rate limiting."
                        ),
                    )

                if status_code == 401:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.FAILED,
                        error_code=(
                            "STEAM_AUTH_FAILED"
                        ),
                        error_message=(
                            "Steam Web API key authentication failed."
                        ),
                    )

                return ProviderResult(
                    provider_name=self.name,
                    status=ProviderStatus.FAILED,
                    error_code="STEAM_HTTP_ERROR",
                    error_message=str(exc),
                )

            except httpx.HTTPError as exc:
                return ProviderResult(
                    provider_name=self.name,
                    status=ProviderStatus.FAILED,
                    error_code="STEAM_HTTP_ERROR",
                    error_message=str(exc),
                )

            except Exception as exc:
                return ProviderResult(
                    provider_name=self.name,
                    status=ProviderStatus.FAILED,
                    error_code=(
                        "STEAM_PROVIDER_EXCEPTION"
                    ),
                    error_message=str(exc),
                )