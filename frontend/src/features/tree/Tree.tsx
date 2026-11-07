import {
  closestCenter,
  DndContext,
  type DragEndEvent,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { useMemo, useState } from "react";
import { useT } from "../../lib/i18n";
import type { TreeNode } from "../../lib/types";
import { computeDrop, flattenTree } from "./dnd";
import { useTree } from "./queries";
import { TreeRow } from "./TreeRow";
import { useTreeActions } from "./useTreeActions";

interface Props {
  projectId: string;
  selected: string | null;
  onSelect: (path: string | null) => void;
}

function lastChapter(nodes: TreeNode[]): string | null {
  return nodes.length ? (nodes[nodes.length - 1]?.path ?? null) : null;
}

export function Tree({ projectId, selected, onSelect }: Props) {
  const t = useT();
  const { data: nodes = [], isLoading, isError } = useTree(projectId);
  const actions = useTreeActions(projectId, selected, onSelect);
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());
  const [renaming, setRenaming] = useState<string | null>(null);
  const [focused, setFocused] = useState<string | null>(null);

  const rows = useMemo(() => {
    const expanded = new Set<string>();
    const walk = (list: TreeNode[]) => {
      for (const n of list) {
        if (n.kind === "chapter") {
          if (!collapsed.has(n.path)) expanded.add(n.path);
          walk(n.children);
        }
      }
    };
    walk(nodes);
    return flattenTree(nodes, expanded);
  }, [nodes, collapsed]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const toggle = (path: string) =>
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (!next.delete(path)) next.add(path);
      return next;
    });

  const onDragEnd = ({ active, over }: DragEndEvent) => {
    if (!over) return;
    const drop = computeDrop(rows, String(active.id), String(over.id));
    if (drop) actions.move.mutate({ path: String(active.id), ...drop });
  };

  /** Chapter that receives "+ Section": the focused chapter, the chapter of the focused section, or the last one. */
  const targetChapter = (): string | null => {
    const f = focused ?? selected;
    if (f) {
      const row = rows.find((r) => r.node.path === f);
      if (row) return row.node.kind === "chapter" ? row.node.path : row.parent;
    }
    const last = [...rows].reverse().find((r) => r.node.kind === "chapter" && r.depth === 0);
    return last?.node.path ?? lastChapter(nodes);
  };

  const addSection = (parent: string | null = targetChapter()) => {
    if (!parent) return;
    actions.create.mutate(
      { kind: "section", title: t("tree.newSection"), parent },
      {
        onSuccess: (r) => {
          setFocused(parent);
          if (r.path) setRenaming(r.path);
        },
      },
    );
  };
  const addChapter = (parent: string | null = null) =>
    actions.create.mutate(
      { kind: "chapter", title: t("tree.newChapter"), parent },
      {
        onSuccess: (r) => {
          if (r.path) {
            setFocused(r.path); // the next "+ Section" goes into the chapter just created
            setRenaming(r.path);
          }
        },
      },
    );

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto">
        {isLoading && <p className="px-2 py-1 text-muted">{t("tree.loading")}</p>}
        {isError && (
          <p role="alert" className="px-2 py-1 text-red">
            {t("error.loadTree")}
          </p>
        )}
        {!isLoading && !isError && rows.length === 0 && (
          <p className="px-2 py-1 text-muted">{t("sidebar.empty")}</p>
        )}
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext
            items={rows.map((r) => r.node.path)}
            strategy={verticalListSortingStrategy}
          >
            <ul className="m-0 list-none p-0">
              {rows.map((row) => (
                <TreeRow
                  key={row.node.path}
                  row={row}
                  selected={row.node.path === selected}
                  expanded={!collapsed.has(row.node.path)}
                  renaming={renaming === row.node.path}
                  onActivate={() => {
                    setFocused(row.node.path);
                    if (row.node.kind === "chapter") toggle(row.node.path);
                    else onSelect(row.node.path);
                  }}
                  onToggle={() => toggle(row.node.path)}
                  onStartRename={() => setRenaming(row.node.path)}
                  onCommitRename={(title) => {
                    setRenaming(null);
                    if (title !== row.node.title)
                      actions.rename.mutate({ path: row.node.path, title });
                  }}
                  onCancelRename={() => setRenaming(null)}
                  onDelete={() => actions.remove.mutate(row.node.path)}
                  onAddSection={() => addSection(row.node.path)}
                  onAddSubchapter={() => addChapter(row.node.path)}
                />
              ))}
            </ul>
          </SortableContext>
        </DndContext>
      </div>
      <div className="flex gap-1 border-t border-border pt-2">
        <button
          type="button"
          onClick={() => addSection()}
          disabled={!targetChapter()}
          className="flex-1 rounded-ui px-2 py-1 text-left hover:bg-surface disabled:opacity-50"
        >
          {t("tree.addSection")}
        </button>
        <button
          type="button"
          onClick={() => addChapter()}
          className="rounded-ui px-2 py-1 hover:bg-surface"
        >
          {t("tree.addChapter")}
        </button>
      </div>
    </div>
  );
}
