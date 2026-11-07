import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2, Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  addExampleTemplate,
  deleteTemplate,
  getProject,
  getTemplate,
  listTemplates,
  putTemplateMapping,
  setDefaultTemplate,
  uploadTemplate,
} from "../../lib/api";
import { useT } from "../../lib/i18n";
import { useNotices } from "../../lib/notices";
import type { TemplateDetail, TemplateMapping } from "../../lib/types";
import { useView } from "../../lib/view-store";

export const templatesKey = (id: string) => ["templates", id] as const;
const RESERVED = new Set(["CONTENUTO", "REVISIONI", "SOMMARIO"]);
const KNOWN_BY_APP = ["nome", "lingua", "data_esportazione"];

/** Company templates (RF-50..52, 56): upload, what was found in the file, style mapping, default. */
export function TemplateDrawer({ projectId }: { projectId: string }) {
  const t = useT();
  const qc = useQueryClient();
  const notify = useNotices((s) => s.show);
  const close = useView((s) => s.setTemplatesOpen);
  const fileInput = useRef<HTMLInputElement>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [mapping, setMapping] = useState<TemplateMapping | null>(null);
  const [busy, setBusy] = useState(false);

  const { data: templates = [] } = useQuery({
    queryKey: templatesKey(projectId),
    queryFn: () => listTemplates(projectId),
  });
  const name = selected ?? templates.find((x) => x.default)?.name ?? templates[0]?.name ?? null;
  const { data: detail } = useQuery({
    queryKey: ["template", projectId, name],
    queryFn: () => getTemplate(projectId, name as string),
    enabled: name !== null,
  });
  const { data: project } = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => getProject(projectId),
  });

  useEffect(() => {
    setMapping(detail ? structuredClone(detail.mapping) : null);
  }, [detail]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  const refresh = async () => {
    await qc.invalidateQueries({ queryKey: templatesKey(projectId) });
    await qc.invalidateQueries({ queryKey: ["template", projectId] });
    await qc.invalidateQueries({ queryKey: ["project", projectId] });
  };
  const guard = async (run: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await run();
    } catch (e) {
      notify(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const upload = (file: File) =>
    guard(async () => {
      const created = await uploadTemplate(projectId, file);
      setSelected(created.name);
      await refresh();
    });

  const metadata = project ? Object.keys((project.metadati as Record<string, unknown>) ?? {}) : [];
  const provided = new Set([...metadata, ...KNOWN_BY_APP]);
  const withoutValue = (detail?.fields ?? []).filter((f) => !provided.has(f));
  const dirty = detail && mapping && JSON.stringify(mapping) !== JSON.stringify(detail.mapping);

  return (
    <aside
      role="dialog"
      aria-label={t("templates.title")}
      className="fixed inset-y-0 right-0 z-10 flex w-[420px] max-w-full flex-col overflow-y-auto border-l border-border bg-surface p-4 shadow-lg"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">{t("templates.title")}</h2>
        <button
          type="button"
          onClick={() => close(false)}
          className="rounded-ui px-2 py-1 hover:bg-surface-2"
        >
          {t("settings.close")}
        </button>
      </div>

      <input
        ref={fileInput}
        type="file"
        accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        aria-label={t("templates.file")}
        className="sr-only"
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) void upload(file);
        }}
      />
      <button
        type="button"
        disabled={busy}
        onClick={() => fileInput.current?.click()}
        className="mt-3 flex items-center justify-center gap-2 rounded-ui bg-accent px-3 py-1.5 text-accent-fg disabled:opacity-50"
      >
        <Upload size={14} strokeWidth={1.5} aria-hidden />
        {t("templates.upload")}
      </button>

      {!templates.some((x) => x.name === "manuale") && (
        <button
          type="button"
          disabled={busy}
          onClick={() =>
            guard(async () => {
              const created = await addExampleTemplate(projectId);
              setSelected(created.name);
              await refresh();
            })
          }
          className="mt-2 rounded-ui border border-border px-3 py-1.5 hover:bg-surface-2 disabled:opacity-50"
        >
          {t("templates.addExample")}
        </button>
      )}
      {templates.length === 0 && <p className="mt-3 text-muted">{t("templates.empty")}</p>}
      {templates.length > 0 && (
        <ul className="m-0 mt-3 list-none space-y-1 p-0" aria-label={t("templates.list")}>
          {templates.map((tpl) => (
            <li key={tpl.name} className="flex items-center gap-2">
              <button
                type="button"
                aria-pressed={tpl.name === name}
                onClick={() => setSelected(tpl.name)}
                className={`min-w-0 flex-1 truncate rounded-ui px-2 py-1 text-left ${tpl.name === name ? "bg-surface-2 font-medium" : "hover:bg-surface-2"}`}
              >
                {tpl.name}
              </button>
              {tpl.default ? (
                <span className="text-[12px] text-green">{t("templates.default")}</span>
              ) : (
                <button
                  type="button"
                  className="text-[12px] underline underline-offset-2"
                  onClick={() =>
                    guard(async () => {
                      await setDefaultTemplate(projectId, tpl.name);
                      await refresh();
                    })
                  }
                >
                  {t("templates.makeDefault")}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {detail && mapping && (
        <Analysis
          detail={detail}
          mapping={mapping}
          withoutValue={withoutValue}
          onChange={setMapping}
        />
      )}

      {detail && mapping && (
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            disabled={busy || !dirty}
            onClick={() =>
              guard(async () => {
                await putTemplateMapping(projectId, detail.name, mapping);
                await refresh();
              })
            }
            className="rounded-ui bg-accent px-3 py-1.5 text-accent-fg disabled:opacity-50"
          >
            {t("templates.saveMapping")}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() =>
              guard(async () => {
                await deleteTemplate(projectId, detail.name);
                setSelected(null);
                await refresh();
              })
            }
            className="ml-auto flex items-center gap-1 rounded-ui px-3 py-1.5 text-muted hover:text-red"
          >
            <Trash2 size={14} strokeWidth={1.5} aria-hidden />
            {t("templates.delete")}
          </button>
        </div>
      )}
    </aside>
  );
}

function Analysis({
  detail,
  mapping,
  withoutValue,
  onChange,
}: {
  detail: TemplateDetail;
  mapping: TemplateMapping;
  withoutValue: string[];
  onChange: (m: TemplateMapping) => void;
}) {
  const t = useT();
  const paragraph = detail.styles.filter((s) => s.kind === "paragraph");
  const tables = detail.styles.filter((s) => s.kind === "table");
  const fields = detail.fields.filter((f) => !RESERVED.has(f));
  const mark = (ok: boolean) => (ok ? "✓" : "✗");
  return (
    <section className="mt-4" aria-label={t("templates.analysis")}>
      <h3 className="text-sm font-semibold">{t("templates.found")}</h3>
      <ul className="m-0 mt-1 list-none space-y-0.5 p-0 text-[13px]">
        <li className={detail.has_content ? "" : "text-red"}>
          {mark(detail.has_content)} {"{{CONTENUTO}}"}
          {!detail.has_content && ` — ${t("templates.noContent")}`}
        </li>
        <li className="text-muted">
          {mark(detail.has_toc)} {"{{SOMMARIO}}"}
        </li>
        <li className="text-muted">
          {mark(detail.has_revisions)} {"{{REVISIONI}}"}
        </li>
      </ul>
      <p className="m-0 mt-2 text-[13px]">
        <span className="text-muted">{t("templates.fields")}: </span>
        {fields.length ? fields.map((f) => `{{${f}}}`).join(", ") : "—"}
      </p>
      {withoutValue.length > 0 && (
        <p role="alert" className="m-0 mt-1 text-[13px] text-amber">
          {t("templates.noValue", { fields: withoutValue.join(", ") })}
        </p>
      )}
      {detail.problems.length > 0 && (
        <ul className="m-0 mt-1 list-none p-0 text-[13px] text-amber">
          {detail.problems.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ul>
      )}

      <h3 className="mt-4 text-sm font-semibold">{t("templates.mapping")}</h3>
      <div className="mt-1 grid grid-cols-[auto_1fr] items-center gap-x-3 gap-y-1">
        {detail.roles.map((role) => {
          const options = role === "tabella" ? tables : paragraph;
          return (
            <label key={role} className="contents">
              <span className="text-[13px]">
                {t(`templates.role.${role}` as "templates.role.corpo")}
              </span>
              <select
                aria-label={t(`templates.role.${role}` as "templates.role.corpo")}
                value={mapping.stili[role] ?? ""}
                onChange={(e) => {
                  const stili = { ...mapping.stili };
                  if (e.target.value) stili[role] = e.target.value;
                  else delete stili[role];
                  onChange({ ...mapping, stili });
                }}
                className="min-w-0 rounded-ui border border-border bg-bg px-1 py-0.5"
              >
                <option value="">{t("templates.pandocDefault")}</option>
                {options.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
          );
        })}
      </div>
      <label className="mt-3 flex items-center gap-2 text-[13px]">
        <input
          type="checkbox"
          checked={mapping.campi_mancanti_ammessi}
          onChange={(e) => onChange({ ...mapping, campi_mancanti_ammessi: e.target.checked })}
        />
        {t("templates.allowMissing")}
      </label>
    </section>
  );
}
