from app.discovery.schemas import (
    DiscoveryCandidate,
)
from app.providers.username.twitch.client import (
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

        payload = (
            await self.client.search_channels(
                query=query,
                first=10,
                live_only=False,
            )
        )

        candidates: list[
            DiscoveryCandidate
        ] = []

        normalized_query = (
            query.strip().lower()
        )

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

            if not user_id:
                continue

            login_normalized = (
                login or ""
            ).lower()

            display_normalized = (
                display_name or ""
            ).lower()

            if (
                login_normalized
                == normalized_query
            ):
                confidence = 1.0
                match_type = (
                    "EXACT_LOGIN"
                )
                reasons = [
                    "Exact Twitch login match"
                ]

            elif (
                display_normalized
                == normalized_query
            ):
                confidence = 0.95
                match_type = (
                    "EXACT_DISPLAY_NAME"
                )
                reasons = [
                    "Exact Twitch display name match"
                ]

            else:
                confidence = 0.75
                match_type = (
                    "SEARCH_RELEVANCE"
                )
                reasons = [
                    "Twitch channel matched "
                    "the search query"
                ]

            candidates.append(
                DiscoveryCandidate(
                    provider="twitch",
                    provider_user_id=user_id,
                    username=login,
                    display_name=display_name,
                    profile_url=(
                        f"https://www.twitch.tv/"
                        f"{login}"
                        if login
                        else None
                    ),
                    confidence=confidence,
                    identifiers={
                        "twitch_user_id": user_id,
                        "login": login or "",
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
                        "game_id": item.get(
                            "game_id"
                        ),
                        "game_name": item.get(
                            "game_name"
                        ),
                        "is_live": item.get(
                            "is_live"
                        ),
                        "title": item.get(
                            "title"
                        ),
                        "started_at": item.get(
                            "started_at"
                        ),
                        "match_type": match_type,
                        "reasons": reasons,
                    },
                )
            )

        return candidates