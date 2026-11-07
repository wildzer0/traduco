import { useEffect } from "react";
import { usePrefs } from "./prefs";
import { usePreview } from "./preview-store";

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
