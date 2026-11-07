import { useEffect } from "react";
import { useT } from "../lib/i18n";
import { type Locale, type Theme, usePrefs } from "../lib/prefs";

interface Props {
  onClose: () => void;
}

export function SettingsDrawer({ onClose }: Props) {
  const t = useT();
  const { theme, locale, setTheme, setLocale } = usePrefs();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const field = "mt-1 w-full rounded-ui border border-border bg-surface px-2 py-1";
  return (
    <aside
      role="dialog"
      aria-label={t("settings.title")}
      className="fixed inset-y-0 right-0 z-10 w-[420px] max-w-full border-l border-border bg-surface p-4 shadow-lg"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">{t("settings.title")}</h2>
        <button type="button" onClick={onClose} className="rounded-ui px-2 py-1 hover:bg-surface-2">
          {t("settings.close")}
        </button>
      </div>
      <label className="mt-4 block">
        {t("settings.language")}
        <select
          className={field}
          value={locale}
          onChange={(e) => setLocale(e.target.value as Locale)}
        >
          <option value="it">{t("lang.it")}</option>
          <option value="en">{t("lang.en")}</option>
        </select>
      </label>
      <label className="mt-4 block">
        {t("settings.theme")}
        <select className={field} value={theme} onChange={(e) => setTheme(e.target.value as Theme)}>
          <option value="system">{t("settings.theme.system")}</option>
          <option value="light">{t("settings.theme.light")}</option>
          <option value="dark">{t("settings.theme.dark")}</option>
        </select>
      </label>
    </aside>
  );
}
