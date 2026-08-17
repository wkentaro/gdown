FROM python:3.14-alpine3.24 AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0

WORKDIR /app

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev --no-editable

ARG VERSION="0.0.0"
ENV SETUPTOOLS_SCM_PRETEND_VERSION=${VERSION}

COPY pyproject.toml uv.lock LICENSE README.md ./
COPY gdown/ ./gdown/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable


FROM python:3.14-alpine3.24
LABEL org.opencontainers.image.title="gdown" \
      org.opencontainers.image.description="Google Drive Public File/Folder Downloader" \
      org.opencontainers.image.url="https://github.com/wkentaro/gdown" \
      org.opencontainers.image.source="https://github.com/wkentaro/gdown" \
      org.opencontainers.image.vendor="Kentaro Wada" \
      org.opencontainers.image.licenses="MIT"
ENV PYTHONUNBUFFERED=1

RUN apk add --no-cache ca-certificates \
    && addgroup -g 1000 appuser \
    && adduser -D -u 1000 -G appuser appuser \
    && mkdir /downloads && chown appuser:appuser /downloads \
    && mkdir -p /home/appuser/.cache/gdown \
    && chown -R appuser:appuser /home/appuser/.cache

COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY LICENSE README.md /app/

WORKDIR /downloads

USER appuser

ENV HOME=/home/appuser
ENV PATH="/app/.venv/bin:$PATH"

VOLUME ["/downloads"]

ENTRYPOINT ["gdown"]
