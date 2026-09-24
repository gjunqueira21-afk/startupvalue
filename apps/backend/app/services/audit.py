from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditEvent


def record_event(
    db: Session,
    *,
    action: str,
    resource_type: str,
    workspace_id: str | None,
    actor_id: str | None,
    resource_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditEvent(
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_redacted=metadata or {},
        )
    )
