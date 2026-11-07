import { useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useEffect } from "react";
import { EditorPane } from "../features/editor/EditorPane";
import { Preview } from "../features/preview/Preview";
import { keys } from "../features/tree/queries";
import { getLlmStatus } from "../lib/api";
import { emitFileEvent } from "../lib/file-events";
import { useT } from "../lib/i18n";
import { usePrefs } from "../lib/prefs";
import { useTranslationState } from "../lib/translation-store";
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
      qc.invalidateQueries({ queryKey: keys.tree(projectId) });
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
      emitFileEvent({ type: "hello" });
    },
  });

  // Coming back from another program (editor, git client): re-check what may have changed meanwhile.
  useEffect(() => {
    const recheck = () => {
      qc.invalidateQueries({ queryKey: keys.tree(projectId) });
      emitFileEvent({ type: "hello" });
    };
    window.addEventListener("focus", recheck);
    return () => window.removeEventListener("focus", recheck);
  }, [qc, projectId]);

  return (
    <>
      {sidebarOpen && <Sidebar projectId={projectId} selected={selected} onSelect={select} />}
      <main
        aria-label={t("editor.label")}
        className="flex min-w-0 flex-1 flex-col border-r border-border"
      >
        {selected ? (
          <EditorPane key={projectId} projectId={projectId} path={selected} />
        ) : (
          <p className="mx-auto w-full max-w-[72ch] p-6 text-[15px] text-muted">
            {t("editor.noSection")}
          </p>
        )}
      </main>
      <Preview projectId={projectId} />
    </>
  );
}
