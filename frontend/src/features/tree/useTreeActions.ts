import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createNode, deleteNode, moveNode, renameNode } from "../../lib/api";
import { useT } from "../../lib/i18n";
import { useNotices } from "../../lib/notices";
import { isInside, remapPath } from "../../lib/paths";
import { keys } from "./queries";

/** Structure mutations. The open section follows renames/moves done by the server (renumbering). */
export function useTreeActions(
  projectId: string,
  selected: string | null,
  select: (path: string | null) => void,
) {
  const qc = useQueryClient();
  const t = useT();
  const notify = useNotices((s) => s.show);

  const refresh = () => qc.invalidateQueries({ queryKey: keys.tree(projectId) });
  const onError = (e: unknown) =>
    notify(t("error.generic", { message: e instanceof Error ? e.message : String(e) }));
  const follow = (renamed: Record<string, string>) => {
    if (!selected) return;
    const next = remapPath(selected, renamed);
    if (next !== selected) select(next);
  };

  const create = useMutation({
    mutationFn: (v: { kind: "chapter" | "section"; title: string; parent: string | null }) =>
      createNode(projectId, v),
    onSuccess: (r, v) => {
      refresh();
      if (v.kind === "section" && r.path) select(r.path);
    },
    onError,
  });

  const rename = useMutation({
    mutationFn: (v: { path: string; title: string }) => renameNode(projectId, v.path, v.title),
    onSuccess: (r) => {
      follow(r.renamed);
      refresh();
    },
    onError,
  });

  const move = useMutation({
    mutationFn: (v: { path: string; parent: string | null; index: number }) =>
      moveNode(projectId, v.path, v.parent, v.index),
    onSuccess: (r) => {
      follow(r.renamed);
      refresh();
    },
    onError: (e) => {
      onError(e);
      refresh();
    },
  });

  const remove = useMutation({
    mutationFn: (path: string) => deleteNode(projectId, path),
    onSuccess: (_r, path) => {
      if (selected && isInside(selected, path)) select(null);
      refresh();
    },
    onError,
  });

  return { create, rename, move, remove };
}
