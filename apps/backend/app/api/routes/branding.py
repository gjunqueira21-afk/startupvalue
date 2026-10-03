"""Per-workspace report branding (white label) storage and API.

Gated behind the ``white_label`` entitlement (Consultor/Escritorio plans) and
restricted to owner/admin roles. The logo upload endpoint reads the raw
request body instead of a multipart ``UploadFile`` because
``python-multipart`` is not in the locked dependency set for this backend;
see the Task 8 report for the rationale. Validation never trusts the
client-supplied ``Content-Type`` header — the magic bytes of the body are
the only source of truth for the logo's format.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import Field, field_validator
from sqlalchemy import select

from app.api.dependencies import Actor, Database
from app.api.schemas import ApiModel
from app.core.entitlements import workspace_entitlements
from app.db.models import ReportBranding, Role
from app.services.audit import record_event

router = APIRouter(prefix="/api/v1/workspace", tags=["branding"])

MAX_LOGO_BYTES = 1_048_576
_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_MEDIA_TYPE_BY_MAGIC = ((_PNG_MAGIC, "image/png"), (_JPEG_MAGIC, "image/jpeg"))


class BrandingUpdateRequest(ApiModel):
    firm_name: str | None = Field(default=None, max_length=120)
    primary_color: str | None = Field(default=None, max_length=7)
    footer_text: str | None = Field(default=None, max_length=300)

    @field_validator("firm_name", "footer_text")
    @classmethod
    def _trim_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("primary_color")
    @classmethod
    def _validate_hex_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not _HEX_COLOR_RE.match(trimmed):
            raise ValueError("invalid_primary_color")
        return trimmed


class BrandingResponse(ApiModel):
    firm_name: str | None
    primary_color: str | None
    footer_text: str | None
    has_logo: bool


def _authorize(db: Database, actor: Actor) -> None:
    """Owner/admin role AND the ``white_label`` entitlement, or 403."""
    if actor.role not in {Role.owner, Role.admin}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "action_not_allowed")
    ent = workspace_entitlements(db, actor.workspace_id)
    if not ent.white_label:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "white_label_not_in_plan")


def _get_branding(db: Database, workspace_id: str) -> ReportBranding | None:
    return db.scalar(select(ReportBranding).where(ReportBranding.workspace_id == workspace_id))


def _to_response(branding: ReportBranding | None) -> BrandingResponse:
    if branding is None:
        return BrandingResponse(
            firm_name=None, primary_color=None, footer_text=None, has_logo=False
        )
    return BrandingResponse(
        firm_name=branding.firm_name,
        primary_color=branding.primary_color,
        footer_text=branding.footer_text,
        has_logo=branding.logo_bytes is not None,
    )


@router.get("/branding", response_model=BrandingResponse)
def get_branding(db: Database, actor: Actor) -> BrandingResponse:
    _authorize(db, actor)
    return _to_response(_get_branding(db, actor.workspace_id))


@router.put("/branding", response_model=BrandingResponse)
def update_branding(
    payload: BrandingUpdateRequest, db: Database, actor: Actor
) -> BrandingResponse:
    _authorize(db, actor)
    branding = _get_branding(db, actor.workspace_id)
    if branding is None:
        branding = ReportBranding(workspace_id=actor.workspace_id)
        db.add(branding)
    branding.firm_name = payload.firm_name
    branding.primary_color = payload.primary_color
    branding.footer_text = payload.footer_text
    db.flush()
    record_event(
        db,
        action="branding.updated",
        resource_type="workspace",
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        resource_id=actor.workspace_id,
        metadata={
            "firm_name_set": branding.firm_name is not None,
            "primary_color_set": branding.primary_color is not None,
            "footer_text_set": branding.footer_text is not None,
        },
    )
    db.commit()
    db.refresh(branding)
    return _to_response(branding)


async def _read_bounded_body(request: Request) -> bytes:
    """Stream the request body, aborting with 413 before buffering past the cap.

    Never materializes more than ``MAX_LOGO_BYTES`` plus one in-flight chunk in
    memory, unlike ``await request.body()`` which fully buffers first and
    checks size second.
    """
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_LOGO_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "logo_too_large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/branding/logo", response_model=BrandingResponse)
async def upload_logo(request: Request, db: Database, actor: Actor) -> BrandingResponse:
    _authorize(db, actor)
    body = await _read_bounded_body(request)
    media_type = next(
        (mt for magic, mt in _MEDIA_TYPE_BY_MAGIC if body.startswith(magic)), None
    )
    if media_type is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "logo_format_unsupported")
    branding = _get_branding(db, actor.workspace_id)
    if branding is None:
        branding = ReportBranding(workspace_id=actor.workspace_id)
        db.add(branding)
    branding.logo_bytes = body
    branding.logo_media_type = media_type
    db.flush()
    record_event(
        db,
        action="branding.updated",
        resource_type="workspace",
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        resource_id=actor.workspace_id,
        metadata={"logo_media_type": media_type, "logo_bytes_size": len(body)},
    )
    db.commit()
    db.refresh(branding)
    return _to_response(branding)


@router.delete("/branding/logo", response_model=BrandingResponse)
def delete_logo(db: Database, actor: Actor) -> BrandingResponse:
    _authorize(db, actor)
    branding = _get_branding(db, actor.workspace_id)
    if branding is not None:
        branding.logo_bytes = None
        branding.logo_media_type = None
        db.flush()
    record_event(
        db,
        action="branding.updated",
        resource_type="workspace",
        workspace_id=actor.workspace_id,
        actor_id=actor.user_id,
        resource_id=actor.workspace_id,
        metadata={"logo_cleared": True},
    )
    db.commit()
    if branding is not None:
        db.refresh(branding)
    return _to_response(branding)
