from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import Actor, Database
from app.api.schemas import (
    RevisionCreate,
    RevisionResponse,
    ScenarioCreate,
    ScenarioResponse,
    StartupCreate,
    StartupResponse,
)
from app.core.entitlements import workspace_entitlements
from app.db.models import Role, Scenario, ScenarioRevision, Startup
from app.repositories.resources import get_scenario, get_startup
from app.services.audit import record_event

router = APIRouter(prefix="/api/v1", tags=["valuation resources"])


def _require_editor(actor: Actor) -> None:
    if actor.role not in {Role.owner, Role.admin, Role.analyst}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "action_not_allowed")


@router.post("/startups", response_model=StartupResponse, status_code=status.HTTP_201_CREATED)
def create_startup(payload: StartupCreate, db: Database, actor: Actor) -> Startup:
    _require_editor(actor)
    ent = workspace_entitlements(db, actor.workspace_id)
    if ent.max_startups is not None:
        existing = db.scalar(
            select(func.count())
            .select_from(Startup)
            .where(Startup.workspace_id == actor.workspace_id)
        )
        if existing >= ent.max_startups:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "plan_limit_startups")
    startup = Startup(
        workspace_id=actor.workspace_id,
        name=payload.name.strip(),
        currency=payload.currency,
        profile=payload.profile,
    )
    db.add(startup)
    db.flush()
    record_event(
        db,
        action="startup.create",
        resource_type="startup",
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        resource_id=startup.id,
    )
    db.commit()
    db.refresh(startup)
    return startup


@router.get("/startups", response_model=list[StartupResponse])
def list_startups(db: Database, actor: Actor) -> list[Startup]:
    return list(
        db.scalars(
            select(Startup)
            .where(
                Startup.workspace_id == actor.workspace_id,
                Startup.archived_at.is_(None),
            )
            .order_by(Startup.created_at.desc())
        )
    )


@router.get("/startups/{startup_id}", response_model=StartupResponse)
def read_startup(startup_id: str, db: Database, actor: Actor) -> Startup:
    startup = get_startup(db, startup_id=startup_id, workspace_id=actor.workspace_id)
    if startup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "startup_not_found")
    return startup


@router.post(
    "/startups/{startup_id}/scenarios",
    response_model=ScenarioResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_scenario(
    startup_id: str, payload: ScenarioCreate, db: Database, actor: Actor
) -> Scenario:
    _require_editor(actor)
    startup = get_startup(db, startup_id=startup_id, workspace_id=actor.workspace_id)
    if startup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "startup_not_found")
    scenario = Scenario(
        workspace_id=actor.workspace_id,
        startup_id=startup.id,
        name=payload.name.strip(),
        mode=payload.mode,
    )
    db.add(scenario)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "scenario_name_already_exists") from exc
    record_event(
        db,
        action="scenario.create",
        resource_type="scenario",
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        resource_id=scenario.id,
    )
    db.commit()
    db.refresh(scenario)
    return scenario


@router.get("/startups/{startup_id}/scenarios", response_model=list[ScenarioResponse])
def list_scenarios(startup_id: str, db: Database, actor: Actor) -> list[Scenario]:
    startup = get_startup(db, startup_id=startup_id, workspace_id=actor.workspace_id)
    if startup is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "startup_not_found")
    return list(
        db.scalars(
            select(Scenario)
            .where(
                Scenario.workspace_id == actor.workspace_id,
                Scenario.startup_id == startup.id,
                Scenario.archived_at.is_(None),
            )
            .order_by(Scenario.created_at.desc())
        )
    )


@router.get("/scenarios/{scenario_id}", response_model=ScenarioResponse)
def read_scenario(scenario_id: str, db: Database, actor: Actor) -> Scenario:
    scenario = get_scenario(db, scenario_id=scenario_id, workspace_id=actor.workspace_id)
    if scenario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "scenario_not_found")
    return scenario


@router.post(
    "/scenarios/{scenario_id}/revisions",
    response_model=RevisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_revision(
    scenario_id: str, payload: RevisionCreate, db: Database, actor: Actor
) -> ScenarioRevision:
    _require_editor(actor)
    scenario = get_scenario(db, scenario_id=scenario_id, workspace_id=actor.workspace_id)
    if scenario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "scenario_not_found")
    canonical = payload.inputs.model_dump(mode="json")
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    revision_no = (
        db.scalar(
            select(func.max(ScenarioRevision.revision_no)).where(
                ScenarioRevision.scenario_id == scenario.id
            )
        )
        or 0
    ) + 1
    revision = ScenarioRevision(
        workspace_id=actor.workspace_id,
        scenario_id=scenario.id,
        revision_no=revision_no,
        canonical_inputs=canonical,
        input_hash=hashlib.sha256(encoded).hexdigest(),
        created_by=actor.user_id,
    )
    db.add(revision)
    db.flush()
    record_event(
        db,
        action="scenario_revision.create",
        resource_type="scenario_revision",
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        resource_id=revision.id,
        metadata={"revision_no": revision_no, "input_hash": revision.input_hash},
    )
    db.commit()
    db.refresh(revision)
    return revision


@router.get("/scenarios/{scenario_id}/revisions", response_model=list[RevisionResponse])
def list_revisions(scenario_id: str, db: Database, actor: Actor) -> list[ScenarioRevision]:
    scenario = get_scenario(db, scenario_id=scenario_id, workspace_id=actor.workspace_id)
    if scenario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "scenario_not_found")
    return list(
        db.scalars(
            select(ScenarioRevision)
            .where(
                ScenarioRevision.workspace_id == actor.workspace_id,
                ScenarioRevision.scenario_id == scenario.id,
            )
            .order_by(ScenarioRevision.revision_no.desc())
        )
    )
