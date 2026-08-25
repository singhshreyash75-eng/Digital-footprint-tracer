from typing import Any

from app.investigations.models import TargetType
from app.providers.base import BaseProvider
from app.providers.contracts.capability import (
    CapabilityDefinition,
)
from app.providers.schemas import (
    ProviderObservation,
    ProviderResult,
    ProviderStatus,
)

from .client import TwitchClient


class TwitchProvider(BaseProvider):

    name = "twitch"

    supported_target_types = {
        TargetType.USERNAME,
    }

    supported_identifiers = [
        "twitch_user_id",
        "login",
        "profile_url",
    ]

    capabilities = {
        "profile.read": True,
        "channel.read": True,
        "stream.read": True,
        "videos.read": True,
    }

    capability_definitions = {
        "profile.read": CapabilityDefinition(
            name="profile.read",
            description=(
                "Read public Twitch user "
                "profile information."
            ),
            requires_auth=False,
            observation_types=(
                "TWITCH_PROFILE",
            ),
        ),
        "channel.read": CapabilityDefinition(
            name="channel.read",
            description=(
                "Read public Twitch channel "
                "information."
            ),
            requires_auth=False,
            observation_types=(
                "TWITCH_CHANNEL",
            ),
        ),
        "stream.read": CapabilityDefinition(
            name="stream.read",
            description=(
                "Read the current public Twitch "
                "stream state."
            ),
            requires_auth=False,
            observation_types=(
                "TWITCH_STREAM",
            ),
        ),
        "videos.read": CapabilityDefinition(
            name="videos.read",
            description=(
                "Read publicly available Twitch "
                "videos and VODs."
            ),
            requires_auth=False,
            observation_types=(
                "TWITCH_VIDEOS",
            ),
        ),
    }

    def __init__(self) -> None:
        self.client: TwitchClient | None = None

    def _get_client(self) -> TwitchClient:
        if self.client is None:
            self.client = TwitchClient()

        return self.client

    @staticmethod
    def _resolve_user_id(
        target: Any,
        context: dict[str, Any],
    ) -> str:
        """
        Resolve the Twitch user ID from the selected
        provider identity.

        SubjectIdentity.provider_user_id is the canonical
        identity value for provider execution.
        """

        # Preferred: explicitly supplied provider user ID.
        context_user_id = context.get(
            "provider_user_id"
        )

        if context_user_id:
            return str(
                context_user_id
            ).strip()

        # Subject / identity-like target.
        target_user_id = getattr(
            target,
            "provider_user_id",
            None,
        )

        if target_user_id:
            return str(
                target_user_id
            ).strip()

        # Fallback for older target-based execution.
        normalized_value = getattr(
            target,
            "normalized_value",
            None,
        )

        if normalized_value:
            return str(
                normalized_value
            ).strip()

        raise ValueError(
            "Unable to resolve Twitch provider user ID."
        )

    async def execute(
        self,
        target: Any,
        context: dict[str, Any] | None = None,
    ) -> ProviderResult:

        context = context or {}

        client = self._get_client()

        requested = set(
            context.get(
                "requested_capabilities",
                self.capability_definitions.keys(),
            )
        )

        try:
            user_id = self._resolve_user_id(
                target,
                context,
            )
        except Exception as exc:
            return ProviderResult(
                provider_name=self.name,
                status=ProviderStatus.FAILED,
                error_code="TWITCH_IDENTITY_ERROR",
                error_message=str(exc),
            )

        observations: list[
            ProviderObservation
        ] = []

        try:

            # -------------------------------------------------
            # PROFILE
            # -------------------------------------------------
            if "profile.read" in requested:

                payload = (
                    await client.get_users_by_id(
                        [user_id]
                    )
                )

                users = payload.get(
                    "data",
                    [],
                )

                if not users:
                    return ProviderResult(
                        provider_name=self.name,
                        status=(
                            ProviderStatus.NOT_FOUND
                        ),
                        observations=observations,
                    )

                user = users[0]

                observations.append(
                    ProviderObservation(
                        type="TWITCH_PROFILE",
                        source="twitch",
                        source_url=(
                            "https://www.twitch.tv/"
                            f"{user.get('login')}"
                        ),
                        data={
                            "id": user.get(
                                "id"
                            ),
                            "login": user.get(
                                "login"
                            ),
                            "display_name": user.get(
                                "display_name"
                            ),
                            "type": user.get(
                                "type"
                            ),
                            "broadcaster_type": (
                                user.get(
                                    "broadcaster_type"
                                )
                            ),
                            "description": (
                                user.get(
                                    "description"
                                )
                            ),
                            "profile_image_url": (
                                user.get(
                                    "profile_image_url"
                                )
                            ),
                            "offline_image_url": (
                                user.get(
                                    "offline_image_url"
                                )
                            ),
                            "created_at": (
                                user.get(
                                    "created_at"
                                )
                            ),
                        },
                        confidence="HIGH",
                    )
                )

            # -------------------------------------------------
            # CHANNEL
            # -------------------------------------------------
            if "channel.read" in requested:

                payload = (
                    await client.get_channels(
                        [user_id]
                    )
                )

                channels = payload.get(
                    "data",
                    [],
                )

                if channels:
                    channel = channels[0]

                    observations.append(
                        ProviderObservation(
                            type="TWITCH_CHANNEL",
                            source="twitch",
                            source_url=(
                                "https://www.twitch.tv/"
                                f"{channel.get('broadcaster_login')}"
                            ),
                            data={
                                "broadcaster_id": (
                                    channel.get(
                                        "broadcaster_id"
                                    )
                                ),
                                "broadcaster_login": (
                                    channel.get(
                                        "broadcaster_login"
                                    )
                                ),
                                "broadcaster_name": (
                                    channel.get(
                                        "broadcaster_name"
                                    )
                                ),
                                "game_id": (
                                    channel.get(
                                        "game_id"
                                    )
                                ),
                                "game_name": (
                                    channel.get(
                                        "game_name"
                                    )
                                ),
                                "title": (
                                    channel.get(
                                        "title"
                                    )
                                ),
                                "language": (
                                    channel.get(
                                        "broadcaster_language"
                                    )
                                ),
                                "delay": (
                                    channel.get(
                                        "delay"
                                    )
                                ),
                                "started_at": (
                                    channel.get(
                                        "started_at"
                                    )
                                ),
                            },
                            confidence="HIGH",
                        )
                    )

            # -------------------------------------------------
            # STREAM
            # -------------------------------------------------
            if "stream.read" in requested:

                payload = (
                    await client.get_streams(
                        [user_id]
                    )
                )

                streams = payload.get(
                    "data",
                    [],
                )

                if streams:
                    stream = streams[0]

                    observations.append(
                        ProviderObservation(
                            type="TWITCH_STREAM",
                            source="twitch",
                            source_url=(
                                "https://www.twitch.tv/"
                                f"{stream.get('user_login')}"
                            ),
                            data={
                                "id": stream.get(
                                    "id"
                                ),
                                "user_id": stream.get(
                                    "user_id"
                                ),
                                "user_login": (
                                    stream.get(
                                        "user_login"
                                    )
                                ),
                                "user_name": (
                                    stream.get(
                                        "user_name"
                                    )
                                ),
                                "game_id": (
                                    stream.get(
                                        "game_id"
                                    )
                                ),
                                "game_name": (
                                    stream.get(
                                        "game_name"
                                    )
                                ),
                                "type": stream.get(
                                    "type"
                                ),
                                "title": stream.get(
                                    "title"
                                ),
                                "viewer_count": (
                                    stream.get(
                                        "viewer_count"
                                    )
                                ),
                                "started_at": (
                                    stream.get(
                                        "started_at"
                                    )
                                ),
                                "language": (
                                    stream.get(
                                        "language"
                                    )
                                ),
                                "thumbnail_url": (
                                    stream.get(
                                        "thumbnail_url"
                                    )
                                ),
                            },
                            confidence="HIGH",
                        )
                    )

            # -------------------------------------------------
            # VIDEOS
            # -------------------------------------------------
            if "videos.read" in requested:

                payload = (
                    await client.get_videos(
                        user_id=user_id,
                        first=10,
                    )
                )

                videos = []

                for video in payload.get(
                    "data",
                    [],
                ):
                    videos.append(
                        {
                            "id": video.get(
                                "id"
                            ),
                            "stream_id": video.get(
                                "stream_id"
                            ),
                            "user_id": video.get(
                                "user_id"
                            ),
                            "user_login": (
                                video.get(
                                    "user_login"
                                )
                            ),
                            "title": video.get(
                                "title"
                            ),
                            "description": (
                                video.get(
                                    "description"
                                )
                            ),
                            "created_at": (
                                video.get(
                                    "created_at"
                                )
                            ),
                            "published_at": (
                                video.get(
                                    "published_at"
                                )
                            ),
                            "url": video.get(
                                "url"
                            ),
                            "view_count": (
                                video.get(
                                    "view_count"
                                )
                            ),
                            "language": video.get(
                                "language"
                            ),
                            "type": video.get(
                                "type"
                            ),
                            "duration": (
                                video.get(
                                    "duration"
                                )
                            ),
                        }
                    )

                observations.append(
                    ProviderObservation(
                        type="TWITCH_VIDEOS",
                        source="twitch",
                        source_url=(
                            "https://www.twitch.tv/"
                        ),
                        data={
                            "count": len(videos),
                            "videos": videos,
                        },
                        confidence="HIGH",
                    )
                )

            return ProviderResult(
                provider_name=self.name,
                status=ProviderStatus.SUCCESS,
                observations=observations,
            )

        except Exception as exc:
            return ProviderResult(
                provider_name=self.name,
                status=ProviderStatus.FAILED,
                observations=observations,
                error_code="TWITCH_API_ERROR",
                error_message=str(exc),
            )