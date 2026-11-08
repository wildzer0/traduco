# Changelog

All notable changes are documented here. Format based on Keep a Changelog; versioning follows SemVer
(0.x until the first stable release). Each completed milestone gets an annotated tag.

## [Unreleased]

## [0.15.0] - 2026-11-08

Visual refresh: professional, minimal, calm.

### Changed
- New mark (a T whose bar is split in two: the text and its translation) and a larger "Traduco" name; new icon.
- Neutral palette with one accent colour, soft borders and shadows, 14 px text; the same tokens in light and dark.
- Top bar: one primary action (Export), icon-only secondary buttons, a soft segmented control for the view.
- Sidebar and lists: the open section is marked with a tinted background, icons on the secondary links, wider default sidebar.
- Editor on a white page, preview on the background; preview and editor toolbars no longer wrap.
- Projects page: centred column, the list in a card.

## [0.14.1] - 2026-11-08

### Changed
- Top bar: the back button and the panel buttons are icons (their names are in the tooltip), the project name no longer touches the app name.
- Review table: fixed column widths, so the actions are never cut off.
- Glossary: the CSV and TBX links say "Export as".

## [0.14.0] - 2026-11-08

### Added
- Attachments: a CSV file attached from the editor is shown as a table in the preview and in the export; other files are stored in `allegati/` and linked.
- The sidebar numbers the chapters and sections when the project's template has a table of contents.
- Checks before exporting: empty sections, broken links, missing images and attachments, remote images, translations still to review.
- "DRAFT" watermark (in the language of the document) while something is not approved; it can be turned off in the export panel.
- Versions of a section: the text before each writing session is kept (at most one every five minutes, 40 per section) and can be read and restored.
- A project can be copied as a model: titles, glossary, template and settings, without the texts.
- `tools/dev-idp.py`: a login server to try team mode without Keycloak.

## [0.13.0] - 2026-11-08

Milestone M7 - team mode (partial: single process).

### Added
- Team mode (`TRADUCO_MODE=team`): OIDC login (Keycloak in the compose profile `team`), signed sessions, roles author / reviewer / administrator and a permission for every route.
- Soft section locks and presence: whoever edits a section holds it, the others see it read-only with the name; the lock expires by itself.
- Append-only audit log (approvals with their author, exports, imports, issues, project copies and deletions), read by the administrator at `GET /api/audit`.
- Login gate, user menu and people in the project in the top bar.
- `docs/team.md`, ADR-046.

### Not done
- PostgreSQL and Valkey implementations of the store and the job queue; locks and presence live in the memory of one process.
- The `team` profile has not been tried with real Keycloak and vLLM.

## [0.12.0] - 2026-11-08

Interface rework and fixes from the first real export.

### Added
- Projects page with nested folders, search, details (issue, author, last change), duplicate and a reversible trash.
- Resizable sidebar, preview and panels; panels keep their title and close button in view; a way back to all projects.
- Logo and icon.
- Sidebar: automatic folding of the chapters that do not hold the open section (button and Alt+Shift+F).
- Team mode, first slice: OIDC login, signed sessions, roles and a permission for every route (M7).
- The table of contents in a Word export already lists the headings (no page numbers until Word updates the field).

### Fixed
- A table that follows a paragraph without a blank line was exported to Word as loose text with the cells scattered in the document.
- Export no longer asks to open the sections with diagrams first: the diagrams are drawn by the export itself.
- The description of each revision is translated in the official-language export.
- The model status is not "online" while the model is still downloading.

## [0.11.1] - 2026-11-08

Fixes from the first run with the real model, pivot languages and end-to-end tests of the new panels.

### Added
- An additional language can translate from the approved official translation instead of the source (pivot); it waits for each segment to be approved.
- The review table follows the language chosen in the preview.
- `tools/make-big-project.py` (a large realistic manual to try a model on), `tools/benchmark-translation.py` (speed and quality report) and `docs/prova-gemma.md`.
- End-to-end tests for the palette, search, requirements, snippets, comments, issues, languages and translation memory.

### Fixed
- With the real model, bold text was often translated without its markers and the segment was left empty ("**Attenzione.** …" every time). The markers are put back where the place is certain, and otherwise the translation is kept and reported as having lost its formatting.
- The glossary did not recognise a plural in the first words of a term ("valvole di intercettazione"), so imposed and forbidden terms were not checked there.
- The instruction box no longer offers a "proposal" that is the current text.

