import { useQueryClient } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { putSegment } from "../../lib/api";
import { useT } from "../../lib/i18n";
import { useNotices } from "../../lib/notices";
import type { ReviewRow, SegmentStatus } from "../../lib/types";
import { type ReviewFilter, useView } from "../../lib/view-store";
import { reviewKey } from "../preview/segment-actions";
import { translationPrefix } from "../preview/translation";
import { useReview } from "./queries";

const FILTERS: ReviewFilter[] = [
  "all",
  "needs_review",
  "queued",
  "translated",
  "approved",
  "diverged",
  "locked",
];

export function matches(row: ReviewRow, filter: ReviewFilter): boolean {
  if (filter === "all") return true;
  if (filter === "locked") return row.locked;
  return row.status === filter;
}

/** Review mode: all segments of the project with filters and quick approval (docs/03-ui.md). */
export function ReviewTable({
  projectId,
  onOpen,
}: {
  projectId: string;
  onOpen: (path: string, key: string) => void;
}) {
  const t = useT();
  const qc = useQueryClient();
  const notify = useNotices((s) => s.show);
  const { data } = useReview(projectId);
  const filter = useView((s) => s.reviewFilter);
  const setFilter = useView((s) => s.setReviewFilter);
  const rows = (data?.segments ?? []).filter((r) => matches(r, filter));

  const approve = async (row: ReviewRow) => {
    try {
      await putSegment(projectId, row.path, row.key, { action: "approve" });
      await qc.invalidateQueries({ queryKey: reviewKey(projectId) });
      await qc.invalidateQueries({ queryKey: translationPrefix(projectId, row.path) });
    } catch (e) {
      notify(e instanceof Error ? e.message : String(e));
    }
  };

  const count = (f: ReviewFilter) => (data?.segments ?? []).filter((r) => matches(r, f)).length;

  return (
    <main aria-label={t("review.label")} className="flex min-w-0 flex-1 flex-col">
      <div
        role="toolbar"
        aria-label={t("review.filters")}
        className="flex flex-wrap gap-1 border-b border-border p-2"
      >
        {FILTERS.map((f) => (
          <button
            key={f}
            type="button"
            aria-pressed={filter === f}
            onClick={() => setFilter(f)}
            className={`rounded-ui px-2 py-1 ${filter === f ? "bg-accent text-accent-fg" : "hover:bg-surface-2"}`}
          >
            {t(`review.filter.${f}` as "review.filter.all")} · {count(f)}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <table className="w-full border-collapse text-left">
          <thead className="sticky top-0 bg-surface">
            <tr className="text-[12px] text-muted">
              <th className="p-2 font-medium">{t("review.section")}</th>
              <th className="p-2 font-medium">{t("review.source")}</th>
              <th className="p-2 font-medium">{t("review.translation")}</th>
              <th className="p-2 font-medium">{t("review.status")}</th>
              <th className="p-2" />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={`${row.path}:${row.key}`}
                className="border-t border-border align-top"
                data-testid="review-row"
              >
                <td className="p-2 text-muted">{row.section}</td>
                <td className="whitespace-pre-wrap p-2">{row.source}</td>
                <td className="whitespace-pre-wrap p-2">
                  {row.target}
                  {row.pending_target && (
                    <p className="m-0 mt-1 text-amber">
                      {t("segment.proposal")}: {row.pending_target}
                    </p>
                  )}
                </td>
                <td className="p-2">
                  <StatusLabel status={row.status} reason={row.reason} />
                  {row.locked && (
                    <Lock
                      size={12}
                      strokeWidth={1.5}
                      aria-label={t("segment.lock")}
                      className="ml-1 inline"
                    />
                  )}
                </td>
                <td className="p-2">
                  <div className="flex gap-1">
                    <button
                      type="button"
                      disabled={!row.target || row.status === "approved"}
                      onClick={() => void approve(row)}
                      className="rounded-ui border border-border px-2 py-0.5 hover:bg-surface-2 disabled:opacity-40"
                    >
                      {t("segment.approve")}
                    </button>
                    <button
                      type="button"
                      onClick={() => onOpen(row.path, row.key)}
                      className="rounded-ui px-2 py-0.5 hover:bg-surface-2"
                    >
                      {t("review.open")}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="p-4 text-muted">{t("review.empty")}</p>}
      </div>
    </main>
  );
}

function StatusLabel({ status, reason }: { status: SegmentStatus; reason: string }) {
  const t = useT();
  const color =
    status === "approved"
      ? "text-green"
      : status === "needs_review" || status === "diverged"
        ? "text-amber"
        : "text-muted";
  return (
    <span className={color} title={reason || undefined}>
      {t(`review.status.${status}` as "review.status.queued")}
      {reason && <span className="block text-[12px]">{reason}</span>}
    </span>
  );
}
