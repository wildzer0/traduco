import { useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useEffect, useRef } from "react";
import { CheckPanel } from "../features/companion/CheckPanel";
import { EditorPane } from "../features/editor/EditorPane";
import { ExportPanel } from "../features/export/ExportPanel";
import { GlossaryDrawer } from "../features/glossary/GlossaryDrawer";
import { ImportPanel } from "../features/import/ImportPanel";
import { CommentsPanel } from "../features/issues/CommentsPanel";
import { IssuesPanel } from "../features/issues/IssuesPanel";
import { RequirementsPanel } from "../features/issues/RequirementsPanel";
import { Preview } from "../features/preview/Preview";
import { reviewKey } from "../features/preview/segment-actions";
import { ReviewTable } from "../features/review/ReviewTable";
import { TemplateDrawer } from "../features/templates/TemplateDrawer";
import { keys } from "../features/tree/queries";
import { getLlmStatus, getReview } from "../lib/api";
import { useAssist } from "../lib/assist-store";
import { emitFileEvent } from "../lib/file-events";
import { useT } from "../lib/i18n";
import { usePrefs } from "../lib/prefs";
import { useTranslationState } from "../lib/translation-store";
import { useView } from "../lib/view-store";
import { useProjectEvents } from "../lib/ws";
import { Sidebar } from "./Sidebar";

/** Three columns for one project: sidebar, editor, translated preview (docs/03-ui.md). */
export function Workspace() {
  const t = useT();
  const { projectId } = useParams({ strict: false }) as { projectId: string };
  const { s } = useSearch({ strict: false }) as { s?: string };
  const navigate = useNavigate();
  const qc = useQueryClient();
  const sidebarOpen = usePrefs((st) => st.sidebarOpen);
  const {
    mode,
    setMode,
    setFocusKey,
    glossaryOpen,
    templatesOpen,
    exportOpen,
    importOpen,
    issuesOpen,
    commentsOpen,
    requirementsOpen,
  } = useView();
  const checkOpen = useAssist((st) => st.checkOpen);
  const lastF8 = useRef<{ path: string; key: string } | null>(null);
  const selected = s ?? null;
  const select = (path: string | null) =>
    navigate({
      to: "/p/$projectId",
      params: { projectId },
      search: path ? { s: path } : {},
      replace: true,
    });

  useProjectEvents(projectId, {
    onEvent: (event) => {
      const state = useTranslationState.getState();
      if (event.type === "llm.status") state.setLlm(event.online === true, event.model ?? "");
      if (event.type === "job.progress") state.setPending(event.pending ?? 0);
      emitFileEvent(event);
      // translation progress events are frequent and change neither the tree nor the skeleton
      if (event.type === "file.changed" || event.type === "project.changed") {
        qc.invalidateQueries({ queryKey: keys.tree(projectId) });
        qc.invalidateQueries({ queryKey: keys.skeleton(projectId) });
      }
    },
    onConnect: () => {
      getLlmStatus()
        .then((st) => {
          useTranslationState.getState().setLlm(st.online, st.model);
          useTranslationState.getState().setPending(st.pending ?? 0);
        })
        .catch(() => useTranslationState.getState().setLlm(false, ""));
      // changes may have happened while disconnected: refetch the tree, let the open file re-check itself
      qc.invalidateQueries({ queryKey: keys.tree(projectId) });
      qc.invalidateQueries({ queryKey: keys.skeleton(projectId) });
      emitFileEvent({ type: "hello" });
    },
  });

  // Coming back from another program (editor, git client): re-check what may have changed meanwhile.
  useEffect(() => {
    const recheck = () => {
      qc.invalidateQueries({ queryKey: keys.tree(projectId) });
      qc.invalidateQueries({ queryKey: keys.skeleton(projectId) });
      emitFileEvent({ type: "hello" });
    };
    window.addEventListener("focus", recheck);
    return () => window.removeEventListener("focus", recheck);
  }, [qc, projectId]);

  // F8: next segment to review, across sections (docs/03-ui.md)
  // biome-ignore lint/correctness/useExhaustiveDependencies: select only calls the router
  useEffect(() => {
    const onKey = async (e: KeyboardEvent) => {
      if (e.key !== "F8") return;
      e.preventDefault();
      const data = await qc.fetchQuery({
        queryKey: reviewKey(projectId),
        queryFn: () => getReview(projectId),
        staleTime: 0,
      });
      const list = data.segments.filter((r) => r.status === "needs_review");
      if (list.length === 0) return;
      const last = lastF8.current;
      let index = last ? list.findIndex((r) => r.path === last.path && r.key === last.key) : -1;
      if (index < 0 && selected) {
        const from = list.findIndex((r) => r.path >= selected);
        index = from < 0 ? -1 : from - 1;
      }
      const next = list[(index + 1) % list.length];
      if (!next) return;
      lastF8.current = { path: next.path, key: next.key };
      setMode("write");
      select(next.path);
      setFocusKey(next.key);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [qc, projectId, selected, setMode, setFocusKey]);

  const editor = (
    <main
      aria-label={t("editor.label")}
      className={`flex min-w-0 flex-1 flex-col ${mode === "focus" ? "" : "border-r border-border"}`}
    >
      {selected ? (
        <EditorPane key={projectId} projectId={projectId} path={selected} />
      ) : (
        <p className="mx-auto w-full max-w-[72ch] p-6 text-[15px] text-muted">
          {t("editor.noSection")}
        </p>
      )}
    </main>
  );

  return (
    <>
      {sidebarOpen && mode !== "focus" && (
        <Sidebar projectId={projectId} selected={selected} onSelect={select} />
      )}
      {mode === "review" ? (
        <ReviewTable
          projectId={projectId}
          onOpen={(path, key) => {
            setMode("write");
            select(path);
            setFocusKey(key);
          }}
        />
      ) : (
        <>
          {editor}
          {mode === "write" && <Preview projectId={projectId} />}
        </>
      )}
      {glossaryOpen && <GlossaryDrawer projectId={projectId} />}
      {checkOpen && <CheckPanel projectId={projectId} path={selected} />}
      {templatesOpen && <TemplateDrawer projectId={projectId} />}
      {exportOpen && <ExportPanel projectId={projectId} selected={selected} />}
      {importOpen && <ImportPanel projectId={projectId} />}
      {requirementsOpen && <RequirementsPanel projectId={projectId} />}
      {issuesOpen && <IssuesPanel projectId={projectId} />}
      {commentsOpen && <CommentsPanel projectId={projectId} path={selected} />}
    </>
  );
}
