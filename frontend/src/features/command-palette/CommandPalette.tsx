import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useEffect, useMemo, useRef, useState } from "react";
import { importTmx, patchProject, retranslate, searchProject, tmxUrl } from "../../lib/api";
import { fuzzyScore } from "../../lib/fuzzy";
import { type MessageKey, useT } from "../../lib/i18n";
import { useNotices } from "../../lib/notices";
import { usePrefs } from "../../lib/prefs";
import { usePreview } from "../../lib/preview-store";
import type { TreeNode } from "../../lib/types";
import { useView } from "../../lib/view-store";
import { useTree } from "../tree/queries";

interface Item {
  id: string;
  group: "sections" | "actions" | "text";
  label: string;
  hint?: string;
  run: () => void;
}

const sections = (nodes: TreeNode[]): TreeNode[] =>
  nodes.flatMap((n) => (n.kind === "section" ? [n] : sections(n.children)));

/** Ctrl/Cmd+K: sections, actions and the text of the project in one place (docs/03-ui.md). */
export function CommandPalette() {
  const open = useView((s) => s.paletteOpen);
  const { projectId } = useParams({ strict: false }) as { projectId?: string };
  const { s } = useSearch({ strict: false }) as { s?: string };
  useSectionKeys(projectId, s ?? null);
  if (!open || !projectId) return null;
  return <Palette projectId={projectId} selected={s ?? null} />;
}

