import { create } from "zustand";
import { languageContext } from "./language";

interface PreviewState {
  /** Section shown in the preview and its current text (updated while the user types). */
  path: string | null;
  text: string;
  /** Top-level block at the top of the editor viewport, to keep the preview aligned. */
  topBlock: number;
  /** What the right column shows: the translation (default) or the rendered source. */
  mode: "translated" | "source";
  setMode: (mode: "translated" | "source") => void;
  /** Target language shown (`null` = the official one); additional languages are RF-21b. */
  language: string | null;
  setLanguage: (language: string | null) => void;
  setText: (path: string, text: string) => void;
  setTopBlock: (index: number) => void;
  clear: () => void;
}

export const usePreview = create<PreviewState>((set) => ({
  path: null,
  text: "",
  topBlock: 0,
  mode: "translated",
  setMode: (mode) => set({ mode }),
  language: null,
  setLanguage: (language) => {
    languageContext.lang = language;
    set({ language });
  },
  setText: (path, text) => set({ path, text }),
  setTopBlock: (topBlock) => set({ topBlock }),
  clear: () => set({ path: null, text: "", topBlock: 0 }),
}));
