import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useState } from "react";
import { createMissing } from "../../lib/api";
import { useT } from "../../lib/i18n";
import { useNotices } from "../../lib/notices";
import type { SkeletonItem } from "../../lib/types";
import { keys, useSkeleton } from "./queries";

/** Items the author has to look at: mandatory ones that are not in good shape. */
export function problems(items: SkeletonItem[]): SkeletonItem[] {
  return items.filter((i) => i.mandatory && i.status !== "ok");
}

export function SkeletonPanel({
  projectId,
  onSelect,
}: {
  projectId: string;
  onSelect: (path: string) => void;
}) {
  const t = useT();
  const qc = useQueryClient();
  const notify = useNotices((s) => s.show);
  const { data } = useSkeleton(projectId);
  const [open, setOpen] = useState(false);
  const fix = useMutation({
    mutationFn: () => createMissing(projectId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: keys.tree(projectId) });
      qc.invalidateQueries({ queryKey: keys.skeleton(projectId) });
    },
    onError: (e) => notify(e instanceof Error ? e.message : String(e)),
  });
  if (!data) return null;
  const bad = problems(data.items);
  const missing = bad.some((i) => i.status === "missing");
  return (
    <section aria-label={t("skeleton.title")} className="mt-2 border-t border-border pt-2">
      <button
        type="button"
        aria-expanded={open}
        title={t(open ? "skeleton.hide" : "skeleton.show")}
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-1 rounded-ui px-2 py-1 text-left hover:bg-surface"
      >
        {open ? (
          <ChevronDown size={14} strokeWidth={1.5} aria-hidden />
        ) : (
          <ChevronRight size={14} strokeWidth={1.5} aria-hidden />
        )}
        <span className="font-medium">{t("skeleton.title")}</span>
        <span
          data-testid="skeleton-summary"
          className={`ml-auto text-[12px] ${bad.length ? "text-amber" : "text-green"}`}
        >
          {bad.length ? t("skeleton.toFix", { count: bad.length }) : t("skeleton.conform")}
        </span>
      </button>
      {open && (
        <div className="px-2 pb-1">
          <ul className="m-0 max-h-48 list-none overflow-y-auto p-0">
            {bad.map((i) => (
              <li key={i.id} className="py-0.5">
                <button
                  type="button"
                  disabled={!i.path}
                  title={i.guide}
                  onClick={() => i.path && onSelect(i.path)}
                  className="flex w-full items-baseline gap-1 text-left enabled:hover:underline"
                >
                  <span className="truncate">{i.title}</span>
                  <span className="ml-auto shrink-0 text-[12px] text-amber">
                    {t(`skeleton.status.${i.status}` as "skeleton.status.missing")}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {data.extra.length > 0 && (
            <p className="mt-1 text-[12px] text-muted">
              {t("skeleton.extra", { count: data.extra.length })}
            </p>
          )}
          {missing && (
            <button
              type="button"
              disabled={fix.isPending}
              onClick={() => fix.mutate()}
              className="mt-1 w-full rounded-ui border border-border px-2 py-1 hover:bg-surface disabled:opacity-50"
            >
              {t("skeleton.createMissing")}
            </button>
          )}
        </div>
      )}
    </section>
  );
}
