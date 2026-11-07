import { isInside, parentOf } from "../../lib/paths";
import type { TreeNode } from "../../lib/types";

export interface Row {
  node: TreeNode;
  depth: number;
  /** Parent chapter path, ``null`` for top-level chapters. */
  parent: string | null;
  /** Position among its siblings in the real tree (not only the visible ones). */
  index: number;
}

/** Visible rows in display order; children of collapsed chapters are hidden. */
export function flattenTree(nodes: TreeNode[], expanded: ReadonlySet<string>): Row[] {
  const rows: Row[] = [];
  const walk = (list: TreeNode[], depth: number, parent: string | null) => {
    list.forEach((node, index) => {
      rows.push({ node, depth, parent, index });
      if (node.kind === "chapter" && expanded.has(node.path))
        walk(node.children, depth + 1, node.path);
    });
  };
  walk(nodes, 0, null);
  return rows;
}

export interface Drop {
  parent: string | null;
  index: number;
}

/**
 * Where a dragged row lands when dropped on another row:
 * - a section over a chapter goes inside that chapter, at the top;
 * - otherwise it takes the position of the row it was dropped on, in that row's parent
 *   (so dragging down puts it after the target, dragging up puts it before).
 */
export function computeDrop(rows: Row[], activePath: string, overPath: string): Drop | null {
  if (activePath === overPath) return null;
  const active = rows.find((r) => r.node.path === activePath);
  const over = rows.find((r) => r.node.path === overPath);
  if (!active || !over) return null;
  if (active.node.kind === "chapter" && isInside(over.node.path, active.node.path)) return null;

  if (active.node.kind === "section" && over.node.kind === "chapter") {
    return parentOf(active.node.path) === over.node.path && active.index === 0
      ? null
      : { parent: over.node.path, index: 0 };
  }
  if (active.node.kind === "section" && over.parent === null) return null; // sections need a chapter
  return { parent: over.parent, index: over.index };
}
