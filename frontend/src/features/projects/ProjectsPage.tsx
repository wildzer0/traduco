import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { FolderPlus, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import {
  ApiError,
  createFolder,
  createProject,
  deleteFolder,
  deleteProject,
  duplicateProject,
  getWorkspace,
  listTrash,
  purgeProject,
  renameProject,
  restoreProject,
  setProjectFolder,
  updateFolder,
} from "../../lib/api";
import { useT } from "../../lib/i18n";
import { useNotices } from "../../lib/notices";
import { usePrefs } from "../../lib/prefs";
import type { FolderInfo, ProjectSummary, TrashEntry } from "../../lib/types";
import { keys } from "../tree/queries";
import { CreateProjectDialog, type NewProject } from "./CreateProjectDialog";
import { ConfirmDialog, MoveDialog, NameDialog, TrashDialog } from "./dialogs";
import { DRAG_TYPE, FolderTree } from "./FolderTree";
import {
  childrenOf,
  matches,
  projectsIn,
  type SortKey,
  sortProjects,
  withDescendants,
} from "./organize";
import { ProjectTable } from "./ProjectTable";

type Dialog =
  | { kind: "create" }
  | { kind: "folder"; parent: string | null }
  | { kind: "rename-folder"; folder: FolderInfo }
  | { kind: "delete-folder"; folder: FolderInfo }
  | { kind: "duplicate"; project: ProjectSummary }
  | { kind: "rename"; project: ProjectSummary }
  | { kind: "move"; project: ProjectSummary }
  | { kind: "delete"; project: ProjectSummary }
  | { kind: "purge"; entry: TrashEntry }
  | { kind: "trash" }
  | null;

const WORKSPACE = ["workspace"] as const;

/** The home page: folders inside folders, projects with what matters about each, and a search. */
export function ProjectsPage() {
  const t = useT();
  const locale = usePrefs((s) => s.locale);
  const setSettingsOpen = usePrefs((s) => s.setSettingsOpen);
  const notify = useNotices((s) => s.show);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { c: wanted } = useSearch({ strict: false }) as { c?: string };
  const { data } = useQuery({ queryKey: WORKSPACE, queryFn: getWorkspace });
  const { data: trash = [] } = useQuery({ queryKey: ["trash"], queryFn: listTrash });
  const folders = data?.folders ?? [];
  const projects = data?.projects ?? [];
  const current = wanted && folders.some((f) => f.id === wanted) ? wanted : null;
  const here = folders.find((f) => f.id === current) ?? null;
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; direction: "asc" | "desc" }>({
    key: "ultima_modifica",
    direction: "desc",
  });
  const [dialog, setDialog] = useState<Dialog>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const now = useMemo(() => new Date(), []);

  const refresh = async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: WORKSPACE }),
      qc.invalidateQueries({ queryKey: keys.projects }),
      qc.invalidateQueries({ queryKey: ["trash"] }),
    ]);
  };
  const run = async (job: () => Promise<unknown>) => {
    try {
      await job();
      await refresh();
    } catch (e) {
      notify(e instanceof Error ? e.message : String(e));
    }
  };
  const goTo = (id: string | null) => void navigate({ to: "/", search: id ? { c: id } : {} });
  const open = (p: ProjectSummary) =>
    void navigate({ to: "/p/$projectId", params: { projectId: p.id }, search: {} });

  const create = useMutation({
    mutationFn: async (body: NewProject | { esempio: true }) => {
      const { cartella, ...rest } = "cartella" in body ? body : { ...body, cartella: current };
      const made = await createProject(rest);
      if (cartella) await setProjectFolder(made.id, cartella);
      return made;
    },
    onSuccess: async (made) => {
      await refresh();
      setDialog(null);
      void navigate({ to: "/p/$projectId", params: { projectId: made.id }, search: {} });
    },
    onError: (e) => {
      if (e instanceof ApiError && e.code === "invalid_skeleton")
        setCreateError(t("welcome.skeletonError", { message: e.message }));
      else notify(t("error.generic", { message: e instanceof Error ? e.message : String(e) }));
    },
  });

  const searching = query.trim() !== "";
  const shown = sortProjects(
    searching ? projects.filter((p) => matches(p, query)) : projectsIn(projects, current),
    sort.key,
    sort.direction,
  );
  const subfolders = searching ? [] : childrenOf(folders, current);
  const sortBy = (key: SortKey) =>
    setSort((s) =>
      s.key === key
        ? { key, direction: s.direction === "asc" ? "desc" : "asc" }
        : { key, direction: key === "ultima_modifica" ? "desc" : "asc" },
    );
  const drop = (projectId: string, folder: string | null) =>
    run(() => setProjectFolder(projectId, folder));

  const nothing = projects.length === 0 && folders.length === 0;
  return (
    <main className="flex min-h-0 flex-1 overflow-hidden">
      <aside className="flex w-64 shrink-0 flex-col gap-2 overflow-y-auto border-r border-border bg-surface-2 p-3">
        <div className="flex items-center justify-between">
          <h2 className="m-0 text-[11px] font-semibold uppercase tracking-wide text-muted">
            {t("projects.folders")}
          </h2>
          <button
            type="button"
            onClick={() => setDialog({ kind: "folder", parent: current })}
            title={t("projects.newFolder")}
            aria-label={t("projects.newFolder")}
            className="flex size-7 items-center justify-center rounded-ui text-muted hover:bg-surface hover:text-fg"
          >
            <FolderPlus size={16} aria-hidden />
          </button>
        </div>
        <FolderTree
          folders={folders}
          projects={projects}
          current={current}
          onSelect={goTo}
          onNewFolder={(parent) => setDialog({ kind: "folder", parent })}
          onRename={(folder) => setDialog({ kind: "rename-folder", folder })}
          onDelete={(folder) => setDialog({ kind: "delete-folder", folder })}
          onDropProject={drop}
        />
        <button
          type="button"
          onClick={() => setDialog({ kind: "trash" })}
          className="mt-auto flex items-center gap-2 rounded-ui px-2 py-1 text-left text-muted hover:bg-surface hover:text-fg"
        >
          <Trash2 size={14} aria-hidden />
          {t("projects.trash")}
          {trash.length > 0 && <span className="ml-auto text-[12px]">{trash.length}</span>}
        </button>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col overflow-y-auto p-6">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="m-0 mr-2 text-xl font-semibold">{t("projects.title")}</h1>
          <label className="relative min-w-[16rem] max-w-md flex-1">
            <span className="sr-only">{t("projects.search")}</span>
            <Search
              size={14}
              aria-hidden
              className="pointer-events-none absolute left-2 top-1/2 -translate-y-1/2 text-muted"
            />
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t("projects.search")}
              className="w-full rounded-ui border border-border bg-surface py-1.5 pl-7 pr-2"
            />
          </label>
          <span className="ml-auto" />
          <button
            type="button"
            onClick={() => {
              setCreateError(null);
              setDialog({ kind: "create" });
            }}
            className="rounded-ui bg-accent px-3 py-1.5 text-accent-fg"
          >
            {t("welcome.create")}
          </button>
          <button
            type="button"
            onClick={() => create.mutate({ esempio: true })}
            className="rounded-ui border border-border px-3 py-1.5 hover:bg-surface-2"
          >
            {t("welcome.example")}
          </button>
          <button
            type="button"
            onClick={() => setSettingsOpen(true)}
            className="rounded-ui px-3 py-1.5 text-muted hover:bg-surface-2"
          >
            {t("sidebar.settings")}
          </button>
        </div>

        <nav
          aria-label={t("projects.where")}
          className="mt-3 flex flex-wrap items-center gap-1 text-[14px] text-muted"
        >
          {searching ? (
            <span>{t("projects.resultsFor", { query: query.trim() })}</span>
          ) : (
            <>
              <button
                type="button"
                onClick={() => goTo(null)}
                onDragOver={(e) => e.dataTransfer.types.includes(DRAG_TYPE) && e.preventDefault()}
                onDrop={(e) => {
                  const id = e.dataTransfer.getData(DRAG_TYPE);
                  if (id) drop(id, null);
                }}
                className={here ? "hover:text-fg" : "font-medium text-fg"}
              >
                {t("projects.rootName")}
              </button>
              {(here?.percorso ?? []).map((name, index, all) => {
                const id = folderAt(folders, here, index);
                return (
                  <span key={id ?? name} className="flex items-center gap-1">
                    <span aria-hidden>›</span>
                    <button
                      type="button"
                      aria-current={index === all.length - 1 ? "page" : undefined}
                      onClick={() => goTo(id)}
                      className={index === all.length - 1 ? "font-medium text-fg" : "hover:text-fg"}
                    >
                      {name}
                    </button>
                  </span>
                );
              })}
            </>
          )}
        </nav>

        {subfolders.length > 0 && (
          <ul className="m-0 mt-4 grid list-none grid-cols-[repeat(auto-fill,minmax(14rem,1fr))] gap-2 p-0">
            {subfolders.map((f) => (
              <li key={f.id}>
                <button
                  type="button"
                  onClick={() => goTo(f.id)}
                  onDragOver={(e) => e.dataTransfer.types.includes(DRAG_TYPE) && e.preventDefault()}
                  onDrop={(e) => {
                    const id = e.dataTransfer.getData(DRAG_TYPE);
                    if (id) drop(id, f.id);
                  }}
                  className="flex w-full items-center gap-2 rounded-ui border border-border bg-surface px-3 py-2 text-left hover:bg-surface-2"
                >
                  <span className="truncate font-medium">{f.nome}</span>
                  <span className="ml-auto text-[12px] text-muted">
                    {t("projects.count", { count: withDescendantsCount(folders, projects, f.id) })}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-4">
          {shown.length > 0 ? (
            <ProjectTable
              projects={shown}
              showFolder={searching}
              sort={sort}
              onSort={sortBy}
              locale={locale}
              now={now}
              onOpen={open}
              onDuplicate={(project) => setDialog({ kind: "duplicate", project })}
              onMove={(project) => setDialog({ kind: "move", project })}
              onRename={(project) => setDialog({ kind: "rename", project })}
              onDelete={(project) => setDialog({ kind: "delete", project })}
            />
          ) : (
            <p className="text-muted">
              {searching
                ? t("projects.noResults", { query: query.trim() })
                : nothing
                  ? t("welcome.empty")
                  : t("projects.emptyFolder")}
            </p>
          )}
        </div>
      </section>

      {dialog?.kind === "create" && (
        <CreateProjectDialog
          folders={folders}
          folder={current}
          error={createError}
          busy={create.isPending}
          onSubmit={(project) => create.mutate(project)}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog?.kind === "folder" && (
        <NameDialog
          title={t("projects.newFolderTitle")}
          label={t("projects.folderName")}
          confirm={t("welcome.submit")}
          onClose={() => setDialog(null)}
          onSubmit={(name) => {
            const parent = dialog.parent;
            setDialog(null);
            void run(() => createFolder(name, parent));
          }}
        />
      )}
      {dialog?.kind === "rename-folder" && (
        <NameDialog
          title={t("projects.renameFolder")}
          label={t("projects.folderName")}
          initial={dialog.folder.nome}
          confirm={t("projects.save")}
          onClose={() => setDialog(null)}
          onSubmit={(name) => {
            const id = dialog.folder.id;
            setDialog(null);
            void run(() => updateFolder(id, { nome: name }));
          }}
        />
      )}
      {dialog?.kind === "delete-folder" && (
        <ConfirmDialog
          title={t("projects.deleteFolderTitle", { name: dialog.folder.nome })}
          message={t("projects.deleteFolderMessage", { name: dialog.folder.nome })}
          confirm={t("projects.deleteFolderConfirm")}
          destructive
          onClose={() => setDialog(null)}
          onConfirm={() => {
            const id = dialog.folder.id;
            setDialog(null);
            if (current === id || (current && withDescendants(folders, id).has(current)))
              goTo(dialog.folder.genitore);
            void run(() => deleteFolder(id));
          }}
        />
      )}
      {dialog?.kind === "duplicate" && (
        <NameDialog
          title={t("projects.duplicateTitle", { name: dialog.project.nome })}
          label={t("projects.copyName")}
          initial={t("projects.copyOf", { name: dialog.project.nome })}
          confirm={t("projects.duplicateConfirm")}
          onClose={() => setDialog(null)}
          onSubmit={(name) => {
            const id = dialog.project.id;
            setDialog(null);
            void run(() => duplicateProject(id, name));
          }}
        />
      )}
      {dialog?.kind === "rename" && (
        <NameDialog
          title={t("projects.renameTitle")}
          label={t("welcome.name")}
          initial={dialog.project.nome}
          confirm={t("projects.save")}
          onClose={() => setDialog(null)}
          onSubmit={(name) => {
            const id = dialog.project.id;
            setDialog(null);
            void run(() => renameProject(id, name));
          }}
        />
      )}
      {dialog?.kind === "move" && (
        <MoveDialog
          title={t("projects.moveTitle", { name: dialog.project.nome })}
          folders={folders}
          current={dialog.project.cartella ?? null}
          onClose={() => setDialog(null)}
          onPick={(folder) => {
            const id = dialog.project.id;
            setDialog(null);
            void run(() => setProjectFolder(id, folder));
          }}
        />
      )}
      {dialog?.kind === "delete" && (
        <ConfirmDialog
          title={t("projects.deleteTitle", { name: dialog.project.nome })}
          message={t("projects.deleteMessage")}
          confirm={t("projects.deleteConfirm")}
          destructive
          onClose={() => setDialog(null)}
          onConfirm={() => {
            const id = dialog.project.id;
            setDialog(null);
            void run(() => deleteProject(id));
          }}
        />
      )}
      {dialog?.kind === "trash" && (
        <TrashDialog
          entries={trash}
          locale={locale}
          onClose={() => setDialog(null)}
          onRestore={(entry) => void run(() => restoreProject(entry.name))}
          onPurge={(entry) => setDialog({ kind: "purge", entry })}
        />
      )}
      {dialog?.kind === "purge" && (
        <ConfirmDialog
          title={t("projects.purgeTitle", { name: dialog.entry.nome })}
          message={t("projects.purgeMessage", { name: dialog.entry.nome })}
          confirm={t("projects.purge")}
          destructive
          onClose={() => setDialog({ kind: "trash" })}
          onConfirm={() => {
            const name = dialog.entry.name;
            setDialog({ kind: "trash" });
            void run(() => purgeProject(name));
          }}
        />
      )}
    </main>
  );
}

/** The id of the folder at position ``index`` on the path to ``folder`` (top first). */
function folderAt(folders: FolderInfo[], folder: FolderInfo | null, index: number): string | null {
  const chain: FolderInfo[] = [];
  let walk = folder;
  while (walk) {
    chain.unshift(walk);
    const parent: string | null = walk.genitore;
    walk = parent ? (folders.find((f) => f.id === parent) ?? null) : null;
  }
  return chain[index]?.id ?? null;
}

const withDescendantsCount = (folders: FolderInfo[], projects: ProjectSummary[], id: string) => {
  const inside = withDescendants(folders, id);
  return projects.filter((p) => p.cartella && inside.has(p.cartella)).length;
};
