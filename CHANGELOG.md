# Changelog

All notable changes are documented here. Format based on Keep a Changelog; versioning follows SemVer
(0.x until the first stable release). Each completed milestone gets an annotated tag.

## [Unreleased]

## [0.1.1] - 2026-11-07

### Fixed
- `start.cmd` no longer breaks when started from PowerShell 7 (module path of Windows PowerShell 5.1).
- Launcher test no longer depends on `UV_CACHE_DIR`; CI is green on Ubuntu and Windows.

### Added (M1, in progress)
- Workspace core (front matter, ordering, tree, operations, images), REST API with conflict detection,
  file-change WebSocket, canonical Markdown form with shared golden fixtures.

## [0.1.0] - 2026-11-07

Milestone M0 - foundations.

### Added
- Backend (FastAPI, pydantic-settings, `/api/health`), frontend shell (React 19, Vite, Tailwind 4, i18n it/en, light/dark theme).
- `tools/fake-llm` deterministic OpenAI-compatible server; `tools/check-licenses.py`.
- One-command launcher (`start.sh`, `start.cmd`) with verified resumable downloads and a pinned `manifest.toml`.
- Dockerfile and Compose (optional Ollama profile), GitHub Actions CI including clean-start jobs on Ubuntu and Windows.
- Demo workspace `examples/progetto-esempio`.
