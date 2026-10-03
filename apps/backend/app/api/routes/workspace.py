from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.dependencies import Actor, Database
from app.core.entitlements import Entitlements, entitlements_for
from app.db.models import Workspace

router = APIRouter(prefix="/api/v1/workspace", tags=["workspace"])


@router.get("/entitlements")
def get_entitlements(db: Database, actor: Actor) -> dict[str, object]:
    workspace = db.get(Workspace, actor.workspace_id)
    if workspace is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "workspace_not_found")
    entitlements: Entitlements = entitlements_for(workspace.plan)
    return {
        "plan": entitlements.plan.value,
        "max_startups": entitlements.max_startups,
        "max_scenarios_per_run": entitlements.max_scenarios_per_run,
        "white_label": entitlements.white_label,
        "full_report": entitlements.full_report,
        "target_plan_section": entitlements.target_plan_section,
        "implied_multiples": entitlements.implied_multiples,
    }
