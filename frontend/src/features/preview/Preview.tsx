import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import { useEditorStatus } from "../../lib/editor-status";
import { useT } from "../../lib/i18n";
import { createRenderer } from "../../lib/markdown/render";
import { usePrefs } from "../../lib/prefs";
import { usePreview } from "../../lib/preview-store";
import { parseDocument } from "../editor/markdown-io";
import { cacheDiagram, type DiagramTheme, renderDiagram, sha256Hex } from "./diagrams";

const svgCache = new Map<string, string>();

function useDiagramTheme(): DiagramTheme {
  const theme = usePrefs((s) => s.theme);
  const dark = window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;
  return theme === "dark" || (theme === "system" && dark) ? "dark" : "default";
}

/** Rendered source of the open section, aligned with the editor (docs/03-ui.md). */
export function Preview({ projectId }: { projectId: string }) {
  const t = useT();
  const { path, text, topBlock } = usePreview();
  const saved = useEditorStatus((s) => s.save) === "saved";
  const theme = useDiagramTheme();
  const scroller = useRef<HTMLDivElement>(null);
  const article = useRef<HTMLElement>(null);

  const render = useMemo(
    () => (path ? createRenderer({ projectId, sectionPath: path }) : null),
    [projectId, path],
  );
  const html = useMemo(() => (render ? render(parseDocument(text).body) : ""), [render, text]);

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
          if (el.isConnected) {
            el.dataset.state = "error";
            const message = e instanceof Error ? e.message : String(e);
            el.setAttribute("title", t("preview.diagramError", { message }));
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
    <section aria-label={t("preview.label")} className="flex min-w-0 flex-1 flex-col">
      <div className="flex h-10 shrink-0 items-center border-b border-border px-3 text-muted">
        {t("preview.sourceTitle")}
      </div>
      <div ref={scroller} className="editor-scroll relative min-h-0 flex-1 overflow-y-auto">
        {path ? (
          <article
            ref={article}
            className="preview-body mx-auto box-border max-w-[calc(72ch+48px)] p-6"
            // biome-ignore lint/security/noDangerouslySetInnerHtml: markdown-it with raw HTML disabled and validated links
            dangerouslySetInnerHTML={{ __html: html }}
          />
        ) : (
          <p className="p-6 text-muted">{t("preview.empty")}</p>
        )}
      </div>
    </section>
  );
}
