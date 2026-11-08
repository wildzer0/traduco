import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Drawer } from "../../components/Drawer";
import {
  applyChanges,
  type ChangeRow,
  createIssue,
  generateChanges,
  getIssue,
  listIssues,
  saveChanges,
} from "../../lib/api";
import { useT } from "../../lib/i18n";
import { useView } from "../../lib/view-store";
import { ComparePanel } from "./ComparePanel";

const DRAFT = "bozza";

/** Issues (RF-80): freeze, browse, compare, and fill the revision table from the differences. */
export function IssuesPanel({ projectId }: { projectId: string }) {
  const t = useT();
  const qc = useQueryClient();
  const close = useView((s) => s.setIssuesOpen);
  const [rev, setRev] = useState("");
  const [description, setDescription] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [compare, setCompare] = useState<{ from: string; to: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { data: issues = [] } = useQuery({
    queryKey: ["issues", projectId],
    queryFn: () => listIssues(projectId),
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && !compare && close(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close, compare]);

  const freeze = async () => {
    setError(null);
    try {
      await createIssue(projectId, { rev: rev.trim(), descrizione: description });
      setRev("");
      setDescription("");
      await qc.invalidateQueries({ queryKey: ["issues", projectId] });
      await qc.invalidateQueries({ queryKey: ["project", projectId] });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const field = "w-full rounded-ui border border-border bg-bg px-2 py-1";
  return (
    <>
      <Drawer
        title={t("issues.title")}
        onClose={() => close(false)}
        width={460}
        closeOnEscape={!compare}
      >
        <p className="mt-2 text-[13px] text-muted">{t("issues.intro")}</p>

        <fieldset className="mt-2 border-0 p-0">
          <legend className="text-sm font-semibold">{t("issues.new")}</legend>
          <div className="mt-1 flex gap-2">
            <input
              className={`${field} w-20`}
              aria-label={t("issues.rev")}
              placeholder={t("issues.rev")}
              value={rev}
              onChange={(e) => setRev(e.target.value)}
            />
            <input
              className={field}
              aria-label={t("issues.description")}
              placeholder={t("issues.description")}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <button
              type="button"
              disabled={!rev.trim()}
              onClick={() => void freeze()}
              className="rounded-ui bg-accent px-3 py-1 text-accent-fg disabled:opacity-50"
            >
              {t("issues.freeze")}
            </button>
          </div>
        </fieldset>
        {error && (
          <p role="alert" className="m-0 mt-1 text-[13px] text-red">
            {error}
          </p>
        )}

        {issues.length === 0 && <p className="mt-4 text-muted">{t("issues.empty")}</p>}
        <ul className="m-0 mt-4 list-none space-y-2 p-0">
          {[...issues].reverse().map((issue, index, all) => {
            const previous = all[index + 1];
            return (
              <li key={issue.rev} className="rounded-ui border border-border p-2">
                <div className="flex items-baseline gap-2">
                  <strong>{issue.rev}</strong>
                  <span className="text-[12px] text-muted">
                    {issue.data} · {t("issues.sections", { count: issue.sections })}
                  </span>
                </div>
                {issue.descrizione && <p className="m-0 mt-1 text-[13px]">{issue.descrizione}</p>}
                <div className="mt-2 flex flex-wrap gap-2 text-[13px]">
                  <button
                    type="button"
                    className="rounded-ui border border-border px-2 py-0.5 hover:bg-surface-2"
                    onClick={() => setCompare({ from: issue.rev, to: DRAFT })}
                  >
                    {t("issues.compare")}
                  </button>
                  {previous && (
                    <button
                      type="button"
                      className="rounded-ui border border-border px-2 py-0.5 hover:bg-surface-2"
                      onClick={() => setCompare({ from: previous.rev, to: issue.rev })}
                    >
                      {t("issues.compareWith")}
                    </button>
                  )}
                  <button
                    type="button"
                    aria-expanded={open === issue.rev}
                    className="rounded-ui border border-border px-2 py-0.5 hover:bg-surface-2"
                    onClick={() => setOpen(open === issue.rev ? null : issue.rev)}
                  >
                    {t("issues.table")}
                  </button>
                </div>
                {open === issue.rev && <ChangeTable projectId={projectId} rev={issue.rev} />}
              </li>
            );
          })}
        </ul>
      </Drawer>
      {compare && (
        <ComparePanel
          projectId={projectId}
          from={compare.from}
          to={compare.to}
          onClose={() => setCompare(null)}
        />
      )}
    </>
  );
}

/** The change table of one issue: generated by the model, corrected by the author. */
function ChangeTable({ projectId, rev }: { projectId: string; rev: string }) {
  const t = useT();
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["issue", projectId, rev],
    queryFn: () => getIssue(projectId, rev),
  });
  const [rows, setRows] = useState<ChangeRow[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const shown = rows ?? data?.changes ?? [];

  const run = async (job: () => Promise<unknown>) => {
    setBusy(true);
    setNote(null);
    try {
      await job();
    } catch (e) {
      setNote(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-2">
      <button
        type="button"
        disabled={busy}
        className="rounded-ui bg-accent px-2 py-1 text-[13px] text-accent-fg disabled:opacity-50"
        onClick={() =>
          run(async () => {
            const made = await generateChanges(projectId, rev);
            setRows(made.changes);
            await qc.invalidateQueries({ queryKey: ["issues", projectId] });
          })
        }
      >
        {busy ? t("issues.generating") : t("issues.generate")}
      </button>
      {shown.length === 0 && data && (
        <p className="m-0 mt-2 text-[13px] text-muted">{t("issues.noChanges")}</p>
      )}
      {shown.map((row, i) => (
        <label key={row.path} className="mt-2 block text-[13px]">
          <span className="font-medium">{row.title}</span>
          <input
            className="mt-0.5 w-full rounded-ui border border-border bg-bg px-2 py-1"
            value={row.summary}
            onChange={(e) =>
              setRows(shown.map((r, n) => (n === i ? { ...r, summary: e.target.value } : r)))
            }
          />
        </label>
      ))}
      {shown.length > 0 && (
        <button
          type="button"
          disabled={busy}
          className="mt-2 rounded-ui border border-border px-2 py-1 text-[13px] hover:bg-surface-2"
          onClick={() =>
            run(async () => {
              await saveChanges(projectId, rev, shown);
              await applyChanges(projectId, rev);
              await qc.invalidateQueries({ queryKey: ["project", projectId] });
              setNote(t("issues.used"));
            })
          }
        >
          {t("issues.use")}
        </button>
      )}
      {note && (
        <p role="status" className="m-0 mt-1 text-[13px] text-muted">
          {note}
        </p>
      )}
    </div>
  );
}
