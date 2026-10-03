"""Admin script: set a workspace's commercial plan tier.

Usage:
    .venv/Scripts/python.exe scripts/set_plan.py --workspace-id <id> --plan consultor

Opens a direct DB session against DATABASE_URL (same engine app startup uses),
calls the audited `set_workspace_plan` setter, and commits.
"""

from __future__ import annotations

import argparse
import sys

from app.core.entitlements import PlanTier, set_workspace_plan
from app.db.base import SessionLocal


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace-id", required=True, help="Workspace UUID")
    parser.add_argument(
        "--plan", required=True, choices=[tier.value for tier in PlanTier], help="New plan tier"
    )
    args = parser.parse_args(argv)

    if SessionLocal is None:
        print("DATABASE_URL is not configured", file=sys.stderr)
        return 1

    plan = PlanTier(args.plan)
    with SessionLocal() as db:
        try:
            set_workspace_plan(
                db, workspace_id=args.workspace_id, plan=plan, actor_id=None
            )
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        db.commit()

    print(f"workspace {args.workspace_id} set to plan {plan.value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
