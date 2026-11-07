import type { TreeNode } from "../lib/types";

/** Chapters and section leading to ``path`` (for the breadcrumb). Empty if not found. */
export function findTrail(nodes: TreeNode[], path: string | null): TreeNode[] {
  if (!path) return [];
  for (const node of nodes) {
    if (node.path === path) return [node];
    const inner = findTrail(node.children, path);
    if (inner.length) return [node, ...inner];
  }
  return [];
}
