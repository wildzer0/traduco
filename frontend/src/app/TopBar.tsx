import { useParams, useSearch } from "@tanstack/react-router";
import { PanelLeft } from "lucide-react";
import { useProjects, useTree } from "../features/tree/queries";
import { useT } from "../lib/i18n";
import { usePrefs } from "../lib/prefs";
import { findTrail } from "./trail";

export function TopBar() {
  const t = useT();
  const toggleSidebar = usePrefs((s) => s.toggleSidebar);
  const { projectId } = useParams({ strict: false }) as { projectId?: string };
  const { s } = useSearch({ strict: false }) as { s?: string };
  const { data: projects } = useProjects();
  const { data: tree } = useTree(projectId ?? "");
  const project = projects?.find((p) => p.id === projectId);
  const trail = findTrail(projectId ? (tree ?? []) : [], s ?? null);

  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border bg-surface px-3">
      {projectId && (
        <button
          type="button"
          aria-label={t("topbar.toggleSidebar")}
          title={t("topbar.toggleSidebar")}
          onClick={toggleSidebar}
          className="flex size-8 items-center justify-center rounded-ui text-muted hover:bg-surface-2"
        >
          <PanelLeft size={16} strokeWidth={1.5} aria-hidden />
        </button>
      )}
      <span className="font-semibold">{t("app.name")}</span>
      {projectId ? (
        <nav
          aria-label="breadcrumb"
          className="flex min-w-0 items-center gap-1 truncate text-muted"
        >
          <span>{project?.nome ?? projectId}</span>
          {trail.map((n) => (
            <span key={n.path} className="truncate">
              <span aria-hidden> › </span>
              {n.title}
            </span>
          ))}
        </nav>
      ) : (
        <span className="text-muted">{t("topbar.noProject")}</span>
      )}
    </header>
  );
}
