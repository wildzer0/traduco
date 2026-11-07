import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { Languages, RefreshCw } from "lucide-react";
import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { retranslate } from "../../lib/api";
import { useCapabilities } from "../../lib/capabilities";
import { useEditorStatus } from "../../lib/editor-status";
import { useT } from "../../lib/i18n";
import { createRenderer } from "../../lib/markdown/render";
import { useNotices } from "../../lib/notices";
import { usePrefs } from "../../lib/prefs";
import { usePreview } from "../../lib/preview-store";
import { useTranslationState } from "../../lib/translation-store";
import { useView } from "../../lib/view-store";
import { parseDocument } from "../editor/markdown-io";
import {
  cacheDiagram,
  DiagramEngineError,
  type DiagramTheme,
  renderDiagram,
  sha256Hex,
} from "./diagrams";
import { LanguageMenu } from "./LanguageMenu";
import { SectionSettings } from "./SectionSettings";
import { SegmentOverlay } from "./SegmentOverlay";
import { useTranslation } from "./translation";

const svgCache = new Map<string, string>();

function useDiagramTheme(): DiagramTheme {
  const theme = usePrefs((s) => s.theme);
  const dark = window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  return theme === "dark" || (theme === "system" && dark) ? "dark" : "default";
}

/** Rendered source of the open section, aligned with the editor (docs/03-ui.md). */
export function Preview({ projectId }: { projectId: string }) {
  const t = useT();
  const { path, text, topBlock, mode, setMode } = usePreview();
  const locale = usePrefs((s) => s.locale);
  const online = useTranslationState((s) => s.online);
  const downloading = useCapabilities().data?.model.state === "downloading";
  const translation = useTranslation(projectId, path).data;
  // a section that was just opened has no status yet: its diagrams still need caching for the export
  const status = useEditorStatus((s) => s.save);
  const saved = status === "saved" || status === null;
  const theme = useDiagramTheme();
  const scroller = useRef<HTMLDivElement>(null);
  const article = useRef<HTMLElement>(null);

  const render = useMemo(
    () => (path ? createRenderer({ projectId, sectionPath: path }) : null),
    [projectId, path],
  );
  const shown = mode === "translated" && translation ? translation.markdown : text;
  const html = useMemo(() => (render ? render(parseDocument(shown).body) : ""), [render, shown]);
  const language = new Intl.DisplayNames([locale], { type: "language" }).of(
    translation?.lang ?? "en",
  );

  // Mark each segment with its state (queued, needs review, approved…).
  // biome-ignore lint/correctness/useExhaustiveDependencies: html changes whenever the blocks change
  useLayoutEffect(() => {
    const root = article.current;
    if (!root) return;
    for (const el of root.querySelectorAll<HTMLElement>("[data-seg]"))
      el.removeAttribute("data-status");
    if (mode !== "translated" || !translation) return;
    for (const seg of translation.segments) {
      if (seg.status === "translated") continue;
      const el = root.querySelector<HTMLElement>(`[data-seg="${seg.key}"]`);
      if (!el) continue;
      el.dataset.status = seg.status;
      el.title = seg.reason
        ? `${t(`preview.status.${seg.status}`)}: ${seg.reason}`
        : t(`preview.status.${seg.status}`);
    }
  }, [html, translation, mode, t]);

  // Diagrams: draw from cache at once, render the rest in the background.
  // biome-ignore lint/correctness/useExhaustiveDependencies: html changes whenever the blocks change
  useLayoutEffect(() => {
    const root = article.current;
    if (!root) return;
    for (const el of root.querySelectorAll<HTMLElement>(".mermaid-block")) {
      const code = el.dataset.code ?? "";
      void sha256Hex(code).then(async (hash) => {
        const key = `${theme}:${hash}`;
        const show = (svg: string) => {
          if (el.isConnected && el.dataset.code === code) el.innerHTML = svg;
        };
        const cached = svgCache.get(key);
        if (cached) return show(cached);
        try {
          const svg = await renderDiagram(code, theme);
          svgCache.set(key, svg);
          show(svg);
        } catch (e) {
          if (!el.isConnected) return;
          const engine = e instanceof DiagramEngineError;
          const message = engine
            ? t("preview.diagramEngine")
            : t("preview.diagramError", { message: e instanceof Error ? e.message : String(e) });
          el.dataset.state = "error";
          el.setAttribute("title", message);
          if (!el.querySelector(".mermaid-error")) {
            const note = document.createElement("p");
            note.className = "mermaid-error";
            note.textContent = message.split("\n")[0] ?? message;
            el.append(note);
          }
        }
      });
    }
  }, [html, theme, t]);

  // Cache the light rendering for the export once the section is safely on disk.
  // biome-ignore lint/correctness/useExhaustiveDependencies: html changes whenever the blocks change
  useEffect(() => {
    if (!saved || !article.current) return;
    for (const el of article.current.querySelectorAll<HTMLElement>(".mermaid-block")) {
      const code = el.dataset.code ?? "";
      void sha256Hex(code).then((hash) => cacheDiagram(projectId, hash, code));
    }
  }, [saved, html, projectId]);

  // Jump to a segment asked for by F8 or the review table, and flash it.
  const focusKey = useView((s) => s.focusKey);
  const setFocusKey = useView((s) => s.setFocusKey);
  // biome-ignore lint/correctness/useExhaustiveDependencies: html changes whenever the blocks change
  useEffect(() => {
    if (!focusKey || !article.current) return;
    const el = article.current.querySelector<HTMLElement>(`[data-seg="${CSS.escape(focusKey)}"]`);
    if (!el) return;
    el.scrollIntoView?.({ block: "center" });
    el.classList.add("seg-flash");
    const timer = setTimeout(() => el.classList.remove("seg-flash"), 1600);
    setFocusKey(null);
    return () => clearTimeout(timer);
  }, [focusKey, html, setFocusKey]);

  // Keep the block at the top of the editor at the top of the preview.
  // biome-ignore lint/correctness/useExhaustiveDependencies: realign after the content is re-rendered
  useEffect(() => {
    const box = scroller.current;
    if (!box) return;
    const target = box.querySelector<HTMLElement>(`[data-block="${topBlock}"]`);
    if (target) box.scrollTop = target.offsetTop - box.offsetTop;
    else if (topBlock === 0) box.scrollTop = 0;
  }, [topBlock, html]);

  return (
    <section aria-label={t("preview.label")} className="relative flex min-w-0 flex-1 flex-col">
      <div className="flex h-10 shrink-0 items-center gap-2 border-b border-border px-3 text-muted">
        <span className="truncate">
          {mode === "translated"
            ? t("preview.translatedTitle", { language: language ?? "" })
            : t("preview.sourceTitle")}
        </span>
        <div className="ml-auto flex items-center gap-1">
          <LanguageMenu projectId={projectId} />
          <button
            type="button"
            aria-pressed={mode === "source"}
            title={`${t(mode === "source" ? "preview.showTranslation" : "preview.showSource")} (Ctrl+Shift+P)`}
            onClick={() => setMode(mode === "source" ? "translated" : "source")}
            className="flex h-7 items-center gap-1 rounded-ui px-2 hover:bg-surface-2 hover:text-fg"
          >
            <Languages size={14} strokeWidth={1.5} aria-hidden />
            {t(mode === "source" ? "preview.showTranslation" : "preview.showSource")}
          </button>
          {path && translation && (
            <SectionSettings projectId={projectId} path={path} view={translation} />
          )}
          <RetranslateMenu projectId={projectId} path={path} />
        </div>
      </div>
      {online === false && (
        <p
          role="status"
          className="border-b border-border bg-surface-2 px-3 py-1.5 text-[13px] text-amber"
        >
          {downloading ? (
            t("preview.offlineDownloading")
          ) : (
            <>
              {t("preview.offline")}{" "}
              <button
                type="button"
                onClick={() => usePrefs.getState().setSettingsOpen(true)}
                className="underline underline-offset-2"
              >
                {t("preview.offlineSettings")}
              </button>
            </>
          )}
        </p>
      )}
      <div ref={scroller} className="editor-scroll relative min-h-0 flex-1 overflow-y-auto">
        {path ? (
          <SegmentOverlay
            enabled={mode === "translated" && translation !== undefined}
            projectId={projectId}
            path={path}
            view={translation}
            article={article}
            html={html}
          >
            <article
              ref={article}
              className="preview-body box-border p-6"
              // biome-ignore lint/security/noDangerouslySetInnerHtml: markdown-it with raw HTML disabled and validated links
              dangerouslySetInnerHTML={{ __html: html }}
            />
          </SegmentOverlay>
        ) : (
          <p className="p-6 text-muted">{t("preview.empty")}</p>
        )}
      </div>
    </section>
  );
}

