import { useEffect } from "react";
import { usePrefs } from "./prefs";

/** Single source of truth for keyboard shortcuts (docs/03-ui.md). */
export const SHORTCUTS = {
  toggleSidebar: { key: "b", ctrlOrMeta: true },
} as const;

function isEditable(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}

export function useShortcuts(): void {
  const toggleSidebar = usePrefs((s) => s.toggleSidebar);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
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
