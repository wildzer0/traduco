import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Drawer } from "../../components/Drawer";
import { getFile, getVersion, listVersions, putFile } from "../../lib/api";
import { useT } from "../../lib/i18n";
import { useNotices } from "../../lib/notices";
import { useView } from "../../lib/view-store";

/** Earlier versions of the open section: read one, put it back (the current text is kept too). */
export function HistoryPanel({ projectId, path }: { projectId: string; path: string | null }) {
  const t = useT();
  const qc = useQueryClient();
  const close = useView((s) => s.setHistoryOpen);
  const notify = useNotices((s) => s.show);
  const [chosen, setChosen] = useState<string | null>(null);
  const { data: versions = [] } = useQuery({
    queryKey: ["history", projectId, path],
    queryFn: () => listVersions(projectId, path as string),
    enabled: path !== null,
  });
  const { data: version } = useQuery({
    queryKey: ["history", projectId, path, chosen],
    queryFn: () => getVersion(projectId, path as string, chosen as string),
    enabled: path !== null && chosen !== null,
  });

  const restore = async () => {
    if (!path || !version) return;
    try {
      const current = await getFile(projectId, path);
      await putFile(projectId, path, version.content, current.hash);
      await qc.invalidateQueries({ queryKey: ["history", projectId, path] });
      notify(t("history.restored"));
      close(false);
    } catch (e) {
      notify(e instanceof Error ? e.message : String(e));
    }
  };

  const when = (iso: string) => new Date(iso).toLocaleString(document.documentElement.lang);
  return (
    <Drawer title={t("history.title")} onClose={() => close(false)} width={440}>
      {path === null ? (
        <p className="text-muted">{t("history.noSection")}</p>
      ) : versions.length === 0 ? (
        <p className="text-muted">{t("history.empty")}</p>
      ) : (
        <>
          <p className="m-0 mt-2 text-[13px] text-muted">{t("history.hint")}</p>
          <ul className="m-0 mt-2 list-none p-0">
            {versions.map((v) => (
              <li key={v.id}>
                <button
                  type="button"
                  aria-pressed={chosen === v.id}
                  onClick={() => setChosen(v.id)}
                  className={`w-full rounded-ui px-2 py-1.5 text-left hover:bg-surface-2 ${chosen === v.id ? "bg-surface-2" : ""}`}
                >
                  <span className="block">{when(v.at)}</span>
                  <span className="block truncate text-[12px] text-muted">{v.preview}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
      {version && (
        <div className="mt-3">
          <pre
            data-testid="history-text"
            className="m-0 max-h-72 overflow-auto whitespace-pre-wrap rounded-ui border border-border bg-surface p-2 text-[12px]"
          >
            {version.content}
          </pre>
          <button
            type="button"
            onClick={() => void restore()}
            className="mt-2 rounded-ui bg-accent px-3 py-1.5 text-accent-fg"
          >
            {t("history.restore")}
          </button>
        </div>
      )}
    </Drawer>
  );
}