## [0.11.0] - 2026-11-07

Milestone M6 - quality and polish.

### Added
- Command palette (`Ctrl/Cmd+K`), search in the text of the project (`Ctrl/Cmd+Shift+F`), shortcut list (`?`) and `Alt+Up/Down` between sections.
- Translation memory: approved or hand-written translations are reused for the same sentence, similar ones are suggested; TMX import and export.
- Glossary import and export as CSV and TBX (merging, never overwriting).
- Additional target languages, translated from the source in the background after the official one, each with its own tone and date format; language menu with progress, and export in any of them.
- Two-column export (source | translation).
- Visual table editing (rows, columns, alignment) in both editor modes.
- Optional spelling and grammar check of the source with your own LanguageTool server.
- User guide (`docs/guida-utente.md`) and a 300-section performance test.

### Fixed
- The text cursor was black in the Markdown editor and could not be seen on the dark theme.
- Uploading a template right after opening the Templates panel could leave the list empty.

## [0.10.1] - 2026-11-07

### Fixed
- The "Istruzione" box (and the writing assistant's free instruction) no longer writes whatever it is asked: it only rewrites. A request for new content, such as a recipe in a technical manual, is refused with a clear message and nothing changes.
- After using a rewritten translation from the "Istruzione" box, the preview now warns that the source no longer matches and offers to update it, as it already did after a manual edit.
- Emphasis that crossed another protected span (`_:*_*`) broke the placeholders of a segment.

## [0.10.0] - 2026-11-07

Milestone: built-in engine (llama.cpp) as an alternative to Ollama.

### Added
- Built-in engine: without Ollama, or without administrator rights, Traduco can run llama.cpp's `llama-server` with Gemma 4 E2B/E4B by itself (`--llm builtin`; offered automatically when Ollama is missing). Nothing to install: a small program and the model are downloaded and checked, the server listens on this computer only and is protected by a random key.

### Changed
- The "no model" message in the interface now says how to get one without Ollama.

## [0.9.0] - 2026-11-07

Milestone M5c - software documents, other formats, snippets.

### Added
- Document models for software: requirements specification (SRS), architectural design (ADD) and detailed design (DDD).
- "Requirements" panel: identifiers such as FOO-REQ-00042 are defined at the start of a paragraph and cross-references are checked (duplicates, undefined, never referenced).
- Export as a single self-contained web page (index, search, images included, opens from a file), EPUB and Markdown (a zip when there are images).
- Snippets: `snippet.yaml` with aliases, tab-stops and persistent counters (`{{contatore:REQ}}` gives FOO-REQ-00042, then 00043), in the `/` menu with an editor.

### Fixed
- The identifier inside an exported Word file now matches its snapshot, so a revised file is matched with its own export.

## [0.8.0] - 2026-11-07

Milestone M5b - issues, comparison and review comments.

### Added
- Issues: freeze the document with a number and a date (both languages), browse them, restore a section from one.
- Word-level comparison between two issues or with the draft, in the source or the official language, change by change.
- Change table: the model summarises what changed in each section since the previous issue; correct it and write it into the revision table.
- Review comments on segments with threads and an open/resolved status, stored beside the document and following their segment when the text changes.

## [0.7.0] - 2026-11-07

Milestone M5 - PDF/ODT with updated fields, template wizard, import of revised documents.

### Added
- PDF and ODT export refresh the table of contents and the fields through LibreOffice (a macro run on a freshly initialised throw-away profile).
- "Create a template" in four steps (look, cover, header and footer, contents) with a live sketch and an optional logo.
- Import of a revised Word file: the changes (including Word's tracked changes) become proposals per section, written back in the source language by the model; Accept, Edit or Reject each one. Accepting keeps the client's wording as a locked translation.
- A form for the project's metadata and revision history in the Templates panel.

### Changed
- Exported documents carry an identifier and the export snapshot records every unit, so a revised file is matched with the export it came from.

## [0.6.0] - 2026-11-07

Milestone M4b - complete launcher.

### Added
- First start in nine numbered steps: it checks the computer, installs Pandoc, picks the model for the hardware (RAM, NVIDIA/AMD GPU, Apple Silicon),
  finds, starts or - only if you agree - installs Ollama, and downloads the model **in the background** while you already write.
- The interface shows the model download (progress, failure, or "no Ollama") and translation waits for the model instead of failing; PDF and ODT export when LibreOffice is installed, with a clear message when it is not.
- `/api/capabilities`, options `--yes` and `--prepare-only`, error codes E040-E043 in Italian and English.
- Offline package: `make bundle-offline OS=linux|windows [MODEL=tag]`; CI builds it on Ubuntu and Windows and starts it with `--offline` from another folder.
- Model tags `gemma4:e2b`, `gemma4:e4b`, `gemma4:26b-a4b` checked against the Ollama library.

### Fixed
- Stale pages after an update reported a missing diagram engine as an invalid diagram: `index.html` is never cached, a failed chunk reloads the page once.

### Fixed
- Export no longer fails when the project's default template is not in its `template/` folder (projects made before the export existed): it uses the only template present, or Pandoc's styles, and says so.
- A revisions table placed inside a table cell left the cell without a final paragraph, which Word treats as damaged.

### Added
- "Add the sample template" in the Templates panel.

## [0.5.0] - 2026-11-07

Milestone M4 - templates and DOCX export.

### Added
- Company Word templates (`.docx`): upload, analysis (styles by id and name, `{{fields}}` even when Word splits them, headers, footers and text boxes, `{{CONTENUTO}}`, `{{SOMMARIO}}`, `{{REVISIONI}}`),
  automatic style mapping that you can change, several templates per project with a default.
- DOCX export of a section, a chapter or the whole project, in the official or the source language: cover, header and footer of the template, headings, lists, quotes, code and tables in the template's styles,
  numbered figure captions, footnotes, table of contents, revisions table, fields filled from `progetto.yaml`. Missing translations are completed first. `Ctrl+E` repeats the last export.
- An export stops with a clear message if a Mermaid diagram has not been drawn yet; a snapshot of every export is kept in `.traduco/export/`.
- `make tools` downloads the pinned Pandoc into `.runtime/pandoc` (checksum verified).
- Example project: synthetic company template `manuale.docx` with its style mapping.

### Fixed
- Diagrams are cached as soon as a section is opened, not only after an edit, so an export does not depend on having typed something.

## [0.4.1] - 2026-11-07

Milestone M3b - writing companion.

### Added
- Writing assistant on the source text: correct, rephrase, more concise, simpler, formal/neutral/informal tone, or your own instruction. The proposal is shown as a word-by-word
  difference; the file changes only when you apply it, and only that segment is translated again. Controlled glossary terms, "do not translate" entries, code, links and `{{fields}}` are kept.
- Section check: model remarks (grammar, clarity, ambiguity, style, terminology), coverage of the skeleton guide, and optional requirement rules (one prescription per sentence, weak verbs, vague words) in Italian and English.
- Model settings in the app (server address, model, API key) with "Save and verify"; the "model unreachable" banner links to them. Changes apply without a restart.

### Fixed
- Translation with reasoning models (Gemma 4 on Ollama) returned empty text and stayed "translating": reasoning is switched off and the token budget is larger.
- Jobs and events started from threaded endpoints (retranslate, first open of a section) could wait until something else woke the event loop.

## [0.4.0] - 2026-11-07

Milestone M3 - translation control and glossary.

### Added
- Edit a translation by hand: the segment is locked and survives retranslation of section, chapter or project and tone changes.
  When the source of a locked segment changes, the new machine translation is offered as a proposal (Accept / Ignore).
- Hover bar and context menu on the preview: edit, instruct the model ("more formal", "more concise", "simpler", your own words), three alternatives, lock, approve, retranslate, copy.
- Direct edits can be turned into a proposed update of the source (back-translation, applied only on confirmation).
- Glossary panel (`glossario.yaml`): required translation, forbidden terms, "do not translate", notes; checked after every translation with one corrective retry, then "needs review" with the reason.
- Tone per project and per section, translator note in the section front matter.
- Review mode (`Ctrl+2`): every segment with filters and quick approval; `F8` jumps to the next one to review; focus mode (`Ctrl+3`).

### Fixed
- `GET /tree` no longer fails when a folder is renamed while the tree is being read.

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
