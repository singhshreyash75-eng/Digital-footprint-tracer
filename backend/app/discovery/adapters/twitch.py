from app.discovery.schemas import (
    DiscoveryCandidate,
)
from app.providers.username.twitch.client import (
    TwitchAPIError,
    TwitchClient,
)


class TwitchDiscoveryAdapter:

    name = "twitch"

    def __init__(self) -> None:
        self.client = TwitchClient()

    async def search(
        self,
        query: str,
    ) -> list[DiscoveryCandidate]:

        normalized_query = (
            query.strip().lower()
        )

        if not normalized_query:
            return []

        try:
            payload = (
                await self.client.search_channels(
                    query=normalized_query,
                    first=10,
                    live_only=False,
                )
            )

        except TwitchAPIError:
            # DiscoveryEngine already isolates provider
            # failures. Returning [] keeps this adapter
            # independently safe as well.
            return []

        candidates: list[
            DiscoveryCandidate
        ] = []

        for item in payload.get(
            "data",
            [],
        ):

            user_id = item.get("id")
            login = item.get(
                "broadcaster_login"
            )
            display_name = item.get(
                "display_name"
            )

            if not user_id or not login:
                continue

            login_normalized = (
                login.strip().lower()
            )

            # Twitch search/channels with live_only=false
            # matches broadcaster login names. Treat an exact
            # login as the strongest discovery match.
            if (
                login_normalized
                == normalized_query
            ):
                confidence = 1.0
                match_type = (
                    "EXACT_LOGIN"
                )
                reasons = [
                    "Exact Twitch broadcaster "
                    "login match"
                ]
            else:
                confidence = 0.75
                match_type = (
                    "LOGIN_SEARCH_MATCH"
                )
                reasons = [
                    "Twitch broadcaster login "
                    "matched the search query"
                ]

            candidates.append(
                DiscoveryCandidate(
                    provider="twitch",
                    provider_user_id=str(
                        user_id
                    ),
                    username=login,
                    display_name=display_name,
                    profile_url=(
                        f"https://www.twitch.tv/"
                        f"{login}"
                    ),
                    confidence=confidence,
                    identifiers={
                        "twitch_user_id": str(
                            user_id
                        ),
                        "login": login,
                    },
                    metadata={
                        "discovery_source": (
                            "twitch_channel_search"
                        ),
                        "broadcaster_language": (
                            item.get(
                                "broadcaster_language"
                            )
                        ),
                        "game_id": (
                            item.get(
                                "game_id"
                            )
                        ),
                        "game_name": (
                            item.get(
                                "game_name"
                            )
                        ),
                        "is_live": (
                            item.get(
                                "is_live"
                            )
                        ),
                        "title": (
                            item.get(
                                "title"
                            )
                        ),
                        "started_at": (
                            item.get(
                                "started_at"
                            )
                        ),
                        "match_type": match_type,
                        "reasons": reasons,
                    },
                )
            )

        return candidates