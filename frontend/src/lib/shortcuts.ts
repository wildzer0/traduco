import { useEffect } from "react";
import { usePrefs } from "./prefs";
import { usePreview } from "./preview-store";
import { useView } from "./view-store";

/** Single source of truth for keyboard shortcuts (docs/03-ui.md). */
export const SHORTCUTS = {
  toggleSidebar: { key: "b", ctrlOrMeta: true },
  toggleSource: { key: "p", ctrlOrMeta: true, shift: true },
} as const;

function isEditable(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export function useShortcuts(): void {
  const toggleSidebar = usePrefs((s) => s.toggleSidebar);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mode = { "1": "write", "2": "review", "3": "focus" }[e.key] as
        | "write"
        | "review"
        | "focus"
        | undefined;
      if (mode && (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey) {
        e.preventDefault();
        useView.getState().setMode(mode);
        return;
      }
      if (e.key.toLowerCase() === "e" && (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey) {
        if (!location.pathname.startsWith("/p/")) return;
        e.preventDefault();
        useView.getState().setExportOpen(true, true); // repeat the last export
        return;
      }
      const src = SHORTCUTS.toggleSource;
      if (e.key.toLowerCase() === src.key && (e.ctrlKey || e.metaKey) && e.shiftKey) {
        e.preventDefault();
        const { mode, setMode } = usePreview.getState();
        setMode(mode === "source" ? "translated" : "source");
        return;
      }
      const s = SHORTCUTS.toggleSidebar;
      if (e.key.toLowerCase() === s.key && (e.ctrlKey || e.metaKey) && !isEditable(e.target)) {
        e.preventDefault();
        toggleSidebar();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleSidebar]);
}
