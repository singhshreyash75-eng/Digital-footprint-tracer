from dataclasses import dataclass, field


@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    description: str

    requires_auth: bool = False

    observation_types: tuple[str, ...] = field(
        default_factory=tuple
    )