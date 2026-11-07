import { create } from "zustand";

interface TranslationState {
  /** `null` until the first status arrives. */
  online: boolean | null;
  model: string;
  /** Segments waiting for or being translated, across the project. */
  pending: number;
  setLlm: (online: boolean, model: string) => void;
  setPending: (pending: number) => void;
}

export const useTranslationState = create<TranslationState>((set) => ({
  online: null,
  model: "",
  pending: 0,
  setLlm: (online, model) => set({ online, model }),
  setPending: (pending) => set({ pending }),
}));
