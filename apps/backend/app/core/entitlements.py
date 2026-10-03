"""Commercial plan tiers and the entitlement resolver.

Resolves a workspace's persisted ``plan`` column value into the concrete
feature/limit matrix consumed by the API and report layers. Unknown or
missing plan values resolve to the ``free`` tier rather than raising, so a
workspace is never accidentally entitled to more than it has paid for.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db.models import Workspace
from app.services.audit import record_event


class PlanTier(str, enum.Enum):
    free = "free"
    empresario = "empresario"
    consultor = "consultor"
    escritorio = "escritorio"


@dataclass(frozen=True, slots=True)
class Entitlements:
    plan: PlanTier
    max_startups: int | None  # None = unlimited
    max_scenarios_per_run: int
    white_label: bool
    full_report: bool  # False => watermarked PDF
    target_plan_section: bool
    implied_multiples: bool


_MATRIX: dict[PlanTier, Entitlements] = {
    PlanTier.free: Entitlements(
        plan=PlanTier.free,
        max_startups=1,
        max_scenarios_per_run=1_000,
        white_label=False,
        full_report=False,
        target_plan_section=False,
        implied_multiples=False,
    ),
    PlanTier.empresario: Entitlements(
        plan=PlanTier.empresario,
        max_startups=5,
        max_scenarios_per_run=10_000,
        white_label=False,
        full_report=True,
        target_plan_section=True,
        implied_multiples=True,
    ),
    PlanTier.consultor: Entitlements(
        plan=PlanTier.consultor,
        max_startups=10,
        max_scenarios_per_run=25_000,
        white_label=True,
        full_report=True,
        target_plan_section=True,
        implied_multiples=True,
    ),
    PlanTier.escritorio: Entitlements(
        plan=PlanTier.escritorio,
        max_startups=None,
        max_scenarios_per_run=25_000,
        white_label=True,
        full_report=True,
        target_plan_section=True,
        implied_multiples=True,
    ),
}


def entitlements_for(plan_value: str | None) -> Entitlements:
    """Resolve a persisted plan value to its entitlement matrix.

    Unknown or missing values default to the free tier.
    """
    try:
        plan = PlanTier(plan_value)
    except ValueError:
        plan = PlanTier.free
    return _MATRIX[plan]


def set_workspace_plan(
    db: Session, *, workspace_id: str, plan: PlanTier, actor_id: str | None
) -> None:
    """Persist a workspace's plan tier and record an audit event.

    Does not commit; callers own the transaction boundary.
    """
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise ValueError(f"workspace_not_found:{workspace_id}")
    workspace.plan = plan.value
    db.flush()
    record_event(
        db,
        action="workspace.plan_changed",
        resource_type="workspace",
        workspace_id=workspace_id,
        actor_id=actor_id,
        resource_id=workspace_id,
        metadata={"plan": plan.value},
    )
