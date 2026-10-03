"""Admin script: grant or revoke a user's platform admin flag.

Usage:
    .venv/Scripts/python.exe scripts/set_admin.py --email user@example.com --grant
    .venv/Scripts/python.exe scripts/set_admin.py --email user@example.com --revoke

Opens a direct DB session against DATABASE_URL (same engine app startup
uses), flips ``User.is_platform_admin``, records an audited
``user.admin_changed`` event, and commits. This is the only path, HTTP or
otherwise, that can set the flag.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.db.base import SessionLocal
from app.db.models import User
from app.services.audit import record_event


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True, help="User email")
    toggle = parser.add_mutually_exclusive_group(required=True)
    toggle.add_argument("--grant", action="store_true", help="Grant platform admin")
    toggle.add_argument("--revoke", action="store_true", help="Revoke platform admin")
    args = parser.parse_args(argv)

    if SessionLocal is None:
        print("DATABASE_URL is not configured", file=sys.stderr)
        return 1

    granted = bool(args.grant)
    # Signup stores emails stripped and lower-cased; match that normalization.
    email = args.email.strip().lower()

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"user not found: {email}", file=sys.stderr)
            return 1
        user.is_platform_admin = granted
        db.flush()
        record_event(
            db,
            action="user.admin_changed",
            resource_type="user",
            workspace_id=None,
            actor_id=None,
            resource_id=user.id,
            metadata={"granted": granted},
        )
        db.commit()

    print(f"user {email} admin flag set to {granted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
