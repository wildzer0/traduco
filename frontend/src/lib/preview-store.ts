import { create } from "zustand";

interface PreviewState {
  /** Section shown in the preview and its current text (updated while the user types). */
  path: string | null;
  text: string;
  /** Top-level block at the top of the editor viewport, to keep the preview aligned. */
  topBlock: number;
  setText: (path: string, text: string) => void;
  setTopBlock: (index: number) => void;
  clear: () => void;
}

export const usePreview = create<PreviewState>((set) => ({
  path: null,
  text: "",
  topBlock: 0,
  setText: (path, text) => set({ path, text }),
  setTopBlock: (topBlock) => set({ topBlock }),
  clear: () => set({ path: null, text: "", topBlock: 0 }),
}));
