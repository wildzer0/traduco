import { create } from "zustand";

interface PreviewState {
  /** Section shown in the preview and its current text (updated while the user types). */
  path: string | null;
  text: string;
  /** Top-level block at the top of the editor viewport, to keep the preview aligned. */
  topBlock: number;
  /** What the right column shows: the translation (default) or the rendered source. */
  mode: "translated" | "source";
  setMode: (mode: "translated" | "source") => void;
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
  setText: (path, text) => set({ path, text }),
  setTopBlock: (topBlock) => set({ topBlock }),
  clear: () => set({ path: null, text: "", topBlock: 0 }),
}));
