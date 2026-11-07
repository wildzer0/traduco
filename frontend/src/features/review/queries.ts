import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { getReview } from "../../lib/api";
import { onFileEvent } from "../../lib/file-events";
import { reviewKey } from "../preview/segment-actions";

/** Every translated segment of the project; refreshed (debounced) while translation progresses. */
export function useReview(projectId: string) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: reviewKey(projectId),
    queryFn: () => getReview(projectId),
    retry: false,
  });
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const off = onFileEvent((e) => {
      if (e.type === "segment.updated" || e.type === "file.changed" || e.type === "hello") {
        clearTimeout(timer);
        timer = setTimeout(
          () => void qc.invalidateQueries({ queryKey: reviewKey(projectId) }),
          400,
        );
      }
    });
    return () => {
      clearTimeout(timer);
      off();
    };
  }, [qc, projectId]);
  return query;
}
