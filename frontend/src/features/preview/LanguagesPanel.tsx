import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { type AdditionalLanguage, listLanguages, setAdditionalLanguages } from "../../lib/api";
import { useT } from "../../lib/i18n";
import { usePreview } from "../../lib/preview-store";
import type { Tone } from "../../lib/types";
import { useView } from "../../lib/view-store";
import { keys } from "../tree/queries";

const COMMON = ["de", "fr", "es", "pt", "nl", "pl", "ro", "sv", "da", "cs", "tr", "ja", "zh"];

/** Additional target languages of the project: tone and date format of their own (RF-21b…d). */
export function LanguagesPanel({ projectId }: { projectId: string }) {
  const t = useT();
  const qc = useQueryClient();
  const close = useView((s) => s.setLanguagesOpen);
  const { data } = useQuery({
    queryKey: ["languages", projectId],
    queryFn: () => listLanguages(projectId),
  });
  const [rows, setRows] = useState<AdditionalLanguage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const current: AdditionalLanguage[] =
    rows ??
    (data ?? [])
      .filter((l) => l.role === "additional")
      .map((l) => ({
        codice: l.code,
        ...(l.tono ? { tono: l.tono } : {}),
        ...(l.formato_date ? { formato_date: l.formato_date } : {}),
      }));

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  const update = (index: number, patch: Partial<AdditionalLanguage>) =>
    setRows(current.map((r, i) => (i === index ? { ...r, ...patch } : r)));

  const save = async () => {
    setError(null);
    setSaved(false);
    try {
      await setAdditionalLanguages(
        projectId,
        current
          .filter((r) => r.codice.trim())
          .map((r) => ({ ...r, codice: r.codice.trim().toLowerCase() })),
      );
      const shown = usePreview.getState().language;
      if (shown && !current.some((r) => r.codice === shown))
        usePreview.getState().setLanguage(null);
      setRows(null);
      setSaved(true);
      await qc.invalidateQueries({ queryKey: ["languages", projectId] });
      await qc.invalidateQueries({ queryKey: keys.projects });
      await qc.invalidateQueries({ queryKey: ["project", projectId] });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const field = "rounded-ui border border-border bg-bg px-2 py-1";
  return (
    <aside
      role="dialog"
      aria-label={t("languages.manage")}
      className="fixed inset-y-0 right-0 z-10 flex w-[460px] max-w-full flex-col overflow-y-auto border-l border-border bg-surface p-4 shadow-lg"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">{t("languages.manage")}</h2>
        <button
          type="button"
          onClick={() => close(false)}
          className="rounded-ui px-2 py-1 hover:bg-surface-2"
        >
          {t("issues.close")}
        </button>
      </div>
      <p className="mt-2 text-[13px] text-muted">{t("languages.intro")}</p>
      <datalist id="common-languages">
        {COMMON.map((c) => (
          <option key={c} value={c} />
        ))}
      </datalist>
      {current.length === 0 && <p className="text-muted">{t("languages.none")}</p>}
      <ul className="m-0 mt-2 list-none space-y-2 p-0">
        {current.map((row, index) => (
          <li
            // biome-ignore lint/suspicious/noArrayIndexKey: rows have no identity until saved; a key made of the code would lose focus while typing
            key={index}
            className="flex flex-wrap items-center gap-2 rounded-ui border border-border p-2"
          >
            <input
              className={`${field} w-16`}
              list="common-languages"
              aria-label={t("languages.code")}
              value={row.codice}
              onChange={(e) => update(index, { codice: e.target.value })}
            />
            <select
              className={field}
              aria-label={t("languages.tone")}
              value={row.tono ?? ""}
              onChange={(e) => {
                const tone = e.target.value as Tone | "";
                const { tono: _drop, ...rest } = row;
                setRows(
                  current.map((r, i) =>
                    i === index ? (tone ? { ...rest, tono: tone } : rest) : r,
                  ),
                );
              }}
            >
              <option value="">{t("languages.toneInherit")}</option>
              <option value="formale">formale</option>
              <option value="neutro">neutro</option>
              <option value="informale">informale</option>
            </select>
            <input
              className={`${field} w-32`}
              aria-label={t("languages.dateFormat")}
              placeholder="dd.MM.yyyy"
              value={row.formato_date ?? ""}
              onChange={(e) => update(index, { formato_date: e.target.value })}
            />
            <button
              type="button"
              aria-label={t("languages.remove")}
              className="ml-auto rounded-ui p-1 hover:bg-surface-2"
              onClick={() => setRows(current.filter((_, i) => i !== index))}
            >
              <Trash2 size={14} strokeWidth={1.5} aria-hidden />
            </button>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          className="rounded-ui border border-border px-3 py-1.5 hover:bg-surface-2"
          onClick={() => setRows([...current, { codice: "" }])}
        >
          {t("languages.add")}
        </button>
        <button
          type="button"
          className="rounded-ui bg-accent px-3 py-1.5 text-accent-fg"
          onClick={() => void save()}
        >
          {t("languages.save")}
        </button>
        {saved && <span className="text-[13px] text-green">{t("languages.saved")}</span>}
      </div>
      {error && (
        <p role="alert" className="m-0 mt-2 text-[13px] text-red">
          {error}
        </p>
      )}
    </aside>
  );
}
