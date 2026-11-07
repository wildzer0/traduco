import { useState } from "react";
import { useT } from "../lib/i18n";
import { usePrefs } from "../lib/prefs";
import { useShortcuts } from "../lib/shortcuts";
import { SettingsDrawer } from "./SettingsDrawer";
import { Sidebar } from "./Sidebar";
import { StatusBar } from "./StatusBar";
import { TopBar } from "./TopBar";

export function Layout() {
  const t = useT();
  const sidebarOpen = usePrefs((s) => s.sidebarOpen);
  const [settingsOpen, setSettingsOpen] = useState(false);
  useShortcuts();

  return (
    <div className="flex h-full flex-col">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        {sidebarOpen && <Sidebar onOpenSettings={() => setSettingsOpen(true)} />}
        <main
          aria-label={t("editor.label")}
          className="flex min-w-0 flex-1 flex-col border-r border-border"
        >
          <div className="flex h-10 shrink-0 items-center border-b border-border px-3" />
          <p className="mx-auto w-full max-w-[72ch] p-6 text-[15px] text-muted">
            {t("editor.placeholder")}
          </p>
        </main>
        <section aria-label={t("preview.label")} className="flex min-w-0 flex-1 flex-col">
          <div className="flex h-10 shrink-0 items-center border-b border-border px-3 text-muted">
            {t("preview.title")}
          </div>
        </section>
      </div>
      <StatusBar />
      {settingsOpen && <SettingsDrawer onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
