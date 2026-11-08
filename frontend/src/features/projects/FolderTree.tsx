import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { ChevronRight, Ellipsis, Folder, FolderOpen } from "lucide-react";
import { useState } from "react";
import { useT } from "../../lib/i18n";
import type { FolderInfo, ProjectSummary } from "../../lib/types";
import { childrenOf } from "./organize";

export const DRAG_TYPE = "application/x-traduco-project";

interface Props {
  folders: FolderInfo[];
  projects: ProjectSummary[];
  current: string | null;
  onSelect: (id: string | null) => void;
  onNewFolder: (parent: string | null) => void;
  onRename: (folder: FolderInfo) => void;
  onDelete: (folder: FolderInfo) => void;
  /** A project was dropped on a folder (null: on the top level). */
  onDropProject: (projectId: string, folder: string | null) => void;
}

const menuItem =
  "cursor-default rounded-ui px-2 py-1 outline-none data-[highlighted]:bg-accent-soft data-[highlighted]:text-accent";

/** Folders inside folders, as a tree: click to look inside, drop a project on one to move it. */
export function FolderTree({
  folders,
  projects,
  current,
  onSelect,
  onNewFolder,
  onRename,
  onDelete,
  onDropProject,
}: Props) {
  const t = useT();
  const [closed, setClosed] = useState<Set<string>>(new Set());
  const [over, setOver] = useState<string | null | undefined>(undefined);
  const direct = (id: string | null) => projects.filter((p) => (p.cartella ?? null) === id).length;

  const target = (id: string | null) => ({
    onDragOver: (e: React.DragEvent) => {
      if (!e.dataTransfer.types.includes(DRAG_TYPE)) return;
      e.preventDefault();
      setOver(id);
    },
    onDragLeave: () => setOver(undefined),
    onDrop: (e: React.DragEvent) => {
      const project = e.dataTransfer.getData(DRAG_TYPE);
      setOver(undefined);
      if (project) {
        e.preventDefault();
        onDropProject(project, id);
      }
    },
  });

  const highlight = (id: string | null) =>
    over === id ? "bg-accent/20 outline outline-1 outline-accent" : "";

  const level = (parent: string | null, depth: number) => (
    <ul className="m-0 list-none p-0">
      {childrenOf(folders, parent).map((f) => {
        const kids = childrenOf(folders, f.id).length > 0;
        const isClosed = closed.has(f.id);
        return (
          <li key={f.id}>
            <div
              {...target(f.id)}
              style={{ paddingLeft: depth * 14 }}
              className={`group flex items-center rounded-ui ${current === f.id ? "bg-surface" : "hover:bg-surface"} ${highlight(f.id)}`}
            >
              <button
                type="button"
                aria-label={t(isClosed ? "projects.expand" : "projects.collapse", { name: f.nome })}
                aria-expanded={kids ? !isClosed : undefined}
                disabled={!kids}
                onClick={() =>
                  setClosed((prev) => {
                    const next = new Set(prev);
                    if (next.has(f.id)) next.delete(f.id);
                    else next.add(f.id);
                    return next;
                  })
                }
                className="flex size-6 shrink-0 items-center justify-center text-muted disabled:opacity-0"
              >
                <ChevronRight size={14} className={isClosed ? "" : "rotate-90"} aria-hidden />
              </button>
              <button
                type="button"
                aria-current={current === f.id ? "true" : undefined}
                onClick={() => onSelect(f.id)}
                className="flex min-w-0 flex-1 items-center gap-1.5 py-1 text-left"
              >
                {current === f.id ? (
                  <FolderOpen size={14} aria-hidden />
                ) : (
                  <Folder size={14} aria-hidden />
                )}
                <span className="truncate">{f.nome}</span>
                <span className="ml-auto pr-1 text-[12px] text-muted">{direct(f.id)}</span>
              </button>
              <Dropdown.Root>
                <Dropdown.Trigger
                  aria-label={t("projects.folderActions", { name: f.nome })}
                  className="mr-1 flex size-6 items-center justify-center rounded-ui text-muted opacity-0 hover:bg-surface-2 focus:opacity-100 group-hover:opacity-100"
                >
                  <Ellipsis size={14} aria-hidden />
                </Dropdown.Trigger>
                <Dropdown.Portal>
                  <Dropdown.Content
                    align="end"
                    sideOffset={2}
                    className="z-30 min-w-44 rounded-ui border border-border bg-surface p-1 shadow-lg"
                  >
                    <Dropdown.Item className={menuItem} onSelect={() => onNewFolder(f.id)}>
                      {t("projects.newSubfolder")}
                    </Dropdown.Item>
                    <Dropdown.Item className={menuItem} onSelect={() => onRename(f)}>
                      {t("projects.renameFolder")}
                    </Dropdown.Item>
                    <Dropdown.Item className={menuItem} onSelect={() => onDelete(f)}>
                      {t("projects.deleteFolder")}
                    </Dropdown.Item>
                  </Dropdown.Content>
                </Dropdown.Portal>
              </Dropdown.Root>
            </div>
            {kids && !isClosed && level(f.id, depth + 1)}
          </li>
        );
      })}
    </ul>
  );

  return (
    <nav aria-label={t("projects.folders")} className="text-[14px]">
      <div
        {...target(null)}
        className={`flex items-center rounded-ui ${current === null ? "bg-surface" : "hover:bg-surface"} ${highlight(null)}`}
      >
        <button
          type="button"
          aria-current={current === null ? "true" : undefined}
          onClick={() => onSelect(null)}
          className="flex min-w-0 flex-1 items-center gap-1.5 px-2 py-1 text-left font-medium"
        >
          <Folder size={14} aria-hidden />
          {t("projects.rootName")}
          <span className="ml-auto text-[12px] font-normal text-muted">{direct(null)}</span>
        </button>
      </div>
      {level(null, 0)}
    </nav>
  );
}
