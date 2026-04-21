# syntax=docker/dockerfile:1.7

# ---------- build stage: compile deps with build tools ----------
FROM python:3.12-slim AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# Install into /install so build tools (build-essential, libpq-dev) stay
# in the builder and do NOT reach the runtime image.
RUN pip install --upgrade pip && pip install --prefix=/install -e ".[dev]"

# ---------- runtime stage: minimal, non-root ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/bin:${PATH}" \
    PYTHONPATH="/install/lib/python3.12/site-packages"

RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Unprivileged user + owned directories.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid 10001 --home /app --shell /usr/sbin/nologin app \
    && chown -R app:app /app

# Copy installed deps and project tree from the build stage.
COPY --from=build /install /install
COPY --chown=app:app . .
RUN chmod +x ./entrypoint.sh

USER app

EXPOSE 8000

CMD ["./entrypoint.sh"]
