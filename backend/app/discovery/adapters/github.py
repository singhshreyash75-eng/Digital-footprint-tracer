from app.discovery.schemas import DiscoveryCandidate
from app.identity.resolver import GitHubIdentityResolver

from .base import DiscoveryAdapter


class GitHubDiscoveryAdapter(
    DiscoveryAdapter
):
    provider_name = "github"

    def __init__(self) -> None:
        self.resolver = GitHubIdentityResolver()

    async def search(
        self,
        query: str,
    ) -> list[DiscoveryCandidate]:

        candidates = await self.resolver.search(
            query
        )

        return [
            DiscoveryCandidate(
                provider=candidate.provider,
                provider_user_id=(
                    candidate.provider_user_id
                ),
                username=candidate.username,
                display_name=(
                    candidate.display_name
                ),
                profile_url=(
                    candidate.profile_url
                ),
                avatar_url=candidate.avatar_url,
                confidence=candidate.score,
                match_type=candidate.match_type,
                reasons=list(candidate.reasons),
                identifiers=dict(
                    candidate.identifiers
                ),
                metadata={
                    "discovery_source": (
                        "github_search"
                    ),
                    "public_repos": (
                        candidate.public_repos
                    ),
                    "followers": (
                        candidate.followers
                    ),
                    "following": (
                        candidate.following
                    ),
                    "bio": candidate.bio,
                    "location": candidate.location,
                    "company": candidate.company,
                    "blog": candidate.blog,
                    "confidence_percent": (
                        candidate.confidence_percent
                    ),
                },
            )
            for candidate in candidates
        ]