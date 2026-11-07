import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { applyAssist, assist } from "../../lib/api";
import { diffWords } from "../../lib/diff";
import { editorBridge } from "../../lib/editor-bridge";
import { recheckOpenFile } from "../../lib/file-events";
import { useT } from "../../lib/i18n";
import { useNotices } from "../../lib/notices";
import { useTranslationState } from "../../lib/translation-store";
import type { AssistAction } from "../../lib/types";
import { translationKey } from "./translation";

const ACTIONS: AssistAction[] = [
  "correct",
  "rephrase",
  "concise",
  "simple",
  "formale",
  "neutro",
  "informale",
];

/** Word-level difference, as shown to accept or refuse a suggestion. */
export function Diff({ before, after }: { before: string; after: string }) {
  const parts = diffWords(before, after);
  return (
    <p className="m-0 whitespace-pre-wrap" data-testid="diff">
      {parts.map((part, i) => {
        const key = `${i}-${part.type}`;
        if (part.type === "add")
          return (
            <ins key={key} className="bg-green/20 no-underline">
              {part.text}
            </ins>
          );
        if (part.type === "del")
          return (
            <del key={key} className="bg-red/20">
              {part.text}
            </del>
          );
        return <span key={key}>{part.text}</span>;
      })}
    </p>
  );
}

/**
 * Writing companion for one segment (RF-87): choose what to do, read the difference, accept.
 * The text is never changed before "Apply"; applying rewrites the source and the server translates
 * just this segment again.
 */
export function AssistBox({
  projectId,
  path,
  segKey,
  top,
  onClose,
}: {
  projectId: string;
  path: string;
  segKey: string;
  top: number;
  onClose: () => void;
}) {
  const t = useT();
  const qc = useQueryClient();
  const notify = useNotices((s) => s.show);
  const online = useTranslationState((s) => s.online) !== false;
  const [instruction, setInstruction] = useState("");
  const [last, setLast] = useState<AssistAction | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{
    original: string;
    proposal: string;
    changed: boolean;
  } | null>(null);

  const run = async (action: AssistAction) => {
    setBusy(true);
    setLast(action);
    setResult(null);
    try {
      setResult(await assist(projectId, { path, key: segKey, action, instruction }));
    } catch (e) {
      notify(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const apply = async () => {
    if (!result) return;
    try {
      await editorBridge.flush(); // unsaved typing must be on disk before the file is rewritten
      await applyAssist(projectId, { path, key: segKey, text: result.proposal });
      recheckOpenFile();
      await qc.invalidateQueries({ queryKey: translationKey(projectId, path) });
      onClose();
    } catch (e) {
      notify(e instanceof Error ? e.message : String(e));
    }
  };

  const chip = "rounded-ui border border-border px-2 py-0.5 hover:bg-surface-2 disabled:opacity-50";
  return (
    <div
      className="absolute left-0 right-0 z-10 rounded-ui border border-border bg-surface p-2 text-[13px] shadow-lg"
      style={{ top }}
      role="dialog"
      aria-label={t("assist.toolbar")}
    >
      {!online && <p className="m-0 mb-2 text-amber">{t("assist.offline")}</p>}
      <div className="flex flex-wrap gap-1">
        {ACTIONS.map((a) => (
          <button
            key={a}
            type="button"
            className={chip}
            disabled={!online || busy}
            aria-pressed={last === a}
            onClick={() => void run(a)}
          >
            {t(`assist.${a}` as "assist.correct")}
          </button>
        ))}
      </div>
      <label className="mt-2 block">
        <span className="text-muted">{t("assist.instruction")}</span>
        <input
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !busy && online) void run(last ?? "rephrase");
            if (e.key === "Escape") onClose();
          }}
          className="mt-1 w-full rounded-ui border border-border bg-bg p-1"
        />
      </label>
      {busy && <p className="m-0 mt-2 text-muted">{t("assist.working")}</p>}
      {result && !result.changed && <p className="m-0 mt-2 text-muted">{t("assist.same")}</p>}
      {result?.changed && (
        <div className="mt-2 rounded-ui border border-border p-2">
          <p className="m-0 mb-1 text-muted">{t("assist.original")}</p>
          <Diff before={result.original} after={result.proposal} />
          <p className="m-0 mt-2 text-[12px] text-muted">{t("assist.applyHint")}</p>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              className="rounded-ui bg-accent px-3 py-1 text-accent-fg"
              onClick={() => void apply()}
            >
              {t("assist.apply")}
            </button>
            {last && (
              <button type="button" className={chip} disabled={busy} onClick={() => void run(last)}>
                {t("assist.regenerate")}
              </button>
            )}
          </div>
        </div>
      )}
      <div className="mt-2 flex justify-end">
        <button type="button" className="rounded-ui px-2 py-1 hover:bg-surface-2" onClick={onClose}>
          {t("assist.close")}
        </button>
      </div>
    </div>
  );
}
