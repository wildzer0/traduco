import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { applyAssist, dismissSuggestion, getCheck, runCheck } from "../../lib/api";
import { useAssist } from "../../lib/assist-store";
import { editorBridge } from "../../lib/editor-bridge";
import { recheckOpenFile } from "../../lib/file-events";
import { useT } from "../../lib/i18n";
import { useNotices } from "../../lib/notices";
import { useTranslationState } from "../../lib/translation-store";
import type { Suggestion } from "../../lib/types";
import { useView } from "../../lib/view-store";
import { Diff } from "../preview/AssistBox";
import { translationPrefix, useTranslation } from "../preview/translation";

const checkKey = (id: string, path: string) => ["check", id, path] as const;

/** Section check (RF-88): suggestions anchored to segments; nothing changes until "Apply". */
export function CheckPanel({ projectId, path }: { projectId: string; path: string | null }) {
  const t = useT();
  const qc = useQueryClient();
  const notify = useNotices((s) => s.show);
  const close = useAssist((s) => s.setCheckOpen);
  const setFocusKey = useView((s) => s.setFocusKey);
  const online = useTranslationState((s) => s.online) !== false;
  const [requirements, setRequirements] = useState(false);
  const [busy, setBusy] = useState(false);
  const view = useTranslation(projectId, path).data;
  const { data } = useQuery({
    queryKey: checkKey(projectId, path ?? ""),
    queryFn: () => getCheck(projectId, path as string),
    enabled: path !== null,
  });
  const items = (data?.items ?? []).filter((i) => i.status === "open");
  const sources = new Map((view?.segments ?? []).map((s) => [s.key, s.source]));

  const refresh = () => qc.invalidateQueries({ queryKey: checkKey(projectId, path ?? "") });

  const run = async () => {
    if (!path) return;
    setBusy(true);
    try {
      await editorBridge.flush(); // check what is on screen, not an older save
      const result = await runCheck(projectId, path, requirements);
      qc.setQueryData(checkKey(projectId, path), result);
    } catch (e) {
      notify(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const apply = async (item: Suggestion) => {
    if (!path) return;
    try {
      await editorBridge.flush();
      await applyAssist(projectId, {
        path,
        key: item.key,
        text: item.suggestion,
        suggestion_id: item.id,
      });
      recheckOpenFile();
      await refresh();
      await qc.invalidateQueries({ queryKey: translationPrefix(projectId, path) });
    } catch (e) {
      notify(e instanceof Error ? e.message : String(e));
    }
  };

  const dismiss = async (item: Suggestion) => {
    if (!path) return;
    await dismissSuggestion(projectId, path, item.id);
    await refresh();
  };

  return (
    <aside
      role="dialog"
      aria-label={t("check.title")}
      className="fixed inset-y-0 right-0 z-10 flex w-[420px] max-w-full flex-col border-l border-border bg-surface p-4 shadow-lg"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">{t("check.title")}</h2>
        <button
          type="button"
          onClick={() => close(false)}
          className="rounded-ui px-2 py-1 hover:bg-surface-2"
        >
          {t("assist.close")}
        </button>
      </div>
      <label className="mt-3 flex items-start gap-2 text-[13px]">
        <input
          type="checkbox"
          checked={requirements}
          onChange={(e) => setRequirements(e.target.checked)}
          className="mt-1"
        />
        {t("check.requirements")}
      </label>
      {!online && <p className="mt-2 text-amber">{t("assist.offline")}</p>}
      <button
        type="button"
        disabled={busy || !path || !online}
        onClick={() => void run()}
        className="mt-3 rounded-ui bg-accent px-3 py-1.5 text-accent-fg disabled:opacity-50"
      >
        {busy ? t("check.running") : t("check.run")}
      </button>
      <ul className="m-0 mt-3 min-h-0 flex-1 list-none space-y-3 overflow-y-auto p-0">
        {data === undefined && <li className="text-muted">{t("check.none")}</li>}
        {data !== undefined && items.length === 0 && (
          <li className="text-muted">{t("check.empty")}</li>
        )}
        {items.map((item) => (
          <li
            key={item.id}
            className="rounded-ui border border-border p-2"
            data-testid="suggestion"
          >
            <p className="m-0 flex items-center gap-2 text-[12px] text-muted">
              <span className="rounded-ui bg-surface-2 px-1.5 py-0.5 text-fg">
                {t(`check.cat.${item.category}` as "check.cat.style")}
              </span>
              <span>{t(`check.origin.${item.origin}` as "check.origin.rule")}</span>
              <button
                type="button"
                className="ml-auto underline underline-offset-2"
                onClick={() => setFocusKey(item.key)}
              >
                {t("check.goto")}
              </button>
            </p>
            <p className="m-0 mt-1">{item.message}</p>
            {item.suggestion && (
              <div className="mt-2 rounded-ui bg-bg p-2">
                <Diff before={sources.get(item.key) ?? ""} after={item.suggestion} />
              </div>
            )}
            <div className="mt-2 flex gap-2">
              {item.suggestion && (
                <button
                  type="button"
                  className="rounded-ui bg-accent px-3 py-1 text-accent-fg"
                  onClick={() => void apply(item)}
                >
                  {t("check.apply")}
                </button>
              )}
              <button
                type="button"
                className="rounded-ui px-3 py-1 hover:bg-surface-2"
                onClick={() => void dismiss(item)}
              >
                {t("check.dismiss")}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </aside>
  );
}
