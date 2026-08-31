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

from .client import (
    StackExchangeAPIError,
    StackExchangeClient,
)


class StackExchangeProvider(BaseProvider):

    name = "stackexchange"

    supported_target_types = {
        TargetType.USERNAME,
    }

    supported_identifiers = [
        "site",
        "site_user_id",
        "account_id",
        "profile_url",
    ]

    capabilities = {
        "profile.read": True,
        "posts.read": True,
        "badges.read": True,
        "reputation.read": True,
        "comments.read": True,
        "associated.read": True,
    }

    capability_definitions = {
        "profile.read": CapabilityDefinition(
            name="profile.read",
            description=(
                "Read public Stack Exchange "
                "profile information."
            ),
            requires_auth=False,
            observation_types=(
                "STACKEXCHANGE_PROFILE",
            ),
        ),
        "posts.read": CapabilityDefinition(
            name="posts.read",
            description=(
                "Read public posts made by the "
                "selected Stack Exchange user."
            ),
            requires_auth=False,
            observation_types=(
                "STACKEXCHANGE_POSTS",
            ),
        ),
        "badges.read": CapabilityDefinition(
            name="badges.read",
            description=(
                "Read badges earned by the "
                "selected Stack Exchange user."
            ),
            requires_auth=False,
            observation_types=(
                "STACKEXCHANGE_BADGES",
            ),
        ),
        "reputation.read": CapabilityDefinition(
            name="reputation.read",
            description=(
                "Read public reputation changes "
                "for the selected Stack Exchange user."
            ),
            requires_auth=False,
            observation_types=(
                "STACKEXCHANGE_REPUTATION",
            ),
        ),
        "comments.read": CapabilityDefinition(
            name="comments.read",
            description=(
                "Read comments made by the "
                "selected Stack Exchange user."
            ),
            requires_auth=False,
            observation_types=(
                "STACKEXCHANGE_COMMENTS",
            ),
        ),
        "associated.read": CapabilityDefinition(
            name="associated.read",
            description=(
                "Read the user's associated "
                "Stack Exchange network accounts."
            ),
            requires_auth=False,
            observation_types=(
                "STACKEXCHANGE_ASSOCIATED",
            ),
        ),
    }

    def __init__(self) -> None:
        self.client: StackExchangeClient | None = None

    def _get_client(self) -> StackExchangeClient:
        if self.client is None:
            self.client = StackExchangeClient()

        return self.client

    @staticmethod
    def _resolve_identity(
        target: Any,
        context: dict[str, Any],
    ) -> tuple[str, int]:

        identifiers = dict(
            context.get(
                "identifiers",
                {}
            )
            or {}
        )

        site = (
            identifiers.get("site")
            or context.get("site")
        )

        site_user_id = (
            identifiers.get(
                "site_user_id"
            )
            or context.get(
                "site_user_id"
            )
        )

        provider_user_id = (
            context.get(
                "provider_user_id"
            )
            or getattr(
                target,
                "provider_user_id",
                None,
            )
        )

        if site_user_id is None and provider_user_id:
            provider_value = str(
                provider_user_id
            ).strip()

            if ":" in provider_value:
                parsed_site, parsed_user_id = (
                    provider_value.split(
                        ":",
                        1,
                    )
                )

                if site is None:
                    site = parsed_site

                site_user_id = parsed_user_id

        if not site:
            raise ValueError(
                "Stack Exchange site is missing."
            )

        if site_user_id is None:
            raise ValueError(
                "Stack Exchange site user ID is missing."
            )

        try:
            user_id = int(
                str(site_user_id).strip()
            )
        except ValueError as exc:
            raise ValueError(
                "Stack Exchange site user ID "
                "must be an integer."
            ) from exc

        return (
            str(site).strip().lower(),
            user_id,
        )

    @staticmethod
    def _failure_result(
        exc: StackExchangeAPIError,
        observations: list[
            ProviderObservation
        ],
    ) -> ProviderResult:

        if exc.backoff is not None:
            return ProviderResult(
                provider_name="stackexchange",
                status=ProviderStatus.RATE_LIMITED,
                observations=observations,
                error_code=(
                    "STACKEXCHANGE_BACKOFF"
                ),
                error_message=str(exc),
            )

        if exc.status_code == 429:
            return ProviderResult(
                provider_name="stackexchange",
                status=ProviderStatus.RATE_LIMITED,
                observations=observations,
                error_code=(
                    "STACKEXCHANGE_RATE_LIMITED"
                ),
                error_message=str(exc),
            )

        if (
            "timed out"
            in str(exc).lower()
        ):
            return ProviderResult(
                provider_name="stackexchange",
                status=ProviderStatus.TIMEOUT,
                observations=observations,
                error_code=(
                    "STACKEXCHANGE_TIMEOUT"
                ),
                error_message=str(exc),
            )

        return ProviderResult(
            provider_name="stackexchange",
            status=ProviderStatus.FAILED,
            observations=observations,
            error_code="STACKEXCHANGE_API_ERROR",
            error_message=str(exc),
        )

    async def execute(
        self,
        target: Any,
        context: dict[str, Any] | None = None,
    ) -> ProviderResult:

        context = context or {}

        observations: list[
            ProviderObservation
        ] = []

        try:
            client = self._get_client()

            requested = set(
                context.get(
                    "requested_capabilities",
                    self.capability_definitions.keys(),
                )
            )

            site, user_id = (
                self._resolve_identity(
                    target,
                    context,
                )
            )

            # -------------------------------------------------
            # PROFILE
            # -------------------------------------------------
            profile = None

            if "profile.read" in requested:
                payload = await client.get_users(
                    site=site,
                    user_ids=[user_id],
                )

                users = payload.get(
                    "items",
                    [],
                )

                if not users:
                    return ProviderResult(
                        provider_name=self.name,
                        status=ProviderStatus.NOT_FOUND,
                        observations=[],
                        error_code=(
                            "STACKEXCHANGE_USER_NOT_FOUND"
                        ),
                        error_message=(
                            "No Stack Exchange user "
                            "was found for the selected "
                            "site and user ID."
                        ),
                    )

                profile = users[0]

                observations.append(
                    ProviderObservation(
                        type=(
                            "STACKEXCHANGE_PROFILE"
                        ),
                        source=(
                            "stackexchange"
                        ),
                        source_url=(
                            profile.get("link")
                        ),
                        data={
                            "site": site,
                            "user_id": (
                                profile.get(
                                    "user_id"
                                )
                            ),
                            "account_id": (
                                profile.get(
                                    "account_id"
                                )
                            ),
                            "display_name": (
                                profile.get(
                                    "display_name"
                                )
                            ),
                            "location": (
                                profile.get(
                                    "location"
                                )
                            ),
                            "about_me": (
                                profile.get(
                                    "about_me"
                                )
                            ),
                            "website_url": (
                                profile.get(
                                    "website_url"
                                )
                            ),
                            "reputation": (
                                profile.get(
                                    "reputation"
                                )
                            ),
                            "question_count": (
                                profile.get(
                                    "question_count"
                                )
                            ),
                            "answer_count": (
                                profile.get(
                                    "answer_count"
                                )
                            ),
                            "accept_rate": (
                                profile.get(
                                    "accept_rate"
                                )
                            ),
                            "badge_counts": (
                                profile.get(
                                    "badge_counts"
                                )
                            ),
                            "user_type": (
                                profile.get(
                                    "user_type"
                                )
                            ),
                            "creation_date": (
                                profile.get(
                                    "creation_date"
                                )
                            ),
                            "last_access_date": (
                                profile.get(
                                    "last_access_date"
                                )
                            ),
                        },
                        confidence="HIGH",
                    )
                )

            # -------------------------------------------------
            # POSTS
            # -------------------------------------------------
            if "posts.read" in requested:

                payload = (
                    await client.get_user_posts(
                        site=site,
                        user_id=user_id,
                        pagesize=20,
                    )
                )

                observations.append(
                    ProviderObservation(
                        type=(
                            "STACKEXCHANGE_POSTS"
                        ),
                        source=(
                            "stackexchange"
                        ),
                        source_url=(
                            profile.get("link")
                            if profile
                            else None
                        ),
                        data={
                            "site": site,
                            "count": len(
                                payload.get(
                                    "items",
                                    []
                                )
                            ),
                            "posts": payload.get(
                                "items",
                                []
                            ),
                        },
                        confidence="HIGH",
                    )
                )

            # -------------------------------------------------
            # BADGES
            # -------------------------------------------------
            if "badges.read" in requested:

                payload = (
                    await client.get_user_badges(
                        site=site,
                        user_id=user_id,
                        pagesize=100,
                    )
                )

                observations.append(
                    ProviderObservation(
                        type=(
                            "STACKEXCHANGE_BADGES"
                        ),
                        source=(
                            "stackexchange"
                        ),
                        source_url=(
                            (
                                profile.get("link")
                                if profile
                                else None
                            )
                        ),
                        data={
                            "site": site,
                            "count": len(
                                payload.get(
                                    "items",
                                    []
                                )
                            ),
                            "badges": payload.get(
                                "items",
                                []
                            ),
                        },
                        confidence="HIGH",
                    )
                )

            # -------------------------------------------------
            # REPUTATION
            # -------------------------------------------------
            if "reputation.read" in requested:

                payload = (
                    await client.get_user_reputation(
                        site=site,
                        user_id=user_id,
                        pagesize=20,
                    )
                )

                observations.append(
                    ProviderObservation(
                        type=(
                            "STACKEXCHANGE_REPUTATION"
                        ),
                        source=(
                            "stackexchange"
                        ),
                        source_url=(
                            (
                                profile.get("link")
                                if profile
                                else None
                            )
                        ),
                        data={
                            "site": site,
                            "changes": payload.get(
                                "items",
                                []
                            ),
                        },
                        confidence="HIGH",
                    )
                )

            # -------------------------------------------------
            # COMMENTS
            # -------------------------------------------------
            if "comments.read" in requested:

                payload = (
                    await client.get_user_comments(
                        site=site,
                        user_id=user_id,
                        pagesize=20,
                    )
                )

                observations.append(
                    ProviderObservation(
                        type=(
                            "STACKEXCHANGE_COMMENTS"
                        ),
                        source=(
                            "stackexchange"
                        ),
                        source_url=(
                            (
                                profile.get("link")
                                if profile
                                else None
                            )
                        ),
                        data={
                            "site": site,
                            "count": len(
                                payload.get(
                                    "items",
                                    []
                                )
                            ),
                            "comments": payload.get(
                                "items",
                                []
                            ),
                        },
                        confidence="HIGH",
                    )
                )

            # -------------------------------------------------
            # ASSOCIATED NETWORK ACCOUNTS
            # -------------------------------------------------
            if "associated.read" in requested:

                # IMPORTANT:
                # /users/{id}/associated is a network-level
                # endpoint and MUST NOT receive a site parameter.
                payload = (
                    await client.get_associated_users(
                        user_id=user_id,
                    )
                )

                observations.append(
                    ProviderObservation(
                        type=(
                            "STACKEXCHANGE_ASSOCIATED"
                        ),
                        source=(
                            "stackexchange"
                        ),
                        source_url=(
                            (
                                profile.get("link")
                                if profile
                                else None
                            )
                        ),
                        data={
                            "site": site,
                            "associated_accounts": (
                                payload.get(
                                    "items",
                                    []
                                )
                            ),
                        },
                        confidence="HIGH",
                    )
                )

            return ProviderResult(
                provider_name=self.name,
                status=ProviderStatus.SUCCESS,
                observations=observations,
            )

        except StackExchangeAPIError as exc:
            return self._failure_result(
                exc,
                observations,
            )

        except Exception as exc:
            return ProviderResult(
                provider_name=self.name,
                status=ProviderStatus.FAILED,
                observations=observations,
                error_code=(
                    "STACKEXCHANGE_PROVIDER_ERROR"
                ),
                error_message=str(exc),
            )