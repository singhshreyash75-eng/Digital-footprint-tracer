from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ProviderStatus(str, Enum):
    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class ProviderObservation:
    type: str
    source: str
    source_url: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    confidence: str = "MEDIUM"


@dataclass
class ProviderResult:
    provider_name: str
    status: ProviderStatus
    observations: list[ProviderObservation] = field(default_factory=list)
    raw_data: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None