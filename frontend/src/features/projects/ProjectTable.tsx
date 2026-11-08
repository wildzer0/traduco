import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { ArrowDown, ArrowUp, Ellipsis } from "lucide-react";
import { useT } from "../../lib/i18n";
import type { ProjectSummary } from "../../lib/types";
import { DRAG_TYPE } from "./FolderTree";
import { ago, type SortKey } from "./organize";

interface Props {
  projects: ProjectSummary[];
  /** Show where each project is (when looking at results from every folder). */
  showFolder: boolean;
  sort: { key: SortKey; direction: "asc" | "desc" };
  onSort: (key: SortKey) => void;
  locale: string;
  now: Date;
  onOpen: (project: ProjectSummary) => void;
  onDuplicate: (project: ProjectSummary) => void;
  onMove: (project: ProjectSummary) => void;
  onRename: (project: ProjectSummary) => void;
  onDelete: (project: ProjectSummary) => void;
}

const menuItem =
  "cursor-default rounded-ui px-2 py-1 outline-none data-[highlighted]:bg-accent-soft data-[highlighted]:text-accent";

/** The projects of a folder with what matters at a glance, sortable by every useful column. */
export function ProjectTable({
  projects,
  showFolder,
  sort,
  onSort,
  locale,
  now,
  onOpen,
  onDuplicate,
  onMove,
  onRename,
  onDelete,
}: Props) {
  const t = useT();
  const fullDate = (iso?: string) =>
    iso ? new Date(iso).toLocaleString(locale, { dateStyle: "medium", timeStyle: "short" }) : "";

  const header = (key: SortKey, label: string) => (
    <th
      scope="col"
      aria-sort={
        sort.key === key ? (sort.direction === "asc" ? "ascending" : "descending") : "none"
      }
      className="px-2 py-1.5 text-left font-medium"
    >
      <button
        type="button"
        onClick={() => onSort(key)}
        title={t("projects.sortBy", { column: label })}
        className="flex items-center gap-1 hover:text-fg"
      >
        {label}
        {sort.key === key &&
          (sort.direction === "asc" ? (
            <ArrowUp size={12} aria-hidden />
          ) : (
            <ArrowDown size={12} aria-hidden />
          ))}
      </button>
    </th>
  );
  const plainHeader = (label: string) => (
    <th scope="col" className="px-2 py-1.5 text-left font-medium">
      {label}
    </th>
  );

  return (
    <div className="overflow-hidden rounded-[10px] border border-border bg-surface">
      <table className="w-full border-collapse text-[14px]">
        <thead className="text-[12px] uppercase tracking-wide text-muted">
          <tr className="border-b border-border">
            {header("nome", t("projects.colName"))}
            {showFolder && plainHeader(t("projects.colFolder"))}
            {header("emissione", t("projects.colIssue"))}
            {header("autore", t("projects.colAuthor"))}
            {header("ultima_modifica", t("projects.colModified"))}
            {plainHeader(t("projects.colSections"))}
            {plainHeader(t("projects.colLanguages"))}
            <th scope="col" className="w-8 px-1">
              <span className="sr-only">{t("projects.colActions")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {projects.map((p) => (
            <tr
              key={p.id}
              draggable
              onDragStart={(e) => {
                e.dataTransfer.setData(DRAG_TYPE, p.id);
                e.dataTransfer.effectAllowed = "move";
              }}
              className="group border-b border-border/60 hover:bg-surface-2"
              data-testid="project-row"
            >
              <td className="max-w-[28ch] px-2 py-2">
                <button
                  type="button"
                  onClick={() => onOpen(p)}
                  className="block max-w-full truncate text-left font-medium hover:text-accent"
                >
                  {p.nome}
                </button>
              </td>
              {showFolder && (
                <td className="px-2 py-2 text-muted">
                  {p.percorso && p.percorso.length > 0
                    ? p.percorso.join(" › ")
                    : t("projects.rootName")}
                </td>
              )}
              <td className="px-2 py-2" title={p.emissione_data}>
                {p.emissione ? (
                  t("projects.issue", { rev: p.emissione })
                ) : (
                  <span className="text-muted">{t("projects.noIssue")}</span>
                )}
              </td>
              <td className="px-2 py-2">{p.autore || <span className="text-muted">—</span>}</td>
              <td className="px-2 py-2" title={fullDate(p.ultima_modifica)}>
                {ago(p.ultima_modifica, now, locale) || <span className="text-muted">—</span>}
              </td>
              <td className="px-2 py-2 tabular-nums">{p.sezioni ?? 0}</td>
              <td className="px-2 py-2 text-muted">
                {p.lingua_sorgente} →{" "}
                {(p.lingue?.length ? p.lingue : [p.lingua_ufficiale]).join(", ")}
              </td>
              <td className="px-1 py-1">
                <Dropdown.Root>
                  <Dropdown.Trigger
                    aria-label={t("projects.actions", { name: p.nome })}
                    className="flex size-7 items-center justify-center rounded-ui text-muted hover:bg-surface hover:text-fg"
                  >
                    <Ellipsis size={16} aria-hidden />
                  </Dropdown.Trigger>
                  <Dropdown.Portal>
                    <Dropdown.Content
                      align="end"
                      sideOffset={2}
                      className="z-30 min-w-44 rounded-ui border border-border bg-surface p-1 shadow-lg"
                    >
                      <Dropdown.Item className={menuItem} onSelect={() => onOpen(p)}>
                        {t("projects.open")}
                      </Dropdown.Item>
                      <Dropdown.Item className={menuItem} onSelect={() => onDuplicate(p)}>
                        {t("projects.duplicate")}
                      </Dropdown.Item>
                      <Dropdown.Item className={menuItem} onSelect={() => onMove(p)}>
                        {t("projects.move")}
                      </Dropdown.Item>
                      <Dropdown.Item className={menuItem} onSelect={() => onRename(p)}>
                        {t("projects.rename")}
                      </Dropdown.Item>
                      <Dropdown.Separator className="my-1 h-px bg-border" />
                      <Dropdown.Item
                        className={`${menuItem} text-red`}
                        onSelect={() => onDelete(p)}
                      >
                        {t("projects.delete")}
                      </Dropdown.Item>
                    </Dropdown.Content>
                  </Dropdown.Portal>
                </Dropdown.Root>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
