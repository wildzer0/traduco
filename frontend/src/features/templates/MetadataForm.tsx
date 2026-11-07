import { useState } from "react";
import { type ProjectRevision, patchProject } from "../../lib/api";
import { useT } from "../../lib/i18n";

/** Project metadata (the values of the template's {{fields}}) and the revision history. */
export function MetadataForm({
  projectId,
  fields,
  metadata,
  revisions,
  onSaved,
}: {
  projectId: string;
  fields: string[];
  metadata: Record<string, string>;
  revisions: ProjectRevision[];
  onSaved: () => void;
}) {
  const t = useT();
  const keys = [...new Set([...fields, ...Object.keys(metadata)])];
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(keys.map((k) => [k, String(metadata[k] ?? "")])),
  );
  const [rows, setRows] = useState<ProjectRevision[]>(revisions);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const input = "min-w-0 rounded-ui border border-border bg-bg px-2 py-1";

  const save = async () => {
    setError(null);
    setSaved(false);
    try {
      const filled = Object.fromEntries(Object.entries(values).filter(([, v]) => v.trim() !== ""));
      await patchProject(projectId, {
        metadati: filled,
        revisioni: rows.filter((r) => r.rev.trim() && r.data),
      });
      setSaved(true);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <details className="mt-4" open={fields.length > 0}>
      <summary className="cursor-pointer text-sm font-semibold">{t("metadata.title")}</summary>
      <div className="mt-2 grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1">
        {keys.map((k) => (
          <label key={k} className="contents">
            <span className="text-[13px]">{k}</span>
            <input
              className={input}
              aria-label={k}
              value={values[k] ?? ""}
              onChange={(e) => setValues({ ...values, [k]: e.target.value })}
            />
          </label>
        ))}
      </div>
      <h4 className="m-0 mt-3 text-[13px] font-semibold">{t("metadata.revisions")}</h4>
      {rows.map((r, i) => (
        // biome-ignore lint/suspicious/noArrayIndexKey: rows have no identity until saved
        <div key={i} className="mt-1 flex gap-1">
          <input
            className={`${input} w-14`}
            aria-label={t("metadata.rev")}
            value={r.rev}
            onChange={(e) =>
              setRows(rows.map((x, n) => (n === i ? { ...x, rev: e.target.value } : x)))
            }
          />
          <input
            className={`${input} w-32`}
            type="date"
            aria-label={t("metadata.date")}
            value={r.data}
            onChange={(e) =>
              setRows(rows.map((x, n) => (n === i ? { ...x, data: e.target.value } : x)))
            }
          />
          <input
            className={`${input} flex-1`}
            aria-label={t("metadata.description")}
            value={r.descrizione}
            onChange={(e) =>
              setRows(rows.map((x, n) => (n === i ? { ...x, descrizione: e.target.value } : x)))
            }
          />
          <button
            type="button"
            aria-label={t("metadata.removeRevision")}
            className="px-1"
            onClick={() => setRows(rows.filter((_, n) => n !== i))}
          >
            ×
          </button>
        </div>
      ))}
      <div className="mt-2 flex items-center gap-2">
        <button
          type="button"
          className="rounded-ui border border-border px-2 py-1 hover:bg-surface-2"
          onClick={() =>
            setRows([
              ...rows,
              { rev: "", data: new Date().toISOString().slice(0, 10), descrizione: "" },
            ])
          }
        >
          {t("metadata.addRevision")}
        </button>
        <button
          type="button"
          className="rounded-ui bg-accent px-3 py-1 text-accent-fg"
          onClick={() => void save()}
        >
          {t("metadata.save")}
        </button>
        {saved && <span className="text-[13px] text-green">{t("metadata.saved")}</span>}
      </div>
      {error && (
        <p role="alert" className="m-0 mt-1 text-[13px] text-red">
          {error}
        </p>
      )}
    </details>
  );
}
