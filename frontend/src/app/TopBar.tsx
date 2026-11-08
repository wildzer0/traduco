import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import {
  ArrowLeft,
  Clock,
  Download,
  ListChecks,
  LogOut,
  MessageSquare,
  PanelLeft,
  Tag,
} from "lucide-react";
import { Brand } from "../components/Logo";
import { useProjects, useTree } from "../features/tree/queries";
import { getProject, patchProject, retranslate } from "../lib/api";
import { useT } from "../lib/i18n";
import { useNotices } from "../lib/notices";
import { usePrefs } from "../lib/prefs";
import { logout, useLeaveOnExit, useMe, usePresence } from "../lib/team";
import { useTranslationState } from "../lib/translation-store";
import type { Tone } from "../lib/types";
import { useView, type ViewMode } from "../lib/view-store";
import { findTrail } from "./trail";

export function TopBar() {
  const t = useT();
  const navigate = useNavigate();
  const toggleSidebar = usePrefs((s) => s.toggleSidebar);
  const { online, model } = useTranslationState();
  const { projectId } = useParams({ strict: false }) as { projectId?: string };
  const { s } = useSearch({ strict: false }) as { s?: string };
  const { data: projects } = useProjects();
  const { data: tree } = useTree(projectId ?? "");
  const project = projects?.find((p) => p.id === projectId);
  const trail = findTrail(projectId ? (tree ?? []) : [], s ?? null);

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-surface px-4">
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
      {projectId ? (
        <button
          type="button"
          onClick={() => void navigate({ to: "/" })}
          title={t("topbar.allProjects")}
          className="flex h-8 items-center gap-1 rounded-ui px-2 text-muted hover:bg-surface-2 hover:text-fg"
        >
          <ArrowLeft size={14} strokeWidth={1.5} aria-hidden />
          <span className="sr-only">{t("topbar.allProjects")}</span>
        </button>
      ) : null}
      <button
        type="button"
        onClick={() => void navigate({ to: "/" })}
        className="rounded-ui px-1 py-1 hover:bg-surface-2"
        title={t("topbar.allProjects")}
      >
        <Brand />
      </button>
      {projectId ? (
        <nav
          aria-label="breadcrumb"
          className="ml-2 flex min-w-0 items-center gap-1.5 truncate border-l border-border pl-4 text-muted"
        >
          <button
            type="button"
            onClick={() => void navigate({ to: "/p/$projectId", params: { projectId } })}
            aria-label={t("topbar.project", { name: project?.nome ?? projectId })}
            className="rounded-ui font-medium text-fg hover:text-accent"
          >
            {project?.nome ?? projectId}
          </button>
          {trail.map((n) => (
            <span key={n.path} className="truncate">
              <span aria-hidden className="mr-1.5 text-border">
                /
              </span>
              {n.title}
            </span>
          ))}
        </nav>
      ) : (
        <span className="text-muted">{t("topbar.noProject")}</span>
      )}
      <span className="ml-auto" />
      {projectId && <People projectId={projectId} path={s ?? null} />}
      {projectId && <ProjectTone projectId={projectId} />}
      {projectId && <ViewSwitch />}
      {projectId && <PanelButtons />}
      {projectId && <ExportButton />}
      {projectId && (
        <span
          data-testid="llm-indicator"
          data-online={String(online)}
          title={
            online === null
              ? t("llm.unknown")
              : online
                ? t("llm.online", { model })
                : t("llm.offline")
          }
          className="flex items-center gap-1.5 text-muted"
        >
          <span
            aria-hidden
            className={`size-2 rounded-full ${online === null ? "bg-amber" : online ? "bg-green" : "bg-red"}`}
          />
          <span className="sr-only">
            {online === null
              ? t("llm.unknown")
              : online
                ? t("llm.online", { model })
                : t("llm.offline")}
          </span>
        </span>
      )}
      <UserMenu />
    </header>
  );
}

/** Initials of the other people in the project; a ring marks who is editing. */
function People({ projectId, path }: { projectId: string; path: string | null }) {
  const t = useT();
  const { people } = usePresence(projectId, path);
  useLeaveOnExit(projectId);
  if (people.length === 0) return null;
  return (
    <ul aria-label={t("team.people")} className="m-0 flex list-none gap-1 p-0">
      {people.map((p) => (
        <li
          key={p.sub}
          title={p.editing ? t("team.editing", { name: p.name, section: p.path ?? "" }) : p.name}
          className={`flex size-6 items-center justify-center rounded-full bg-surface-2 text-[11px] font-semibold ${p.editing ? "ring-2 ring-accent" : ""}`}
        >
          {p.name.slice(0, 2).toUpperCase()}
        </li>
      ))}
    </ul>
  );
}

function UserMenu() {
  const t = useT();
  const { data: me } = useMe();
  if (me?.mode !== "team" || !me.user) return null;
  return (
    <span className="flex items-center gap-1 text-muted">
      <span>{me.user.name}</span>
      <button
        type="button"
        aria-label={t("team.logout")}
        title={t("team.logout")}
        onClick={() => void logout()}
        className="flex size-8 items-center justify-center rounded-ui hover:bg-surface-2"
      >
        <LogOut size={16} strokeWidth={1.5} aria-hidden />
      </button>
    </span>
  );
}

