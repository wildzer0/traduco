import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { getTranslation } from "../../lib/api";
import { onFileEvent } from "../../lib/file-events";
import type { TranslationView } from "../../lib/types";

export const translationKey = (projectId: string, path: string) =>
  ["translation", projectId, path] as const;

/**
 * Translation of the open section. Refetched (debounced) when the server reports progress on it,
 * after a reconnection, and when the file changes on disk.
 */
export function useTranslation(projectId: string, path: string | null) {
  const qc = useQueryClient();
  const query = useQuery<TranslationView>({
    queryKey: translationKey(projectId, path ?? ""),
    queryFn: () => getTranslation(projectId, path as string),
    enabled: path !== null,
    retry: false,
  });
  useEffect(() => {
    if (!path) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const refresh = () => {
      clearTimeout(timer);
      timer = setTimeout(
        () => void qc.invalidateQueries({ queryKey: translationKey(projectId, path) }),
        150,
      );
    };
    const off = onFileEvent((e) => {
      const mine = e.path === path;
      if (
        (mine && (e.type === "segment.queued" || e.type === "segment.updated")) ||
        e.type === "hello" ||
        (mine && e.type === "file.changed")
      )
        refresh();
    });
    return () => {
      clearTimeout(timer);
      off();
    };
  }, [qc, projectId, path]);
  return query;
}
