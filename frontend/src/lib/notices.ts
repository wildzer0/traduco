import { create } from "zustand";

interface NoticeState {
  /** Latest error shown in the status area; successes stay silent (docs/03-ui.md). */
  message: string | null;
  show: (message: string) => void;
  clear: () => void;
}

let timer: ReturnType<typeof setTimeout> | undefined;

export const useNotices = create<NoticeState>((set) => ({
  message: null,
  show: (message) => {
    clearTimeout(timer);
    set({ message });
    timer = setTimeout(() => set({ message: null }), 8000);
  },
  clear: () => {
    clearTimeout(timer);
    set({ message: null });
  },
}));
