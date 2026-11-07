import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { getTranslation } from "../../lib/api";
import { onFileEvent } from "../../lib/file-events";
import { usePreview } from "../../lib/preview-store";
import type { TranslationView } from "../../lib/types";

/** Prefix shared by every language of a section: what to invalidate after a change. */
export const translationPrefix = (projectId: string, path: string) =>
  ["translation", projectId, path] as const;

/** The language is the last element, so invalidating by (project, path) reaches all of them. */
export const translationKey = (projectId: string, path: string, lang: string | null = null) =>
  ["translation", projectId, path, lang] as const;

/**
 * Translation of the open section. Refetched (debounced) when the server reports progress on it,
 * after a reconnection, and when the file changes on disk.
 */
export function useTranslation(projectId: string, path: string | null) {
  const qc = useQueryClient();
  const language = usePreview((s) => s.language);
  const query = useQuery<TranslationView>({
    queryKey: translationKey(projectId, path ?? "", language),
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
        () => void qc.invalidateQueries({ queryKey: translationPrefix(projectId, path) }),
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
