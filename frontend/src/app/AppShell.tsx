import { Outlet } from "@tanstack/react-router";
import { useEffect } from "react";
import { CommandPalette } from "../features/command-palette/CommandPalette";
import { ShortcutsHelp } from "../features/command-palette/ShortcutsHelp";
import { usePrefs } from "../lib/prefs";
import { useShortcuts } from "../lib/shortcuts";
import { loginUrl, useMe } from "../lib/team";
import { ModelBanner } from "./ModelBanner";
import { SettingsDrawer } from "./SettingsDrawer";
import { StatusBar } from "./StatusBar";
import { TopBar } from "./TopBar";

export function AppShell() {
  const settingsOpen = usePrefs((s) => s.settingsOpen);
  const setSettingsOpen = usePrefs((s) => s.setSettingsOpen);
  useShortcuts();
  const { data: me, isPending } = useMe();
  const mustLogIn = me?.mode === "team" && me.user === null;
  useEffect(() => {
    if (mustLogIn)
      window.location.href = loginUrl(window.location.pathname + window.location.search);
  }, [mustLogIn]);
  if (isPending || mustLogIn) return null; // nothing of the app is shown before the login
  return (
    <div className="flex h-full flex-col">
      <TopBar />
      <ModelBanner />
      <div className="flex min-h-0 flex-1">
        <Outlet />
      </div>
      <StatusBar />
      <CommandPalette />
      <ShortcutsHelp />
      {settingsOpen && <SettingsDrawer onClose={() => setSettingsOpen(false)} />}
    </div>
  );
}
