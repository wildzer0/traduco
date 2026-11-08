import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Drawer } from "../../components/Drawer";
import { decideProposal, getImport, startImport } from "../../lib/api";
import { useT } from "../../lib/i18n";
import type { ImportJob, ImportProposal } from "../../lib/types";
import { useView } from "../../lib/view-store";

const STEPS = new Set(["read", "align", "translate", "save"]);

/** Revised-document import (RF-65, RF-66): proposals per section, accepted one by one. */
export function ImportPanel({ projectId }: { projectId: string }) {
  const t = useT();
  const close = useView((s) => s.setImportOpen);
  const queryClient = useQueryClient();
  const [job, setJob] = useState<ImportJob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  const upload = async (file: File) => {
    setError(null);
    setEdits({});
    try {
      let current = await startImport(projectId, file);
      setJob(current);
      while (current.state === "running") {
        await new Promise((resolve) => setTimeout(resolve, 500));
        current = await getImport(projectId, current.id);
        setJob(current);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const patch = (done: ImportProposal) =>
    setJob((j) =>
      j ? { ...j, proposals: j.proposals.map((p) => (p.id === done.id ? done : p)) } : j,
    );

  const decide = async (p: ImportProposal, action: "accept" | "reject") => {
    if (!job) return;
    setBusy(p.id);
    setError(null);
    try {
      patch(
        await decideProposal(
          projectId,
          job.id,
          p.id,
          action,
          action === "accept" ? (edits[p.id] ?? p.proposed_source) : undefined,
        ),
      );
      if (action === "accept") void queryClient.invalidateQueries();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const acceptSection = async (items: ImportProposal[]) => {
    for (const p of items)
      if (p.status === "pending" && p.applicable && !p.stale) await decide(p, "accept");
  };

  const sections = new Map<string, ImportProposal[]>();
  for (const p of job?.proposals ?? [])
    sections.set(p.section, [...(sections.get(p.section) ?? []), p]);
  const area = "mt-1 w-full rounded-ui border border-border bg-bg px-2 py-1 text-[13px]";

  return (
    <Drawer title={t("import.title")} onClose={() => close(false)} width={640}>
      {(!job || job.state === "failed") && (
        <p className="mt-3 text-[13px] text-muted">{t("import.intro")}</p>
      )}
      {job?.state !== "running" && (
        <label className="mt-3 inline-block cursor-pointer self-start rounded-ui bg-accent px-3 py-1.5 text-accent-fg">
          {job ? t("import.another") : t("import.choose")}
          <input
            type="file"
            accept=".docx"
            className="sr-only"
            onChange={(e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (file) void upload(file);
            }}
          />
        </label>
      )}

      {job?.state === "running" && (
        <div className="mt-3" role="status">
          <div className="h-2 overflow-hidden rounded-full bg-surface-2">
            <div
              className="h-full bg-accent transition-all"
              style={{ width: `${job.progress}%` }}
            />
          </div>
          <p className="m-0 mt-1 text-[13px] text-muted">
            {STEPS.has(job.message)
              ? t(`import.step.${job.message}` as "import.step.read")
              : t("import.running")}
          </p>
        </div>
      )}

      {(error || job?.state === "failed") && (
        <div role="alert" className="mt-3 text-red">
          <p className="m-0 font-medium">{t("import.failed")}</p>
          <p className="m-0 mt-1 text-[13px]">{error ?? job?.error?.message}</p>
        </div>
      )}

      {job?.warnings.map((w) => (
        <p key={w} className="m-0 mt-2 text-[13px] text-amber">
          {w}
        </p>
      ))}

      {job?.state === "done" &&
        (job.proposals.length === 0 ? (
          <p className="mt-3 text-green" role="status">
            {t("import.none")}
          </p>
        ) : (
          <p className="mt-3 text-[13px] text-muted">
            {t("import.summary", { count: job.proposals.length })}
          </p>
        ))}

      {[...sections.entries()].map(([path, items]) => (
        <section key={path} className="mt-4" aria-label={items[0]?.section_title}>
          <div className="flex items-center justify-between gap-2">
            <h3 className="m-0 text-[14px] font-semibold">{items[0]?.section_title}</h3>
            {items.filter((p) => p.status === "pending" && p.applicable && !p.stale).length > 1 && (
              <button
                type="button"
                className="rounded-ui border border-border px-2 py-0.5 text-[12px] hover:bg-surface-2"
                onClick={() => void acceptSection(items)}
              >
                {t("import.acceptAll")}
              </button>
            )}
          </div>
          {items.map((p) => (
            <article
              key={p.id}
              className="mt-2 rounded-ui border border-border p-2"
              data-testid="proposal"
            >
              <p className="m-0 text-[12px] font-medium uppercase text-muted">
                {t(`import.kind.${p.kind}` as "import.kind.modified")}
                {p.tracked && ` · ${t("import.tracked", { authors: p.authors.join(", ") || "?" })}`}
              </p>
              {p.stale && <p className="m-0 mt-1 text-[12px] text-amber">{t("import.stale")}</p>}
              {!p.applicable && (
                <p className="m-0 mt-1 text-[12px] text-amber">{t("import.notApplicable")}</p>
              )}
              {p.kind !== "added" && (
                <p className="m-0 mt-1 text-[13px]">
                  <span className="text-muted">{t("import.current")}: </span>
                  {p.current_source || p.old}
                </p>
              )}
              {p.kind !== "deleted" && (
                <>
                  <label className="mt-1 block text-[12px] text-muted">
                    {t("import.proposal")}
                    <textarea
                      className={area}
                      rows={3}
                      value={edits[p.id] ?? p.proposed_source}
                      disabled={p.status !== "pending" || !p.applicable}
                      onChange={(e) => setEdits({ ...edits, [p.id]: e.target.value })}
                    />
                  </label>
                  <p className="m-0 mt-1 text-[12px] text-muted">
                    {t("import.client")}: {p.new}
                  </p>
                </>
              )}
              {p.note && p.applicable && (
                <p className="m-0 mt-1 text-[12px] text-amber">{p.note}</p>
              )}
              <div className="mt-2 flex items-center gap-2">
                {p.status === "pending" || p.status === "failed" ? (
                  <>
                    <button
                      type="button"
                      disabled={busy === p.id || !p.applicable}
                      onClick={() => void decide(p, "accept")}
                      className="rounded-ui bg-accent px-2 py-1 text-accent-fg disabled:opacity-50"
                    >
                      {t("import.accept")}
                    </button>
                    <button
                      type="button"
                      disabled={busy === p.id}
                      onClick={() => void decide(p, "reject")}
                      className="rounded-ui border border-border px-2 py-1 hover:bg-surface-2"
                    >
                      {t("import.reject")}
                    </button>
                  </>
                ) : (
                  <span className={p.status === "accepted" ? "text-green" : "text-muted"}>
                    {t(p.status === "accepted" ? "import.accepted" : "import.rejected")}
                  </span>
                )}
              </div>
            </article>
          ))}
        </section>
      ))}
    </Drawer>
  );
}
