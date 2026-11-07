import { create } from "zustand";

interface AssistState {
  /** Top-level block under the editor cursor, asked from the toolbar; the preview resolves it. */
  request: { blockIndex: number } | null;
  requestAssist: (blockIndex: number) => void;
  clearRequest: () => void;
  checkOpen: boolean;
  setCheckOpen: (open: boolean) => void;
}

export const useAssist = create<AssistState>((set) => ({
  request: null,
  requestAssist: (blockIndex) => set({ request: { blockIndex } }),
  clearRequest: () => set({ request: null }),
  checkOpen: false,
  setCheckOpen: (checkOpen) => set({ checkOpen }),
}));
