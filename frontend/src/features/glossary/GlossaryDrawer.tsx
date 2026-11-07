import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getGlossary, glossaryExportUrl, importGlossary, putGlossary } from "../../lib/api";
import { useT } from "../../lib/i18n";
import { useNotices } from "../../lib/notices";
import type { GlossaryEntry } from "../../lib/types";
import { useView } from "../../lib/view-store";
import { useProjects } from "../tree/queries";

const blank = (): GlossaryEntry => ({
  sorgente: "",
  destinazione: {},
  vietati: {},
  non_tradurre: false,
  note: "",
});

export const glossaryKey = (id: string) => ["glossary", id] as const;

/** Project glossary (RF-40, 41, 43): imposed and forbidden terms, "do not translate", notes. */
export function GlossaryDrawer({ projectId }: { projectId: string }) {
  const t = useT();
  const qc = useQueryClient();
  const notify = useNotices((s) => s.show);
  const draft = useView((s) => s.glossaryDraft);
  const close = useView((s) => s.closeGlossary);
  const { data: projects = [] } = useProjects();
  const lang = projects.find((p) => p.id === projectId)?.lingua_ufficiale ?? "en";
  const { data } = useQuery({
    queryKey: glossaryKey(projectId),
    queryFn: () => getGlossary(projectId),
  });
  const [rows, setRows] = useState<GlossaryEntry[] | null>(null);
  const [search, setSearch] = useState("");
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (!data || rows !== null) return;
    const base = [...data];
    if (draft) {
      base.unshift({
        sorgente: draft.sorgente ?? "",
        destinazione: { ...(draft.destinazione ?? {}) },
        vietati: {},
        non_tradurre: draft.non_tradurre ?? false,
        note: "",
      });
      setDirty(true);
    }
    setRows(base);
  }, [data, rows, draft]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return (rows ?? [])
      .map((entry, index) => ({ entry, index }))
      .filter(
        ({ entry }) =>
          !q ||
          entry.sorgente.toLowerCase().includes(q) ||
          (entry.destinazione[lang] ?? "").toLowerCase().includes(q),
      );
  }, [rows, search, lang]);

  const edit = (index: number, patch: Partial<GlossaryEntry>) => {
    setRows((current) => (current ?? []).map((r, i) => (i === index ? { ...r, ...patch } : r)));
    setDirty(true);
  };

  const save = async () => {
    const clean = (rows ?? [])
      .filter((r) => r.sorgente.trim())
      .map((r) => ({ ...r, sorgente: r.sorgente.trim() }));
    try {
      const saved = await putGlossary(projectId, clean);
      qc.setQueryData(glossaryKey(projectId), saved);
      setRows(saved);
      setDirty(false);
    } catch (e) {
      notify(e instanceof Error ? e.message : String(e));
    }
  };

  const input = "w-full rounded-ui border border-border bg-bg px-1 py-0.5";
  return (
    <aside
      role="dialog"
      aria-label={t("glossary.title")}
      className="fixed inset-y-0 right-0 z-10 flex w-[420px] max-w-full flex-col border-l border-border bg-surface p-4 shadow-lg"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">{t("glossary.title")}</h2>
        <button type="button" onClick={close} className="rounded-ui px-2 py-1 hover:bg-surface-2">
          {t("settings.close")}
        </button>
      </div>
      <div className="mt-3 flex gap-2">
        <input
          type="search"
          aria-label={t("glossary.search")}
          placeholder={t("glossary.search")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className={input}
        />
        <button
          type="button"
          onClick={() => {
            setRows((r) => [blank(), ...(r ?? [])]);
            setDirty(true);
          }}
          className="flex shrink-0 items-center gap-1 rounded-ui border border-border px-2 hover:bg-surface-2"
        >
          <Plus size={14} strokeWidth={1.5} aria-hidden />
          {t("glossary.add")}
        </button>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-[13px]">
        <label className="cursor-pointer rounded-ui border border-border px-2 py-1 hover:bg-surface-2">
          {t("glossary.import")}
          <input
            type="file"
            accept=".csv,.tbx,.xml"
            className="sr-only"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              e.target.value = "";
              if (!file) return;
              try {
                const result = await importGlossary(
                  projectId,
                  file,
                  file.name.toLowerCase().endsWith(".csv") ? "csv" : "tbx",
                );
                await qc.invalidateQueries({ queryKey: glossaryKey(projectId) });
                setRows(null);
                setDirty(false);
                notify(t("glossary.imported", { added: result.added, seen: result.seen }));
              } catch (err) {
                notify(err instanceof Error ? err.message : String(err));
              }
            }}
          />
        </label>
        <a
          className="underline underline-offset-2"
          href={glossaryExportUrl(projectId, "csv")}
          download
        >
          CSV
        </a>
        <a
          className="underline underline-offset-2"
          href={glossaryExportUrl(projectId, "tbx")}
          download
        >
          TBX
        </a>
      </div>
      <ul className="m-0 mt-3 min-h-0 flex-1 list-none space-y-3 overflow-y-auto p-0">
        {visible.length === 0 && <li className="text-muted">{t("glossary.empty")}</li>}
        {visible.map(({ entry, index }) => (
          <li
            key={index}
            className="rounded-ui border border-border p-2"
            data-testid="glossary-row"
          >
            <label className="block text-[12px] text-muted">
              {t("glossary.term")}
              <input
                value={entry.sorgente}
                onChange={(e) => edit(index, { sorgente: e.target.value })}
                className={input}
              />
            </label>
            <label className="mt-1 flex items-center gap-2 text-[13px]">
              <input
                type="checkbox"
                checked={entry.non_tradurre}
                onChange={(e) => edit(index, { non_tradurre: e.target.checked })}
              />
              {t("glossary.doNotTranslate")}
            </label>
            {!entry.non_tradurre && (
              <>
                <label className="mt-1 block text-[12px] text-muted">
                  {t("glossary.imposed", { lang })}
                  <input
                    value={entry.destinazione[lang] ?? ""}
                    onChange={(e) =>
                      edit(index, {
                        destinazione: { ...entry.destinazione, [lang]: e.target.value },
                      })
                    }
                    className={input}
                  />
                </label>
                <label className="mt-1 block text-[12px] text-muted">
                  {t("glossary.forbidden", { lang })}
                  <input
                    value={(entry.vietati[lang] ?? []).join(", ")}
                    onChange={(e) =>
                      edit(index, {
                        vietati: {
                          ...entry.vietati,
                          [lang]: e.target.value
                            .split(",")
                            .map((x) => x.trim())
                            .filter(Boolean),
                        },
                      })
                    }
                    className={input}
                  />
                </label>
              </>
            )}
            <label className="mt-1 block text-[12px] text-muted">
              {t("glossary.notes")}
              <input
                value={entry.note}
                onChange={(e) => edit(index, { note: e.target.value })}
                className={input}
              />
            </label>
            <button
              type="button"
              aria-label={t("glossary.delete")}
              title={t("glossary.delete")}
              onClick={() => {
                setRows((r) => (r ?? []).filter((_, i) => i !== index));
                setDirty(true);
              }}
              className="mt-1 flex items-center gap-1 text-muted hover:text-red"
            >
              <Trash2 size={14} strokeWidth={1.5} aria-hidden />
              {t("glossary.delete")}
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        disabled={!dirty}
        onClick={() => void save()}
        className="mt-3 rounded-ui bg-accent px-3 py-1.5 text-accent-fg disabled:opacity-50"
      >
        {dirty ? t("glossary.save") : t("glossary.saved")}
      </button>
    </aside>
  );
}
