import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import * as ContextMenu from "@radix-ui/react-context-menu";
import { ChevronDown, ChevronRight, GripVertical } from "lucide-react";
import { useState } from "react";
import { useT } from "../../lib/i18n";
import type { Row } from "./dnd";

interface Props {
  row: Row;
  selected: boolean;
  expanded: boolean;
  /** Skeleton problem of this node (empty, out of order…), shown as an amber dot. */
  flag?: string;
  renaming: boolean;
  onActivate: () => void;
  onToggle: () => void;
  onStartRename: () => void;
  onCommitRename: (title: string) => void;
  onCancelRename: () => void;
  onDelete: () => void;
  onAddSection: () => void;
  onAddSubchapter: () => void;
}

const menuItem =
  "cursor-default rounded-ui px-2 py-1 outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-fg";

export function TreeRow(props: Props) {
  const { row, selected, expanded, renaming } = props;
  const t = useT();
  const isChapter = row.node.kind === "chapter";
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: row.node.path });
  const [draft, setDraft] = useState(row.node.title);

  return (
    <ContextMenu.Root>
      <ContextMenu.Trigger asChild>
        <li
          ref={setNodeRef}
          style={{
            transform: CSS.Transform.toString(transform),
            transition,
            paddingLeft: row.depth * 14,
          }}
          className={`group flex items-center rounded-ui ${selected ? "bg-surface" : "hover:bg-surface"} ${isDragging ? "opacity-50" : ""}`}
        >
          <button
            ref={setActivatorNodeRef}
            type="button"
            aria-label={t("tree.dragHandle")}
            title={t("tree.dragHandle")}
            className="cursor-grab px-0.5 text-muted opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
            {...attributes}
            {...listeners}
          >
            <GripVertical size={14} strokeWidth={1.5} aria-hidden />
          </button>
          {isChapter ? (
            <button
              type="button"
              aria-label={expanded ? t("tree.collapse") : t("tree.expand")}
              aria-expanded={expanded}
              onClick={props.onToggle}
              className="px-0.5 text-muted"
            >
              {expanded ? (
                <ChevronDown size={14} strokeWidth={1.5} aria-hidden />
              ) : (
                <ChevronRight size={14} strokeWidth={1.5} aria-hidden />
              )}
            </button>
          ) : (
            <span className="w-[18px]" />
          )}
          {renaming ? (
            <input
              // biome-ignore lint/a11y/noAutofocus: the input appears only after an explicit rename action
              autoFocus
              aria-label={t("tree.rename")}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onFocus={(e) => e.currentTarget.select()}
              onBlur={() =>
                draft.trim() ? props.onCommitRename(draft.trim()) : props.onCancelRename()
              }
              onKeyDown={(e) => {
                if (e.key === "Enter") props.onCommitRename(draft.trim() || row.node.title);
                if (e.key === "Escape") props.onCancelRename();
              }}
              className="min-w-0 flex-1 rounded-ui border border-accent bg-surface px-1"
            />
          ) : (
            <button
              type="button"
              onClick={props.onActivate}
              aria-current={selected ? "true" : undefined}
              onDoubleClick={props.onStartRename}
              className={`min-w-0 flex-1 truncate px-1 py-1 text-left ${isChapter ? "font-medium" : ""}`}
            >
              {row.node.title}
            </button>
          )}
          {props.flag && !renaming && (
            <span
              role="img"
              data-testid="skeleton-flag"
              aria-label={t("skeleton.flag", {
                status: t(`skeleton.status.${props.flag}` as "skeleton.status.missing"),
              })}
              title={t("skeleton.flag", {
                status: t(`skeleton.status.${props.flag}` as "skeleton.status.missing"),
              })}
              className="mr-1 size-2 shrink-0 rounded-full bg-amber"
            />
          )}
        </li>
      </ContextMenu.Trigger>
      <ContextMenu.Portal>
        <ContextMenu.Content className="z-20 min-w-44 rounded-ui border border-border bg-surface p-1 shadow-lg">
          {isChapter && (
            <>
              <ContextMenu.Item className={menuItem} onSelect={props.onAddSection}>
                {t("tree.newSectionHere")}
              </ContextMenu.Item>
              <ContextMenu.Item className={menuItem} onSelect={props.onAddSubchapter}>
                {t("tree.newSubchapter")}
              </ContextMenu.Item>
            </>
          )}
          <ContextMenu.Item
            className={menuItem}
            onSelect={() => {
              setDraft(row.node.title);
              props.onStartRename();
            }}
          >
            {t("tree.rename")}
          </ContextMenu.Item>
          <ContextMenu.Item className={menuItem} onSelect={props.onDelete}>
            {t("tree.delete")}
          </ContextMenu.Item>
        </ContextMenu.Content>
      </ContextMenu.Portal>
    </ContextMenu.Root>
  );
}