/** Alt+Up / Alt+Down move to the previous / next section of the tree. */
function useSectionKeys(projectId: string | undefined, selected: string | null) {
  const navigate = useNavigate();
  const { data: tree } = useTree(projectId ?? "");
  useEffect(() => {
    if (!projectId) return;
    const onKey = (e: KeyboardEvent) => {
      if (!e.altKey || e.ctrlKey || e.metaKey || !["ArrowUp", "ArrowDown"].includes(e.key)) return;
      const list = sections(tree ?? []);
      if (list.length === 0) return;
      const at = list.findIndex((n) => n.path === selected);
      const next = e.key === "ArrowDown" ? Math.min(list.length - 1, at + 1) : Math.max(0, at - 1);
      const target = list[at < 0 ? 0 : next];
      if (!target) return;
      e.preventDefault();
      void navigate({ to: "/p/$projectId", params: { projectId }, search: { s: target.path } });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [projectId, selected, tree, navigate]);
}

function Palette({ projectId, selected }: { projectId: string; selected: string | null }) {
  const t = useT();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const mode = useView((st) => st.paletteMode);
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const [debounced, setDebounced] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const { data: tree } = useTree(projectId);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query.trim()), 200);
    return () => clearTimeout(timer);
  }, [query]);
  const { data: found } = useQuery({
    queryKey: ["search", projectId, debounced],
    queryFn: () => searchProject(projectId, debounced),
    enabled: debounced.length >= 2,
  });

  const items = useMemo<Item[]>(() => {
    const view = useView.getState();
    const open = (path: string) => {
      view.setPalette(false);
      void navigate({ to: "/p/$projectId", params: { projectId }, search: { s: path } });
    };
    const act = (id: string, label: string, run: () => void): Item => ({
      id: `a:${id}`,
      group: "actions",
      label,
      run: () => {
        view.setPalette(false);
        run();
      },
    });
    const tones = ["formale", "neutro", "informale"] as const;
    const actions: Item[] = [
      act("export", t("export.title"), () => view.setExportOpen(true)),
      act("import", t("import.open"), () => view.setImportOpen(true)),
      act("glossary", t("glossary.title"), () => view.openGlossary()),
      act("templates", t("templates.title"), () => view.setTemplatesOpen(true)),
      act("issues", t("issues.title"), () => view.setIssuesOpen(true)),
      act("comments", t("comments.title"), () => view.setCommentsOpen(true)),
      act("requirements", t("requirements.open"), () => view.setRequirementsOpen(true)),
      act("snippets", t("snippets.title"), () => view.setSnippetsOpen(true)),
      act("settings", t("settings.title"), () => usePrefs.getState().setSettingsOpen(true)),
      act("write", t("view.write"), () => view.setMode("write")),
      act("review", t("view.review"), () => view.setMode("review")),
      act("focus", t("view.focus"), () => view.setMode("focus")),
      act("source", t("palette.toggleSource"), () => {
        const { mode: m, setMode } = usePreview.getState();
        setMode(m === "source" ? "translated" : "source");
      }),
      act("help", t("shortcuts.title"), () => view.setHelpOpen(true)),
      act("tmx-export", t("palette.tmxExport"), () => {
        const link = document.createElement("a");
        link.href = tmxUrl(projectId);
        link.download = "memoria.tmx";
        document.body.append(link);
        link.click();
        link.remove();
      }),
      act("tmx-import", t("palette.tmxImport"), () => {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = ".tmx,.xml";
        input.onchange = async () => {
          const file = input.files?.[0];
          if (!file) return;
          const show = useNotices.getState().show;
          try {
            const { added } = await importTmx(projectId, file);
            show(t("palette.tmxDone", { count: added }));
          } catch (e) {
            show(e instanceof Error ? e.message : String(e));
          }
        };
        input.click();
      }),
      ...tones.map((tone) =>
        act(`tone:${tone}`, t("palette.tone", { tone }), () => {
          void patchProject(projectId, { tono: tone }).then(() =>
            qc.invalidateQueries({ queryKey: ["project", projectId] }),
          );
        }),
      ),
      act("retranslate-project", t("palette.retranslateProject"), () => {
        void retranslate(projectId, "project");
      }),
    ];
    if (selected) {
      actions.push(
        act("retranslate-section", t("palette.retranslateSection"), () => {
          void retranslate(projectId, "section", selected);
        }),
      );
    }
    const pages: Item[] = sections(tree ?? []).map((n) => ({
      id: `s:${n.path}`,
      group: "sections",
      label: n.title,
      hint: n.path.replace(/^capitoli\//, ""),
      run: () => open(n.path),
    }));
    const hits: Item[] = (found?.hits ?? []).map((h) => ({
      id: `t:${h.path}:${h.key}:${h.field}`,
      group: "text",
      label: `${h.before}${h.match}${h.after}`,
      hint: `${h.title} · ${t(h.field === "source" ? "palette.source" : "palette.translation")}`,
      run: () => open(h.path),
    }));
    return [...pages, ...actions, ...hits];
  }, [t, tree, found, projectId, selected, qc, navigate]);

  const shown = useMemo(() => {
    const q = query.trim();
    if (mode === "text" && !q) return [];
    const ranked = items
      .filter((i) => (mode === "text" ? i.group === "text" : true))
      .map((i) => ({
        item: i,
        score: i.group === "text" ? 0 : fuzzyScore(q, `${i.label} ${i.hint ?? ""}`),
      }))
      .filter((r): r is { item: Item; score: number } => r.score !== null);
    const order = { sections: 0, actions: 1, text: 2 } as const;
    return ranked
      .sort((a, b) => order[a.item.group] - order[b.item.group] || b.score - a.score)
      .map((r) => r.item)
      .slice(0, 40);
  }, [items, query, mode]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: back to the top for each query
  useEffect(() => setIndex(0), [query]);
  useEffect(() => input.current?.focus(), []);

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      e.preventDefault();
      useView.getState().setPalette(false);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setIndex((i) => (shown.length ? (i + 1) % shown.length : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setIndex((i) => (shown.length ? (i - 1 + shown.length) % shown.length : 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      shown[index]?.run();
    }
  };

  let lastGroup = "";
  return (
    <div className="fixed inset-0 z-30 flex items-start justify-center bg-black/30 pt-[12vh]">
      <div
        role="dialog"
        aria-label={t("palette.title")}
        className="w-[560px] max-w-[92vw] rounded-ui border border-border bg-surface shadow-lg"
        onKeyDown={onKey}
      >
        <input
          ref={input}
          role="combobox"
          aria-expanded
          aria-controls="palette-list"
          aria-label={t("palette.title")}
          className="w-full rounded-t-ui border-0 border-b border-border bg-bg px-3 py-2 outline-none"
          placeholder={t(mode === "text" ? "palette.textPlaceholder" : "palette.placeholder")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div id="palette-list" role="listbox" className="max-h-[50vh] overflow-y-auto p-1">
          {shown.length === 0 && query.trim() !== "" && (
            <p className="m-0 px-2 py-1 text-muted">{t("palette.none")}</p>
          )}
          {shown.map((item, i) => {
            const heading = item.group !== lastGroup;
            lastGroup = item.group;
            return (
              <div key={item.id}>
                {heading && (
                  <div className="px-2 pt-2 text-[11px] uppercase text-muted">
                    {t(`palette.${item.group}` as MessageKey)}
                  </div>
                )}
                <div
                  role="option"
                  aria-selected={i === index}
                  tabIndex={-1}
                  onMouseMove={() => setIndex(i)}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    item.run();
                  }}
                  onKeyDown={() => {}}
                  className={`flex cursor-default items-baseline justify-between gap-3 rounded-ui px-2 py-1 ${i === index ? "bg-accent text-accent-fg" : ""}`}
                >
                  <span className="min-w-0 truncate">{item.label}</span>
                  {item.hint && (
                    <span className={`shrink-0 text-[12px] ${i === index ? "" : "text-muted"}`}>
                      {item.hint}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
