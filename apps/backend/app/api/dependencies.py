from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.services.auth import SESSION_COOKIE, CurrentActor, authenticate

Database = Annotated[Session, Depends(get_db)]


def get_current_actor(
    db: Database,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> CurrentActor:
    if session_token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "authentication_required")
    actor = authenticate(db, session_token)
    if actor is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_or_expired_session")
    return actor


Actor = Annotated[CurrentActor, Depends(get_current_actor)]
