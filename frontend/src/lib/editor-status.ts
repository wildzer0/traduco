import { create } from "zustand";
import type { SaveStatus } from "../features/editor/autosaver";

/** Save state of the open section, shown in the status bar. */
export const useEditorStatus = create<{
  save: SaveStatus | null;
  setSave: (s: SaveStatus | null) => void;
}>((set) => ({
  save: null,
  setSave: (save) => set({ save }),
}));
