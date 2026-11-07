import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useT } from "../lib/i18n";
import { usePrefs } from "../lib/prefs";
import { Sidebar } from "./Sidebar";

/** Three columns for one project: sidebar, editor, translated preview (docs/03-ui.md). */
export function Workspace() {
  const t = useT();
  const { projectId } = useParams({ strict: false }) as { projectId: string };
  const { s } = useSearch({ strict: false }) as { s?: string };
  const navigate = useNavigate();
  const sidebarOpen = usePrefs((st) => st.sidebarOpen);
  const selected = s ?? null;
  const select = (path: string | null) =>
    navigate({
      to: "/p/$projectId",
      params: { projectId },
      search: path ? { s: path } : {},
      replace: true,
    });

  return (
    <>
      {sidebarOpen && <Sidebar projectId={projectId} selected={selected} onSelect={select} />}
      <main
        aria-label={t("editor.label")}
        className="flex min-w-0 flex-1 flex-col border-r border-border"
      >
        <div className="flex h-10 shrink-0 items-center border-b border-border px-3" />
        <p className="mx-auto w-full max-w-[72ch] p-6 text-[15px] text-muted">
          {selected ? t("editor.placeholder") : t("editor.noSection")}
        </p>
      </main>
      <section aria-label={t("preview.label")} className="flex min-w-0 flex-1 flex-col">
        <div className="flex h-10 shrink-0 items-center border-b border-border px-3 text-muted">
          {t("preview.title")}
        </div>
      </section>
    </>
  );
}
