from typing import Any


OBSERVATION_SECTION_MAP: dict[str, str] = {
    "STEAM_PROFILE": "profile",
    "STEAM_OWNED_GAMES": "activity",
    "STEAM_RECENTLY_PLAYED": "history",
    "STEAM_LEVEL": "profile",
    "STEAM_BADGES": "profile",
    "STEAM_BAN_STATUS": "security",
    "STEAM_FRIENDS": "relationships",
    "STEAM_DERIVED_METRICS": "analytics",

    "GITHUB_PROFILE": "profile",
    "GITHUB_REPOSITORIES": "activity",
    "GITHUB_EVENTS": "history",
    "GITHUB_ORGANIZATIONS": "relationships",
}


DEFAULT_SECTIONS = [
    "profile",
    "activity",
    "history",
    "relationships",
    "security",
    "analytics",
]


def section_for_observation(
    observation_type: str,
) -> str:
    return OBSERVATION_SECTION_MAP.get(
        observation_type,
        "other",
    )


def build_sections(
    observations: list[dict[str, Any]],
) -> list[dict[str, Any]]:

    buckets: dict[
        str,
        list[dict[str, Any]],
    ] = {
        section: []
        for section in DEFAULT_SECTIONS
    }

    buckets["other"] = []

    for observation in observations:
        observation_type = observation.get(
            "type",
            "UNKNOWN",
        )

        section = section_for_observation(
            observation_type
        )

        buckets.setdefault(
            section,
            [],
        ).append(observation)

    return [
        {
            "name": section,
            "observation_types": [
                observation.get(
                    "type",
                    "UNKNOWN",
                )
                for observation in section_observations
            ],
            "observations": section_observations,
            "count": len(
                section_observations
            ),
        }
        for section, section_observations
        in buckets.items()
        if section_observations
    ]