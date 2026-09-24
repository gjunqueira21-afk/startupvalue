from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def uuid4_str() -> str:
    return str(uuid.uuid4())


def now_utc() -> datetime:
    return datetime.now(UTC)


class Role(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    analyst = "analyst"
    viewer = "viewer"


class SimulationStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_utc, onupdate=now_utc
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(Text)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Workspace(TimestampMixin, Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    name: Mapped[str] = mapped_column(String(160))


class WorkspaceMembership(TimestampMixin, Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False))


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Startup(TimestampMixin, Base):
    __tablename__ = "startups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    currency: Mapped[str] = mapped_column(String(3), default="BRL")
    profile: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    scenarios: Mapped[list[Scenario]] = relationship(back_populates="startup")


class Scenario(TimestampMixin, Base):
    __tablename__ = "scenarios"
    __table_args__ = (UniqueConstraint("startup_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    startup_id: Mapped[str] = mapped_column(ForeignKey("startups.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    mode: Mapped[str] = mapped_column(String(20), default="simple")
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    startup: Mapped[Startup] = relationship(back_populates="scenarios")
    revisions: Mapped[list[ScenarioRevision]] = relationship(back_populates="scenario")


class ScenarioRevision(TimestampMixin, Base):
    __tablename__ = "scenario_revisions"
    __table_args__ = (UniqueConstraint("scenario_id", "revision_no"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    scenario_id: Mapped[str] = mapped_column(ForeignKey("scenarios.id", ondelete="CASCADE"))
    revision_no: Mapped[int] = mapped_column(Integer)
    canonical_inputs: Mapped[dict[str, Any]] = mapped_column(JSON)
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))

    scenario: Mapped[Scenario] = relationship(back_populates="revisions")


class Simulation(TimestampMixin, Base):
    __tablename__ = "simulations"
    __table_args__ = (UniqueConstraint("workspace_id", "idempotency_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    scenario_revision_id: Mapped[str] = mapped_column(ForeignKey("scenario_revisions.id"))
    model_version: Mapped[str] = mapped_column(String(64))
    tax_version: Mapped[str] = mapped_column(String(64))
    seed: Mapped[int] = mapped_column()
    simulation_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[SimulationStatus] = mapped_column(
        Enum(SimulationStatus, native_enum=False), default=SimulationStatus.queued, index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(128))
    error_code: Mapped[str | None] = mapped_column(String(100))


class SimulationResult(TimestampMixin, Base):
    __tablename__ = "simulation_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    simulation_id: Mapped[str] = mapped_column(ForeignKey("simulations.id"), unique=True)
    schema_version: Mapped[str] = mapped_column(String(32))
    summary: Mapped[dict[str, Any]] = mapped_column(JSON)
    result_hash: Mapped[str] = mapped_column(String(64), unique=True)
    samples_object_key: Mapped[str] = mapped_column(String(512))
    samples_hash: Mapped[str] = mapped_column(String(64))


class SimulationSamples(Base):
    """Private, immutable scenario vectors used for derived decision analyses."""

    __tablename__ = "simulation_samples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    simulation_result_id: Mapped[str] = mapped_column(
        ForeignKey("simulation_results.id", ondelete="CASCADE"), unique=True
    )
    format_version: Mapped[str] = mapped_column(String(32))
    factor_names: Mapped[list[str]] = mapped_column(JSON)
    scenario_count: Mapped[int] = mapped_column(Integer)
    payload: Mapped[bytes] = mapped_column(LargeBinary)
    payload_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)


class Report(TimestampMixin, Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), index=True
    )
    simulation_result_id: Mapped[str] = mapped_column(ForeignKey("simulation_results.id"))
    template_version: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(30), index=True)
    object_key: Mapped[str | None] = mapped_column(String(512))
    checksum: Mapped[str | None] = mapped_column(String(64))


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid4_str)
    workspace_id: Mapped[str | None] = mapped_column(String(36), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(120), index=True)
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str | None] = mapped_column(String(36))
    metadata_redacted: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_utc)
