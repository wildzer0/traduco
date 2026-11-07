import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { listSnippets, saveSnippets } from "../../lib/api";
import { useT } from "../../lib/i18n";
import { useView } from "../../lib/view-store";

const EXAMPLE = `contatori:
  REQ: { prefisso: "FOO-REQ-", cifre: 5 }
snippet:
  - alias: req
    descrizione: Nuovo requisito
    testo: "**{{contatore:REQ}}** Il sistema deve \${1:fare qualcosa}."
`;

/** Edit snippet.yaml (RF-86); the file is checked before it is saved. */
export function SnippetsDrawer({ projectId }: { projectId: string }) {
  const t = useT();
  const qc = useQueryClient();
  const close = useView((s) => s.setSnippetsOpen);
  const { data } = useQuery({
    queryKey: ["snippets", projectId],
    queryFn: () => listSnippets(projectId),
  });
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const shown = text ?? data?.raw ?? "";

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  const save = async () => {
    setError(null);
    setSaved(false);
    try {
      await saveSnippets(projectId, shown);
      setText(null);
      setSaved(true);
      await qc.invalidateQueries({ queryKey: ["snippets", projectId] });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  return (
    <aside
      role="dialog"
      aria-label={t("snippets.title")}
      className="fixed inset-y-0 right-0 z-10 flex w-[460px] max-w-full flex-col overflow-y-auto border-l border-border bg-surface p-4 shadow-lg"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">{t("snippets.title")}</h2>
        <button
          type="button"
          onClick={() => close(false)}
          className="rounded-ui px-2 py-1 hover:bg-surface-2"
        >
          {t("issues.close")}
        </button>
      </div>
      <p className="mt-2 text-[13px] text-muted">{t("snippets.intro")}</p>
      <textarea
        aria-label="snippet.yaml"
        className="mt-1 min-h-64 w-full rounded-ui border border-border bg-bg p-2 font-mono text-[13px]"
        value={shown}
        onChange={(e) => setText(e.target.value)}
        spellCheck={false}
      />
      <div className="mt-2 flex items-center gap-2">
        <button
          type="button"
          onClick={() => void save()}
          className="rounded-ui bg-accent px-3 py-1 text-accent-fg"
        >
          {t("snippets.save")}
        </button>
        {shown.trim() === "" && (
          <button
            type="button"
            onClick={() => setText(EXAMPLE)}
            className="rounded-ui border border-border px-3 py-1 hover:bg-surface-2"
          >
            {t("snippets.example")}
          </button>
        )}
        {saved && <span className="text-[13px] text-green">{t("snippets.saved")}</span>}
      </div>
      {error && (
        <p role="alert" className="m-0 mt-2 text-[13px] text-red">
          {error}
        </p>
      )}
      {data && data.counters.length > 0 && (
        <>
          <h3 className="mt-4 text-sm font-semibold">{t("snippets.counters")}</h3>
          <ul className="m-0 list-none p-0 text-[13px]">
            {data.counters.map((c) => (
              <li key={c.name}>
                {c.name}: <code>{c.next}</code>
              </li>
            ))}
          </ul>
        </>
      )}
    </aside>
  );
}
