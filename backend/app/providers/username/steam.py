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

    def _params(
        self,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        params = {
            "key": settings.steam_api_key,
            "format": "json",
        }

        if extra:
            params.update(extra)

        return params

    async def _get(
        self,
        client: httpx.AsyncClient,
        path: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:

        response = await client.get(
            path,
            params=self._params(params),
        )

        if response.status_code == 404:
            return None

        if response.status_code == 403:
            raise httpx.HTTPStatusError(
                "Steam API returned 403",
                request=response.request,
                response=response,
            )

        response.raise_for_status()

        return response.json()

    async def _resolve_target(
        self,
        client: httpx.AsyncClient,
        value: str,
    ) -> tuple[str | None, str]:

        value = value.strip()

        # Direct SteamID64.
        if STEAM_ID64_RE.fullmatch(value):
            return value, "STEAMID64"

        # Full Steam profile URL:
        # https://steamcommunity.com/id/foo
        # https://steamcommunity.com/profiles/7656...
        if value.startswith("https://steamcommunity.com/"):
            value = value.rstrip("/")

            profiles_prefix = (
                "https://steamcommunity.com/profiles/"
            )

            vanity_prefix = (
                "https://steamcommunity.com/id/"
            )

            if value.startswith(profiles_prefix):
                candidate = value[len(profiles_prefix):]

                if STEAM_ID64_RE.fullmatch(candidate):
                    return candidate, "PROFILE_URL"

            if value.startswith(vanity_prefix):
                value = value[len(vanity_prefix):]

        # Treat remaining input as a vanity URL slug.
        result = await self._get(
            client,
            "/ISteamUser/ResolveVanityURL/v1/",
            params={
                "vanityurl": value,
                "url_type": 1,
            },
        )

        steamid = (
            (result or {}).get("response") or {}
        ).get("steamid")

        if steamid:
            return steamid, "VANITY_URL"

        return None, "UNRESOLVED"

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
                # -------------------------------------------------
                # 1. Resolve username / vanity URL → SteamID64
                # -------------------------------------------------
                steamid, resolution_type = (
                    await self._resolve_target(
                        client,
                        raw_value,
                    )
                )

                if not steamid:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.NOT_FOUND,
                        error_code="STEAM_PROFILE_NOT_RESOLVED",
                        error_message=(
                            "Input could not be resolved "
                            "to a SteamID."
                        ),
                    )

                # -------------------------------------------------
                # 2. Profile
                # -------------------------------------------------
                summary_response = await self._get(
                    client,
                    "/ISteamUser/GetPlayerSummaries/v2/",
                    params={
                        "steamids": steamid,
                    },
                )

                players = (
                    (summary_response or {}).get("response") or {}
                ).get("players") or []

                if not players:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.NOT_FOUND,
                        error_code="STEAM_PROFILE_NOT_FOUND",
                        error_message=(
                            "Steam profile was not returned."
                        ),
                    )

                profile = players[0]

                # -------------------------------------------------
                # 3. Enrichment endpoints
                # -------------------------------------------------
                owned_response = await self._get(
                    client,
                    "/IPlayerService/GetOwnedGames/v1/",
                    params={
                        "steamid": steamid,
                        "include_appinfo": "true",
                        "include_played_free_games": "true",
                    },
                )

                recent_response = await self._get(
                    client,
                    "/IPlayerService/GetRecentlyPlayedGames/v1/",
                    params={
                        "steamid": steamid,
                    },
                )

                level_response = await self._get(
                    client,
                    "/IPlayerService/GetSteamLevel/v1/",
                    params={
                        "steamid": steamid,
                    },
                )

                badges_response = await self._get(
                    client,
                    "/IPlayerService/GetBadges/v1/",
                    params={
                        "steamid": steamid,
                    },
                )

                bans_response = await self._get(
                    client,
                    "/ISteamUser/GetPlayerBans/v1/",
                    params={
                        "steamids": steamid,
                    },
                )

                observations: list[
                    ProviderObservation
                ] = []

                # -------------------------------------------------
                # PROFILE
                # -------------------------------------------------
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
                            "community_visibility_state": profile.get(
                                "communityvisibilitystate"
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

                # -------------------------------------------------
                # OWNED GAMES
                # -------------------------------------------------
                owned_data = (
                    owned_response or {}
                ).get("response") or {}

                games = owned_data.get(
                    "games"
                ) or []

                observations.append(
                    ProviderObservation(
                        type="STEAM_OWNED_GAMES",
                        source="steam",
                        source_url=(
                            f"https://steamcommunity.com/"
                            f"profiles/{steamid}/games/"
                        ),
                        data={
                            "game_count": owned_data.get(
                                "game_count",
                                len(games),
                            ),
                            "games": [
                                {
                                    "appid": game.get(
                                        "appid"
                                    ),
                                    "name": game.get(
                                        "name"
                                    ),
                                    "playtime_forever": game.get(
                                        "playtime_forever"
                                    ),
                                    "playtime_2weeks": game.get(
                                        "playtime_2weeks"
                                    ),
                                    "img_icon_url": game.get(
                                        "img_icon_url"
                                    ),
                                }
                                for game in games
                            ],
                        },
                        confidence="HIGH",
                    )
                )

                # -------------------------------------------------
                # RECENTLY PLAYED
                # -------------------------------------------------
                recent_data = (
                    recent_response or {}
                ).get("response") or {}

                recent_games = recent_data.get(
                    "games"
                ) or []

                observations.append(
                    ProviderObservation(
                        type="STEAM_RECENTLY_PLAYED",
                        source="steam",
                        source_url=(
                            f"https://steamcommunity.com/"
                            f"profiles/{steamid}/"
                        ),
                        data={
                            "total_count": recent_data.get(
                                "total_count",
                                len(recent_games),
                            ),
                            "games": [
                                {
                                    "appid": game.get(
                                        "appid"
                                    ),
                                    "name": game.get(
                                        "name"
                                    ),
                                    "playtime_2weeks": game.get(
                                        "playtime_2weeks"
                                    ),
                                    "playtime_forever": game.get(
                                        "playtime_forever"
                                    ),
                                }
                                for game in recent_games
                            ],
                        },
                        confidence="HIGH",
                    )
                )

                # -------------------------------------------------
                # STEAM LEVEL
                # -------------------------------------------------
                level_data = (
                    level_response or {}
                ).get("response") or {}

                observations.append(
                    ProviderObservation(
                        type="STEAM_LEVEL",
                        source="steam",
                        source_url=(
                            f"https://steamcommunity.com/"
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

                # -------------------------------------------------
                # BADGES
                # -------------------------------------------------
                badge_data = (
                    badges_response or {}
                ).get("response") or {}

                observations.append(
                    ProviderObservation(
                        type="STEAM_BADGES",
                        source="steam",
                        source_url=(
                            f"https://steamcommunity.com/"
                            f"profiles/{steamid}/badges/"
                        ),
                        data={
                            "badge_count": badge_data.get(
                                "badge_count"
                            ),
                            "badges": badge_data.get(
                                "badges",
                                [],
                            ),
                        },
                        confidence="HIGH",
                    )
                )

                # -------------------------------------------------
                # BAN STATUS
                # -------------------------------------------------
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

                observations.append(
                    ProviderObservation(
                        type="STEAM_BAN_STATUS",
                        source="steam",
                        source_url=(
                            f"https://steamcommunity.com/"
                            f"profiles/{steamid}/"
                        ),
                        data={
                            "vac_banned": ban_data.get(
                                "VACBanned"
                            ),
                            "number_of_vac_bans": ban_data.get(
                                "NumberOfVACBans"
                            ),
                            "days_since_last_ban": ban_data.get(
                                "DaysSinceLastBan"
                            ),
                            "number_of_game_bans": ban_data.get(
                                "NumberOfGameBans"
                            ),
                            "economy_ban": ban_data.get(
                                "EconomyBan"
                            ),
                            "community_banned": ban_data.get(
                                "CommunityBanned"
                            ),
                        },
                        confidence="HIGH",
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
                            "resolution_type": resolution_type,
                        },
                        "profile": profile,
                        "owned_games": owned_response,
                        "recently_played": recent_response,
                        "steam_level": level_response,
                        "badges": badges_response,
                        "ban_status": bans_response,
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

                if status_code == 403:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.RATE_LIMITED,
                        error_code="STEAM_403",
                        error_message=(
                            "Steam rejected the request. "
                            "This may indicate key restrictions, "
                            "permissions, or rate limiting."
                        ),
                    )

                if status_code == 429:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.RATE_LIMITED,
                        error_code="STEAM_RATE_LIMITED",
                        error_message=(
                            "Steam API rate limit was reached."
                        ),
                    )

                if status_code == 401:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.FAILED,
                        error_code="STEAM_AUTH_FAILED",
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
                    error_code="STEAM_PROVIDER_EXCEPTION",
                    error_message=str(exc),
                )