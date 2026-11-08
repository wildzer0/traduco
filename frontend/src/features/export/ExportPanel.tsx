import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Drawer } from "../../components/Drawer";
import {
  checkExport,
  exportDownloadUrl,
  getExport,
  listLanguages,
  listTemplates,
  startExport,
} from "../../lib/api";
import { useCapabilities } from "../../lib/capabilities";
import { type ExportChoice, loadExportChoice, saveExportChoice } from "../../lib/export-prefs";
import { type MessageKey, useT } from "../../lib/i18n";
import type { ExportStatus } from "../../lib/types";
import { useView } from "../../lib/view-store";
import { cacheDiagram } from "../preview/diagrams";
import { useReview } from "../review/queries";
import { useProjects } from "../tree/queries";

const STEPS = new Set([
  "collect",
  "translate",
  "titles",
  "fields",
  "document",
  "snapshot",
  "convert",
]);

/** Export panel (docs/03-ui.md): scope, language and template, progress, then the download. */
export function ExportPanel({
  projectId,
  selected,
}: {
  projectId: string;
  selected: string | null;
}) {
  const t = useT();
  const close = useView((s) => s.setExportOpen);
  const autoRun = useView((s) => s.exportAutoRun);
  const setMode = useView((s) => s.setMode);
  const openImport = useView((s) => s.setImportOpen);
  const setFilter = useView((s) => s.setReviewFilter);
  const { data: projects = [] } = useProjects();
  const project = projects.find((p) => p.id === projectId);
  const { data: templates = [] } = useQuery({
    queryKey: ["templates", projectId],
    queryFn: () => listTemplates(projectId),
  });
  const { data: languages = [] } = useQuery({
    queryKey: ["languages", projectId],
    queryFn: () => listLanguages(projectId),
  });
  const { data: review } = useReview(projectId);
  const { data: capabilities } = useCapabilities();
  const office = capabilities?.libreoffice.available ?? false;
  const [choice, setChoice] = useState<ExportChoice>(loadExportChoice);
  const [status, setStatus] = useState<ExportStatus | null>(null);
  const [running, setRunning] = useState(false);
  const names = new Intl.DisplayNames([document.documentElement.lang || "it"], {
    type: "language",
  });
  const ran = useRef(false);

  const chapterPath = selected ? selected.split("/").slice(0, -1).join("/") : null;
  const pathFor = (scope: ExportChoice["scope"]) =>
    scope === "section" ? selected : scope === "chapter" ? chapterPath : null;
  const scope = choice.scope !== "project" && !pathFor(choice.scope) ? "project" : choice.scope;
  const toReview = review?.counts.needs_review ?? 0;
  const { data: check } = useQuery({
    queryKey: ["export-check", projectId, scope, pathFor(scope), choice.language],
    queryFn: () =>
      checkExport(projectId, {
        scope,
        ...(pathFor(scope) ? { path: pathFor(scope) as string } : {}),
        language: choice.language,
      }),
    staleTime: 0,
    retry: false,
  });
  // sections still to review are already offered above: here only what the export would hide
  const findings = (check?.findings ?? []).filter((f) => f.code !== "needs_review");

  const download = (job: string) => {
    const link = document.createElement("a");
    link.href = exportDownloadUrl(projectId, job);
    link.download = "";
    document.body.append(link);
    link.click();
    link.remove();
  };

  const run = async (used: ExportChoice = { ...choice, scope }) => {
    setRunning(true);
    setStatus(null);
    saveExportChoice(used);
    try {
      const attempt = async (): Promise<ExportStatus> => {
        let job = await startExport(projectId, {
          scope: used.scope,
          ...(pathFor(used.scope) ? { path: pathFor(used.scope) as string } : {}),
          language: used.language,
          ...(used.template ? { template: used.template } : {}),
          format: used.format,
          draft: used.watermark ? "auto" : "off",
        });
        setStatus(job);
        while (job.state === "running") {
          await new Promise((resolve) => setTimeout(resolve, 400));
          job = await getExport(projectId, job.id);
          setStatus(job);
        }
        return job;
      };
      let job = await attempt();
      // diagrams not drawn yet: draw them here (the browser does it) and start again, once
      const missing = (job.error?.details?.diagrams ?? []) as { hash?: string; code?: string }[];
      if (job.state === "failed" && job.error?.code === "diagram_missing" && missing.length > 0) {
        setStatus({ ...job, state: "running", message: t("export.drawingDiagrams"), error: null });
        for (const d of missing)
          if (d.hash && d.code) await cacheDiagram(projectId, d.hash, d.code);
        job = await attempt();
      }
      if (job.state === "done") download(job.id);
    } catch (e) {
      setStatus({
        id: "",
        state: "failed",
        progress: 0,
        message: "",
        warnings: [],
        filename: null,
        error: { code: "client", message: e instanceof Error ? e.message : String(e), details: {} },
      });
    } finally {
      setRunning(false);
    }
  };

  // biome-ignore lint/correctness/useExhaustiveDependencies: Ctrl+E runs once when the panel opens
  useEffect(() => {
    if (autoRun && !ran.current) {
      ran.current = true;
      void run();
    }
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  const field = "mt-1 w-full rounded-ui border border-border bg-bg px-2 py-1";
  // the project list may not be loaded yet: DisplayNames.of("") throws, so an unknown code is shown empty
  const language = (code: string | undefined) => {
    if (!code) return "";
    try {
      return names.of(code) ?? code;
    } catch {
      return code;
    }
  };
  const diagrams = (status?.error?.details?.diagrams as { section: string }[] | undefined) ?? [];

  return (
    <Drawer title={t("export.title")} onClose={() => close(false)} width={420}>
      <label className="mt-3 block">
        {t("export.scope")}
        <select
          className={field}
          value={scope}
          disabled={running}
          onChange={(e) => setChoice({ ...choice, scope: e.target.value as ExportChoice["scope"] })}
        >
          <option value="section" disabled={!selected}>
            {t("export.scope.section")}
          </option>
          <option value="chapter" disabled={!chapterPath}>
            {t("export.scope.chapter")}
          </option>
          <option value="project">{t("export.scope.project")}</option>
        </select>
      </label>
      {!selected && <p className="m-0 mt-1 text-[12px] text-muted">{t("export.needPath")}</p>}

      <label className="mt-3 block">
        {t("export.language")}
        <select
          className={field}
          value={choice.language}
          disabled={running}
          onChange={(e) =>
            setChoice({ ...choice, language: e.target.value as ExportChoice["language"] })
          }
        >
          <option value="ufficiale">
            {t("export.language.ufficiale", { language: language(project?.lingua_ufficiale) })}
          </option>
          <option value="sorgente">
            {t("export.language.sorgente", { language: language(project?.lingua_sorgente) })}
          </option>
          <option value="bilingue">{t("export.language.bilingue")}</option>
          {languages
            .filter((l) => l.role === "additional")
            .map((l) => (
              <option key={l.code} value={l.code}>
                {language(l.code)} ({l.percent}%)
              </option>
            ))}
        </select>
      </label>

      <label className="mt-3 block">
        {t("export.format")}
        <select
          className={field}
          value={choice.format}
          disabled={running}
          onChange={(e) =>
            setChoice({ ...choice, format: e.target.value as ExportChoice["format"] })
          }
        >
          <option value="docx">{t("export.format.docx")}</option>
          <option value="pdf" disabled={!office}>
            {t("export.format.pdf")}
          </option>
          <option value="odt" disabled={!office}>
            {t("export.format.odt")}
          </option>
          <option value="html">{t("export.format.html")}</option>
          <option value="epub">{t("export.format.epub")}</option>
          <option value="md">{t("export.format.md")}</option>
        </select>
      </label>
      {!office && <p className="m-0 mt-1 text-[12px] text-muted">{t("export.needOffice")}</p>}

      <label
        className={`mt-3 block ${["html", "epub", "md"].includes(choice.format) ? "hidden" : ""}`}
      >
        {t("export.template")}
        <select
          className={field}
          value={choice.template}
          disabled={running}
          onChange={(e) => setChoice({ ...choice, template: e.target.value })}
        >
          <option value="">
            {templates.some((x) => x.default)
              ? `${templates.find((x) => x.default)?.name} (${t("templates.default")})`
              : t("export.noTemplate")}
          </option>
          {templates.map((tpl) => (
            <option key={tpl.name} value={tpl.name}>
              {tpl.name}
            </option>
          ))}
        </select>
      </label>

      {findings.length > 0 && (
        <div className="mt-3 text-[13px]" data-testid="export-findings">
          <p className="m-0 font-medium">{t("export.findings", { count: findings.length })}</p>
          <ul className="m-0 mt-1 list-disc pl-5">
            {findings.slice(0, 8).map((f) => (
              <li
                key={`${f.code}:${f.path}:${f.detail}`}
                className={f.severity === "error" ? "text-red" : "text-amber"}
              >
                {t(`export.finding.${f.code}` as MessageKey, {
                  section: f.path.split("/").pop() ?? f.path,
                  detail: f.detail,
                })}
              </li>
            ))}
          </ul>
          {findings.length > 8 && (
            <p className="m-0 mt-1 text-muted">
              {t("export.findingsMore", { count: findings.length - 8 })}
            </p>
          )}
        </div>
      )}

      {toReview > 0 && (
        <p className="m-0 mt-3 text-[13px] text-amber">
          {t("export.toReview", { count: toReview })}{" "}
          <button
            type="button"
            className="underline underline-offset-2"
            onClick={() => {
              setFilter("needs_review");
              setMode("review");
              close(false);
            }}
          >
            {t("export.goReview")}
          </button>
        </p>
      )}

      <label className="mt-3 flex items-center gap-2 text-[13px]">
        <input
          type="checkbox"
          checked={choice.watermark}
          disabled={running}
          onChange={(e) => setChoice({ ...choice, watermark: e.target.checked })}
        />
        {t("export.watermark")}
      </label>

      <button
        type="button"
        disabled={running}
        onClick={() => void run()}
        className="mt-4 rounded-ui bg-accent px-3 py-1.5 text-accent-fg disabled:opacity-50"
      >
        {running
          ? t("export.running")
          : status?.state === "done"
            ? t("export.again")
            : t("export.run")}
      </button>

      <button
        type="button"
        disabled={running}
        onClick={() => {
          close(false);
          openImport(true);
        }}
        className="mt-2 rounded-ui border border-border px-3 py-1.5 hover:bg-surface-2 disabled:opacity-50"
      >
        {t("import.open")}
      </button>

      {status && status.state === "running" && (
        <div className="mt-3" role="status">
          <div className="h-2 overflow-hidden rounded-full bg-surface-2">
            <div
              className="h-full bg-accent transition-all"
              style={{ width: `${status.progress}%` }}
              data-testid="export-progress"
            />
          </div>
          <p className="m-0 mt-1 text-[13px] text-muted">
            {STEPS.has(status.message)
              ? t(`export.step.${status.message}` as "export.step.collect")
              : t("export.running")}
          </p>
        </div>
      )}

      {status?.state === "done" && (
        <div className="mt-3" role="status">
          <p className="m-0 text-green">{t("export.done", { name: status.filename ?? "" })}</p>
          <a
            className="text-[13px] underline underline-offset-2"
            href={exportDownloadUrl(projectId, status.id)}
            download
          >
            {t("export.download")}
          </a>
        </div>
      )}

      {status?.state === "failed" && status.error && (
        <div role="alert" className="mt-3 text-red">
          <p className="m-0 font-medium">{t("export.failed")}</p>
          <p className="m-0 mt-1 text-[13px]">{status.error.message}</p>
          {diagrams.length > 0 && (
            <p className="m-0 mt-1 text-[13px]">
              {t("export.diagrams", {
                sections: [...new Set(diagrams.map((d) => d.section.split("/").pop()))].join(", "),
              })}
            </p>
          )}
        </div>
      )}

      {status && status.warnings.length > 0 && (
        <div className="mt-3 text-[13px]">
          <p className="m-0 font-medium text-amber">{t("export.warnings")}</p>
          <ul className="m-0 mt-1 list-disc pl-5">
            {status.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}
    </Drawer>
  );
}
