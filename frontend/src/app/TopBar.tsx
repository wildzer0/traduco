import { useT } from "../lib/i18n";
import { usePrefs } from "../lib/prefs";

export function TopBar() {
  const t = useT();
  const toggleSidebar = usePrefs((s) => s.toggleSidebar);
  return (
    <header className="flex h-12 shrink-0 items-center gap-3 border-b border-border bg-surface px-3">
      <button
        type="button"
        aria-label={t("topbar.toggleSidebar")}
        title={t("topbar.toggleSidebar")}
        onClick={toggleSidebar}
        className="flex size-8 items-center justify-center rounded-ui text-muted hover:bg-surface-2"
      >
        <svg
          width="16"
          height="16"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          aria-hidden
        >
          <rect x="1.75" y="2.75" width="12.5" height="10.5" rx="1.5" strokeWidth="1.5" />
          <path d="M6 3v10" strokeWidth="1.5" />
        </svg>
      </button>
      <span className="font-semibold">{t("app.name")}</span>
      <span className="text-muted">{t("topbar.noProject")}</span>
    </header>
  );
}
