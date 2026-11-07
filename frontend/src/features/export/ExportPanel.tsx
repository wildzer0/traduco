import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { exportDownloadUrl, getExport, listTemplates, startExport } from "../../lib/api";
import { type ExportChoice, loadExportChoice, saveExportChoice } from "../../lib/export-prefs";
import { useT } from "../../lib/i18n";
import type { ExportStatus } from "../../lib/types";
import { useView } from "../../lib/view-store";
import { useReview } from "../review/queries";
import { useProjects } from "../tree/queries";

const STEPS = new Set(["collect", "translate", "titles", "fields", "document", "snapshot"]);

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
  const setFilter = useView((s) => s.setReviewFilter);
  const { data: projects = [] } = useProjects();
  const project = projects.find((p) => p.id === projectId);
  const { data: templates = [] } = useQuery({
    queryKey: ["templates", projectId],
    queryFn: () => listTemplates(projectId),
  });
  const { data: review } = useReview(projectId);
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
      let job = await startExport(projectId, {
        scope: used.scope,
        ...(pathFor(used.scope) ? { path: pathFor(used.scope) as string } : {}),
        language: used.language,
        ...(used.template ? { template: used.template } : {}),
      });
      setStatus(job);
      while (job.state === "running") {
        await new Promise((resolve) => setTimeout(resolve, 400));
        job = await getExport(projectId, job.id);
        setStatus(job);
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
  const language = (code: string | undefined) => names.of(code ?? "") ?? code ?? "";
  const diagrams = (status?.error?.details?.diagrams as { section: string }[] | undefined) ?? [];

  return (
    <aside
      role="dialog"
      aria-label={t("export.title")}
      className="fixed inset-y-0 right-0 z-10 flex w-[420px] max-w-full flex-col overflow-y-auto border-l border-border bg-surface p-4 shadow-lg"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">{t("export.title")}</h2>
        <button
          type="button"
          onClick={() => close(false)}
          className="rounded-ui px-2 py-1 hover:bg-surface-2"
        >
          {t("settings.close")}
        </button>
      </div>

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
        </select>
      </label>

      <label className="mt-3 block">
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
    </aside>
  );
}
