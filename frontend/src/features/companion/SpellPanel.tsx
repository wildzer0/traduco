import { useState } from "react";
import { applyAssist, type SpellIssue, spellcheck } from "../../lib/api";
import { editorBridge } from "../../lib/editor-bridge";
import { recheckOpenFile } from "../../lib/file-events";
import { useT } from "../../lib/i18n";
import { useNotices } from "../../lib/notices";

/** Spelling and grammar of the source with the author's own LanguageTool (RF-16, optional). */
export function SpellPanel({ projectId, path }: { projectId: string; path: string | null }) {
  const t = useT();
  const notify = useNotices((s) => s.show);
  const [issues, setIssues] = useState<SpellIssue[] | null>(null);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    if (!path) return;
    setBusy(true);
    try {
      await editorBridge.flush(); // check what is on screen
      setIssues((await spellcheck(projectId, path)).issues);
    } catch (e) {
      notify(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const apply = async (issue: SpellIssue, replacement: string) => {
    if (!path) return;
    const text =
      issue.context.slice(0, issue.offset) +
      replacement +
      issue.context.slice(issue.offset + issue.length);
    try {
      await editorBridge.flush();
      await applyAssist(projectId, { path, key: issue.key, text });
      recheckOpenFile();
      await run(); // offsets of the rest of the segment moved: look again
    } catch (e) {
      notify(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <section className="mt-4 border-t border-border pt-3" aria-label={t("spell.title")}>
      <h3 className="m-0 text-sm font-semibold">{t("spell.title")}</h3>
      <button
        type="button"
        disabled={busy || !path}
        onClick={() => void run()}
        className="mt-2 rounded-ui border border-border px-3 py-1 hover:bg-surface-2 disabled:opacity-50"
      >
        {busy ? t("check.running") : t("spell.run")}
      </button>
      {issues?.length === 0 && (
        <p role="status" className="m-0 mt-2 text-green">
          {t("spell.none")}
        </p>
      )}
      <ul className="m-0 mt-2 list-none space-y-2 p-0">
        {issues?.map((issue) => (
          <li
            key={`${issue.key}:${issue.offset}`}
            className="text-[13px]"
            data-testid="spell-issue"
          >
            <strong>{issue.word}</strong> — {issue.message}
            <div className="mt-1 flex flex-wrap gap-1">
              {issue.replacements.map((r) => (
                <button
                  key={r}
                  type="button"
                  className="rounded-ui border border-border px-2 py-0.5 hover:bg-surface-2"
                  onClick={() => void apply(issue, r)}
                >
                  {r}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
