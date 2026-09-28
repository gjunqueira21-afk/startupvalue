"""Password reset token lifecycle and outbound email. Never log raw tokens or URLs."""

from __future__ import annotations

import logging
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from urllib.parse import quote

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.auth.security import hash_password, hash_token, issue_token
from app.core.config import get_settings
from app.db.models import PasswordResetToken, User, UserSession

logger = logging.getLogger(__name__)
RESET_LIFETIME = timedelta(minutes=30)


def delivery_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_from_email and settings.public_app_url)


def issue_reset(db: Session, user: User) -> str:
    now = datetime.now(UTC)
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    token = issue_token()
    db.add(
        PasswordResetToken(
            user_id=user.id,
            token_digest=token.digest,
            expires_at=now + RESET_LIFETIME,
        )
    )
    return token.plain


def send_reset_email(email: str, token: str) -> bool:
    settings = get_settings()
    if not delivery_configured():
        logger.warning("password_reset_delivery_not_configured")
        return False
    assert settings.smtp_host is not None
    assert settings.smtp_from_email is not None
    assert settings.public_app_url is not None
    link = f"{settings.public_app_url.rstrip('/')}/reset-password#token={quote(token)}"
    message = EmailMessage()
    message["From"] = settings.smtp_from_email
    message["To"] = email
    message["Subject"] = "Recuperação de senha — QuantoVale"
    message.set_content(
        "Recebemos uma solicitação para redefinir sua senha.\n\n"
        f"Abra este link em até 30 minutos:\n{link}\n\n"
        "Se você não fez esta solicitação, ignore esta mensagem."
    )
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=8) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        logger.warning("password_reset_delivery_failed")
        return False


def invalidate_reset(db: Session, token: str) -> None:
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.token_digest == hash_token(token))
        .values(used_at=datetime.now(UTC))
    )


def consume_reset(db: Session, token: str, new_password: str) -> User | None:
    now = datetime.now(UTC)
    # Conditional UPDATE makes concurrent redemption single-use, including on PostgreSQL.
    result = db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.token_digest == hash_token(token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(PasswordResetToken.user_id)
    )
    user_id = result.scalar_one_or_none()
    if user_id is None:
        return None
    user = db.get(User, user_id)
    if user is None or user.disabled_at is not None:
        return None
    user.password_hash = hash_password(new_password)
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user.id, UserSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    return user
