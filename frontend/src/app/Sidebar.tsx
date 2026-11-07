import { useT } from "../lib/i18n";

interface Props {
  onOpenSettings: () => void;
}

const itemClass = "block w-full rounded-ui px-2 py-1 text-left";

export function Sidebar({ onOpenSettings }: Props) {
  const t = useT();
  return (
    <nav
      aria-label={t("sidebar.label")}
      className="flex w-60 shrink-0 flex-col border-r border-border bg-surface-2 p-2"
    >
      <h2 className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
        {t("sidebar.label")}
      </h2>
      <p className="flex-1 px-2 py-1 text-muted">{t("sidebar.empty")}</p>
      <div className="border-t border-border pt-2">
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
        <button type="button" onClick={onOpenSettings} className={`${itemClass} hover:bg-surface`}>
          {t("sidebar.settings")}
        </button>
      </div>
    </nav>
  );
}
