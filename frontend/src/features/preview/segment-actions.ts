import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useMemo } from "react";
import {
  applySource,
  backTranslate,
  instructSegment,
  putSegment,
  type SegmentChange,
} from "../../lib/api";
import { recheckOpenFile } from "../../lib/file-events";
import { useNotices } from "../../lib/notices";
import { translationKey } from "./translation";

export const reviewKey = (projectId: string) => ["review", projectId] as const;

/** Author actions on one segment of the open section; each one refreshes the views it affects. */
export function useSegmentActions(projectId: string, path: string) {
  const qc = useQueryClient();
  const notify = useNotices((s) => s.show);

  const refresh = useCallback(async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: translationKey(projectId, path) }),
      qc.invalidateQueries({ queryKey: reviewKey(projectId) }),
    ]);
  }, [qc, projectId, path]);

  const guard = useCallback(
    async <T>(run: () => Promise<T>): Promise<T | null> => {
      try {
        return await run();
      } catch (e) {
        notify(e instanceof Error ? e.message : String(e));
        return null;
      }
    },
    [notify],
  );

  return useMemo(
    () => ({
      change: async (key: string, change: SegmentChange) => {
        const row = await guard(() => putSegment(projectId, path, key, change));
        await refresh();
        return row;
      },
      instruct: (key: string, instruction: string, alternatives = false) =>
        guard(() => instructSegment(projectId, path, key, instruction, alternatives)),
      backTranslate: (key: string) => guard(() => backTranslate(projectId, path, key)),
      applySource: async (key: string, text: string) => {
        const row = await guard(() => applySource(projectId, path, key, text));
        recheckOpenFile();
        await refresh();
        return row;
      },
    }),
    [guard, refresh, projectId, path],
  );
}
