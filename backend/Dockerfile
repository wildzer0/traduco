# syntax=docker/dockerfile:1
# Build context is the repository root:  docker build -f backend/Dockerfile .
# Debian 13 (trixie) is required: LibreOffice >= 24 (RF-79) is not available in older releases.

FROM node:24-slim AS frontend
WORKDIR /src/frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.12-slim-trixie AS runtime
ARG TARGETARCH
ARG PANDOC_VERSION=3.13
ARG PANDOC_SHA256_AMD64=38aa33b325a2bc96a4c39409631212db55702f564250bcdbead180b3bf646389
ARG PANDOC_SHA256_ARM64=21e1d4ba09bd0b334590d204580fd4f6629b21be4ab6a32b26cc98982e9e0c68
ENV PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

# LibreOffice and fonts come from Debian; Pandoc >= 3.5 is not packaged, so it is downloaded and
# verified (same version and hashes as launcher/manifest.toml). Both run only as external processes.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates curl libreoffice-writer-nogui fonts-liberation fonts-dejavu-core \
 && case "$TARGETARCH" in \
      amd64) SHA="$PANDOC_SHA256_AMD64" ;; \
      arm64) SHA="$PANDOC_SHA256_ARM64" ;; \
      *) echo "unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac \
 && curl -fsSL -o /tmp/pandoc.tgz \
      "https://github.com/jgm/pandoc/releases/download/${PANDOC_VERSION}/pandoc-${PANDOC_VERSION}-linux-${TARGETARCH}.tar.gz" \
 && echo "${SHA}  /tmp/pandoc.tgz" | sha256sum -c - \
 && tar -xzf /tmp/pandoc.tgz -C /usr/local --strip-components=1 \
 && rm /tmp/pandoc.tgz \
 && apt-get purge -y curl && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.13.4 /uv /usr/local/bin/uv

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/app ./app
RUN uv sync --frozen --no-dev
COPY --from=frontend /src/frontend/dist /app/frontend/dist

RUN useradd --create-home --uid 10001 traduco && mkdir /workspaces && chown traduco /workspaces
USER traduco
ENV TRADUCO_FRONTEND_DIST=/app/frontend/dist TRADUCO_WORKSPACES_DIR=/workspaces \
    PATH="/app/backend/.venv/bin:$PATH"
VOLUME /workspaces
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status == 200 else 1)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
