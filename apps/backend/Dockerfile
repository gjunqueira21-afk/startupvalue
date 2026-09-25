# syntax=docker/dockerfile:1.7
FROM python:3.12.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

RUN python -m venv /opt/venv \
    && addgroup --system --gid 10001 startupvalue \
    && adduser --system --uid 10001 --ingroup startupvalue --home /nonexistent --no-create-home startupvalue

# Dependencies come from the resolved lockfile, never from a fresh resolution of
# pyproject.toml, so an image built today matches one built months from now.
# Regenerate with: uv lock && uv export (see README, "Dependency locking").
COPY pyproject.toml requirements.lock.txt ./
RUN pip install --require-hashes --no-deps -r requirements.lock.txt

COPY --chown=startupvalue:startupvalue app ./app
COPY --chown=startupvalue:startupvalue alembic.ini ./alembic.ini
COPY --chown=startupvalue:startupvalue alembic ./alembic
RUN mkdir -p /data/reports /data/samples \
    && chown -R startupvalue:startupvalue /app /data

USER 10001:10001
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
