import { Outlet } from "@tanstack/react-router";
import { usePrefs } from "../lib/prefs";
import { useShortcuts } from "../lib/shortcuts";
import { SettingsDrawer } from "./SettingsDrawer";
import { StatusBar } from "./StatusBar";
import { TopBar } from "./TopBar";

export function AppShell() {
  const settingsOpen = usePrefs((s) => s.settingsOpen);
  const setSettingsOpen = usePrefs((s) => s.setSettingsOpen);
  useShortcuts();
  return (
    <div className="flex h-full flex-col">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <Outlet />
      </div>
      <StatusBar />
      {settingsOpen && <SettingsDrawer onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