function RetranslateMenu({ projectId, path }: { projectId: string; path: string | null }) {
  const t = useT();
  const run = async (scope: "section" | "chapter" | "project") => {
    if (!path && scope !== "project") return;
    const target =
      scope === "chapter" ? path?.split("/").slice(0, -1).join("/") : (path ?? undefined);
    try {
      await retranslate(projectId, scope, target);
    } catch (e) {
      useNotices.getState().show(e instanceof Error ? e.message : String(e));
    }
  };
  const item =
    "cursor-default rounded-ui px-2 py-1 outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-fg";
  return (
    <Dropdown.Root>
      <Dropdown.Trigger
        title={t("preview.retranslate")}
        className="flex h-7 items-center gap-1 rounded-ui px-2 hover:bg-surface-2 hover:text-fg"
      >
        <RefreshCw size={14} strokeWidth={1.5} aria-hidden />
        {t("preview.retranslate")}
      </Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content
          align="end"
          sideOffset={4}
          className="z-20 min-w-44 rounded-ui border border-border bg-surface p-1 shadow-lg"
        >
          <Dropdown.Item className={item} disabled={!path} onSelect={() => void run("section")}>
            {t("preview.retranslateSection")}
          </Dropdown.Item>
          <Dropdown.Item className={item} disabled={!path} onSelect={() => void run("chapter")}>
            {t("preview.retranslateChapter")}
          </Dropdown.Item>
          <Dropdown.Item className={item} onSelect={() => void run("project")}>
            {t("preview.retranslateProject")}
          </Dropdown.Item>
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
}