const MODES: { mode: ViewMode; key: "view.write" | "view.review" | "view.focus"; hint: string }[] =
  [
    { mode: "write", key: "view.write", hint: "Ctrl+1" },
    { mode: "review", key: "view.review", hint: "Ctrl+2" },
    { mode: "focus", key: "view.focus", hint: "Ctrl+3" },
  ];

function ViewSwitch() {
  const t = useT();
  const { mode, setMode } = useView();
  return (
    <fieldset className="m-0 flex gap-0.5 rounded-ui border-0 bg-surface-2 p-0.5">
      <legend className="sr-only">{t("view.label")}</legend>
      {MODES.map((m) => (
        <button
          key={m.mode}
          type="button"
          aria-pressed={mode === m.mode}
          title={`${t(m.key)} (${m.hint})`}
          onClick={() => setMode(m.mode)}
          className={`rounded-[6px] px-3 py-1 ${mode === m.mode ? "bg-surface font-medium text-fg shadow-[0_1px_2px_rgb(0_0_0/10%)]" : "text-muted hover:text-fg"}`}
        >
          {t(m.key)}
        </button>
      ))}
    </fieldset>
  );
}

const TONES: Tone[] = ["formale", "neutro", "informale"];

/** Project tone (RF-25): changing it retranslates what the author has not fixed by hand. */
function ProjectTone({ projectId }: { projectId: string }) {
  const t = useT();
  const qc = useQueryClient();
  const notify = useNotices((s) => s.show);
  const { data } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
  });
  if (!data) return null;
  return (
    <label className="flex items-center gap-1 text-muted">
      <span className="sr-only">{t("tone.project")}</span>
      <select
        aria-label={t("tone.project")}
        title={t("tone.project")}
        value={data.tono}
        onChange={async (e) => {
          try {
            await patchProject(projectId, { tono: e.target.value as Tone });
            await retranslate(projectId, "project");
            await qc.invalidateQueries({ queryKey: ["project", projectId] });
            await qc.invalidateQueries({ queryKey: ["translation", projectId] });
          } catch (err) {
            notify(err instanceof Error ? err.message : String(err));
          }
        }}
        className="rounded-ui border-0 bg-transparent px-1 py-1 text-muted hover:bg-surface-2"
      >
        {TONES.map((tone) => (
          <option key={tone} value={tone}>
            {t(`tone.${tone}` as "tone.formale")}
          </option>
        ))}
      </select>
    </label>
  );
}

function ExportButton() {
  const t = useT();
  const setExportOpen = useView((s) => s.setExportOpen);
  return (
    <button
      type="button"
      title={`${t("export.title")} (Ctrl+E)`}
      onClick={() => setExportOpen(true)}
      className="flex items-center gap-1.5 rounded-ui bg-accent px-3 py-1.5 font-medium text-accent-fg hover:opacity-90"
    >
      <Download size={14} strokeWidth={1.75} aria-hidden />
      {t("export.title")}
    </button>
  );
}

function PanelButtons() {
  const t = useT();
  const setIssuesOpen = useView((s) => s.setIssuesOpen);
  const setHistoryOpen = useView((s) => s.setHistoryOpen);
  const setCommentsOpen = useView((s) => s.setCommentsOpen);
  const setRequirementsOpen = useView((s) => s.setRequirementsOpen);
  const style =
    "flex size-8 items-center justify-center gap-1 rounded-ui text-muted hover:bg-surface-2 hover:text-fg 2xl:w-auto 2xl:px-2";
  return (
    <>
      <button
        type="button"
        onClick={() => setCommentsOpen(true)}
        className={style}
        aria-label={t("comments.open")}
        title={t("comments.open")}
      >
        <MessageSquare size={14} strokeWidth={1.5} aria-hidden />
        <span className="hidden 2xl:inline">{t("comments.open")}</span>
      </button>
      <button
        type="button"
        onClick={() => setRequirementsOpen(true)}
        className={style}
        aria-label={t("requirements.open")}
        title={t("requirements.open")}
      >
        <ListChecks size={14} strokeWidth={1.5} aria-hidden />
        <span className="hidden 2xl:inline">{t("requirements.open")}</span>
      </button>
      <button
        type="button"
        onClick={() => setHistoryOpen(true)}
        className={style}
        aria-label={t("history.open")}
        title={t("history.open")}
      >
        <Clock size={14} strokeWidth={1.5} aria-hidden />
        <span className="hidden 2xl:inline">{t("history.open")}</span>
      </button>
      <button
        type="button"
        onClick={() => setIssuesOpen(true)}
        className={style}
        aria-label={t("issues.open")}
        title={t("issues.open")}
      >
        <Tag size={14} strokeWidth={1.5} aria-hidden />
        <span className="hidden 2xl:inline">{t("issues.open")}</span>
      </button>
    </>
  );
}
