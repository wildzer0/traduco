# Changelog

All notable changes are documented here. Format based on Keep a Changelog; versioning follows SemVer
(0.x until the first stable release). Each completed milestone gets an annotated tag.

## [Unreleased]

## [0.3.1] - 2026-11-07

Milestone M2b - project skeleton.

### Added
- `scheletro.yaml`: chapters and sections a document must contain, with mandatory flag and guide text; errors name the line.
- New project from a bundled skeleton (an abbreviated ECSS-style requirements specification) or from your own file.
- Conformity panel in the sidebar and amber dots in the tree for empty, missing, misplaced or out-of-order sections; "create missing sections" button.

## [0.3.0] - 2026-11-07

Milestone M2 - translation engine.

### Added
- Segmentation of sections (titles, paragraphs, list items, table cells, quotes, footnotes, front matter title) with stable keys and hashes;
  code, Mermaid and raw HTML are never sent to the model. Placeholders protect links, images, inline code, URLs, `{{fields}}` and emphasis.
- Assembler that rebuilds the translated Markdown without touching anything else; property tests prove identity translation gives the same file and HTML.
- OpenAI-compatible client (timeout, retry, cancellation), priority queue that drops superseded requests, validation with one corrective retry.
- Translation saved on every section save, stored in `.traduco/segmenti/<lang>/...json`; only changed paragraphs are retranslated, moved ones keep theirs.
- Translated preview with per-segment state, model indicator, offline banner, retranslation of section/chapter/project, `Ctrl+Shift+P` to see the source.
- Planning docs: project skeleton from a config file (RF-09), issues/change table/review comments/software-doc templates/export formats (RF-80..85), custom snippets (RF-86).

## [0.2.0] - 2026-11-07

Milestone M1 - workspace and editor.

### Added
- Welcome page, projects under `~/Traduco`, chapter/section tree with drag and drop, inline rename, context menu and trash.
- Two-mode editor on the same file (Document with Milkdown, Markdown with CodeMirror), canonical Markdown on save, 1 s autosave,
  toolbar, `/` menu, image paste/drop/upload into `img/`, switch with `Ctrl+/` keeping the position.
- External changes pushed over a WebSocket; reload or "keep mine" when they clash with unsaved typing.
- Source preview (markdown-it, raw HTML escaped) aligned with the editor; Mermaid diagrams drawn in the browser and cached as SVG/PNG.

### Fixed
- Real servers now accept WebSockets (`websockets` dependency).

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
