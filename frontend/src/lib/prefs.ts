import { create } from "zustand";

export type Theme = "system" | "light" | "dark";
export type Locale = "it" | "en";
export type EditorMode = "document" | "markdown";

const KEY = "traduco.prefs";

interface Stored {
  theme: Theme;
  locale: Locale;
  editorMode: EditorMode;
}

function detectLocale(): Locale {
  return navigator.language.toLowerCase().startsWith("it") ? "it" : "en";
}

function load(): Stored {
  const fallback: Stored = { theme: "system", locale: detectLocale(), editorMode: "document" };
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return fallback;
    const data = JSON.parse(raw) as Partial<Stored>;
    return {
      theme: data.theme === "light" || data.theme === "dark" ? data.theme : "system",
      locale: data.locale === "it" || data.locale === "en" ? data.locale : fallback.locale,
      editorMode: data.editorMode === "markdown" ? "markdown" : "document",
    };
  } catch {
    return fallback;
  }
}

export function applyPrefs({ theme, locale }: Pick<Stored, "theme" | "locale">): void {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
  root.lang = locale;
}

interface PrefsState extends Stored {
  sidebarOpen: boolean;
  settingsOpen: boolean;
  setSettingsOpen: (open: boolean) => void;
  setTheme: (theme: Theme) => void;
  setLocale: (locale: Locale) => void;
  setEditorMode: (mode: EditorMode) => void;
  toggleSidebar: () => void;
}

function persist({ theme, locale, editorMode }: Stored): void {
  applyPrefs({ theme, locale });
  try {
    localStorage.setItem(KEY, JSON.stringify({ theme, locale, editorMode }));
  } catch {
    // storage unavailable (private mode): preferences last for the session only
  }
}

export const usePrefs = create<PrefsState>((set, get) => ({
  ...load(),
  sidebarOpen: true,
  settingsOpen: false,
  setSettingsOpen: (settingsOpen) => set({ settingsOpen }),
  setTheme: (theme) => {
    persist({ ...get(), theme });
    set({ theme });
  },
  setLocale: (locale) => {
    persist({ ...get(), locale });
    set({ locale });
  },
  setEditorMode: (editorMode) => {
    persist({ ...get(), editorMode });
    set({ editorMode });
  },
  toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
}));
