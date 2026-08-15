from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, JSON, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class InvestigationStatus(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    CORRELATING = "CORRELATING"
    REPORTING = "REPORTING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class TargetType(str, Enum):
    USERNAME = "USERNAME"
    DOMAIN = "DOMAIN"
    EMAIL = "EMAIL"


class ProviderRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    NOT_FOUND = "NOT_FOUND"
    RATE_LIMITED = "RATE_LIMITED"
    TIMEOUT = "TIMEOUT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[InvestigationStatus] = mapped_column(
        SAEnum(InvestigationStatus, name="investigation_status"),
        default=InvestigationStatus.CREATED,
        nullable=False,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    error_message: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    targets: Mapped[list["Target"]] = relationship(
        back_populates="investigation",
        cascade="all, delete-orphan",
    )

    provider_runs: Mapped[list["ProviderRun"]] = relationship(
        back_populates="investigation",
        cascade="all, delete-orphan",
    )


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    investigation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )

    type: Mapped[TargetType] = mapped_column(
        SAEnum(TargetType, name="target_type"),
        nullable=False,
    )

    value: Mapped[str] = mapped_column(String(500), nullable=False)

    normalized_value: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    investigation: Mapped["Investigation"] = relationship(
        back_populates="targets",
    )


class ProviderRun(Base):
    __tablename__ = "provider_runs"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    investigation_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("investigations.id", ondelete="CASCADE"),
        nullable=False,
    )

    provider_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[ProviderRunStatus] = mapped_column(
        SAEnum(ProviderRunStatus, name="provider_run_status"),
        default=ProviderRunStatus.PENDING,
        nullable=False,
    )

    result: Mapped[dict | None] = mapped_column(JSON)

    error_code: Mapped[str | None] = mapped_column(String(100))

    error_message: Mapped[str | None] = mapped_column(Text)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    investigation: Mapped["Investigation"] = relationship(
        back_populates="provider_runs",
    )