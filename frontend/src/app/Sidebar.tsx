import { Tree } from "../features/tree/Tree";
import { useT } from "../lib/i18n";
import { usePrefs } from "../lib/prefs";

interface Props {
  projectId: string;
  selected: string | null;
  onSelect: (path: string | null) => void;
}

const itemClass = "block w-full rounded-ui px-2 py-1 text-left";

export function Sidebar({ projectId, selected, onSelect }: Props) {
  const t = useT();
  const setSettingsOpen = usePrefs((s) => s.setSettingsOpen);
  return (
    <nav
      aria-label={t("sidebar.label")}
      className="flex w-60 shrink-0 flex-col border-r border-border bg-surface-2 p-2"
    >
      <h2 className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
        {t("sidebar.label")}
      </h2>
      <Tree projectId={projectId} selected={selected} onSelect={onSelect} />
      <div className="mt-2 border-t border-border pt-2">
        {(["sidebar.glossary", "sidebar.templates"] as const).map((key) => (
          <button
            key={key}
            type="button"
            disabled
            title={t("sidebar.soon")}
            className={`${itemClass} cursor-not-allowed text-muted opacity-60`}
          >
            {t(key)}
          </button>
        ))}
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          className={`${itemClass} hover:bg-surface`}
        >
          {t("sidebar.settings")}
        </button>
      </div>
    </nav>
  );
}
