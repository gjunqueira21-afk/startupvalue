"""Platform admin backend.

Everything here is gated by ``require_platform_admin``, which is a strictly
platform-level check: it reloads the ``User`` row fresh from the database on
every request and 403s unless ``user.is_platform_admin`` is set, independent
of the caller's role within whatever workspace their session happens to be
scoped to (an owner of a free-tier workspace is not a platform admin, and a
platform admin's own workspace role is irrelevant to this gate).

No HTTP path in this module, or anywhere else in the API, ever sets
``is_platform_admin``. The only way to grant or revoke it is the operator
running ``scripts/set_admin.py`` directly against the database.

Data boundary: every response here is business metadata (counts, plan
tiers, waitlist contact fields, workspace membership). No route in this
module ever returns scenario inputs, simulation results/summaries, report
bytes, or branding content.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from io import StringIO
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select

from app.api.dependencies import Actor, Database
from app.api.schemas import ApiModel
from app.core.entitlements import PlanTier, set_workspace_plan
from app.db.models import (
    Report,
    Simulation,
    Startup,
    User,
    WaitlistEntry,
    Workspace,
    WorkspaceMembership,
    now_utc,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

_FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@", "\t", "\r")


def _csv_safe(value: str) -> str:
    """Neutralize CSV/Excel formula and DDE injection in exported cells.

    ``email`` and ``source`` originate from the unauthenticated public
    waitlist endpoint and are never sanitized for spreadsheet semantics. A
    value starting with ``=``, ``+``, ``-``, ``@``, a tab, or a carriage
    return is interpreted as a formula (or DDE payload) by Excel/Sheets when
    the exported file is opened, which can exfiltrate data via e.g.
    ``=HYPERLINK(...)``. Prefixing a literal single quote forces the
    spreadsheet to treat the cell as text while leaving the value itself
    untouched for any other consumer (plain CSV readers see the leading
    quote as ordinary data).
    """
    if value.startswith(_FORMULA_TRIGGER_CHARS):
        return "'" + value
    return value


def require_platform_admin(db: Database, actor: Actor) -> User:
    """403 ``admin_only`` unless the current user's platform flag is set.

    Reloads the user row rather than trusting any cached session value, so a
    revoke takes effect on the caller's very next request.
    """
    user = db.get(User, actor.user_id)
    if user is None or not user.is_platform_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "admin_only")
    return user


AdminUser = Annotated[User, Depends(require_platform_admin)]


class WorkspacesByPlan(ApiModel):
    free: int
    empresario: int
    consultor: int
    escritorio: int


class AdminOverviewResponse(ApiModel):
    users: int
    workspaces_by_plan: WorkspacesByPlan
    startups: int
    simulations: int
    simulations_last_7d: int
    reports: int
    waitlist_count: int


class WaitlistEntryResponse(ApiModel):
    id: str
    email: str
    plan_interest: str
    source: str
    created_at: datetime


class AdminWorkspaceResponse(ApiModel):
    id: str
    plan: str
    created_at: datetime
    startup_count: int
    member_email: str


class AdminPlanUpdateRequest(ApiModel):
    plan: PlanTier


class AdminPlanUpdateResponse(ApiModel):
    id: str
    plan: str


@router.get("/overview", response_model=AdminOverviewResponse)
def overview(db: Database, admin: AdminUser) -> AdminOverviewResponse:
    del admin
    users_count = db.scalar(select(func.count()).select_from(User)) or 0

    by_plan = {tier.value: 0 for tier in PlanTier}
    for plan_value, count in db.execute(
        select(Workspace.plan, func.count()).group_by(Workspace.plan)
    ).all():
        key = plan_value if plan_value in by_plan else PlanTier.free.value
        by_plan[key] += count

    startups_count = db.scalar(select(func.count()).select_from(Startup)) or 0
    simulations_count = db.scalar(select(func.count()).select_from(Simulation)) or 0

    cutoff = now_utc() - timedelta(days=7)
    simulations_last_7d = (
        db.scalar(
            select(func.count())
            .select_from(Simulation)
            .where(Simulation.created_at >= cutoff)
        )
        or 0
    )

    reports_count = db.scalar(select(func.count()).select_from(Report)) or 0
    waitlist_count = db.scalar(select(func.count()).select_from(WaitlistEntry)) or 0

    return AdminOverviewResponse(
        users=users_count,
        workspaces_by_plan=WorkspacesByPlan(**by_plan),
        startups=startups_count,
        simulations=simulations_count,
        simulations_last_7d=simulations_last_7d,
        reports=reports_count,
        waitlist_count=waitlist_count,
    )


@router.get("/waitlist", response_model=None)
def list_waitlist(
    db: Database,
    admin: AdminUser,
    format: Literal["json", "csv"] | None = None,
) -> Response | list[WaitlistEntryResponse]:
    del admin
    entries = db.scalars(select(WaitlistEntry).order_by(WaitlistEntry.created_at)).all()

    if format == "csv":
        buffer = StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["email", "plan_interest", "source", "created_at"])
        for entry in entries:
            writer.writerow(
                [
                    _csv_safe(entry.email),
                    _csv_safe(entry.plan_interest),
                    _csv_safe(entry.source),
                    _csv_safe(entry.created_at.isoformat()),
                ]
            )
        return Response(
            content=buffer.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="waitlist.csv"'},
        )

    return [
        WaitlistEntryResponse(
            id=entry.id,
            email=entry.email,
            plan_interest=entry.plan_interest,
            source=entry.source,
            created_at=entry.created_at,
        )
        for entry in entries
    ]


@router.get("/workspaces", response_model=list[AdminWorkspaceResponse])
def search_workspaces(
    db: Database, admin: AdminUser, email: str
) -> list[AdminWorkspaceResponse]:
    del admin
    normalized = email.strip().lower()
    rows = db.execute(
        select(Workspace, User.email)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .join(User, User.id == WorkspaceMembership.user_id)
        .where(func.lower(User.email) == normalized)
    ).all()

    results: list[AdminWorkspaceResponse] = []
    for workspace, member_email in rows:
        startup_count = (
            db.scalar(
                select(func.count())
                .select_from(Startup)
                .where(Startup.workspace_id == workspace.id)
            )
            or 0
        )
        results.append(
            AdminWorkspaceResponse(
                id=workspace.id,
                plan=workspace.plan,
                created_at=workspace.created_at,
                startup_count=startup_count,
                member_email=member_email,
            )
        )
    return results


@router.post("/workspaces/{workspace_id}/plan", response_model=AdminPlanUpdateResponse)
def update_workspace_plan(
    workspace_id: str,
    payload: AdminPlanUpdateRequest,
    db: Database,
    admin: AdminUser,
) -> AdminPlanUpdateResponse:
    try:
        set_workspace_plan(
            db, workspace_id=workspace_id, plan=payload.plan, actor_id=admin.id
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workspace_not_found") from exc
    db.commit()
    return AdminPlanUpdateResponse(id=workspace_id, plan=payload.plan.value)
