from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine: Engine | None = (
    create_engine(settings.database_url, pool_pre_ping=True) if settings.database_url else None
)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False) if engine is not None else None


def get_db() -> Iterator[Session]:
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL is not configured")
    with SessionLocal() as session:
        yield session
