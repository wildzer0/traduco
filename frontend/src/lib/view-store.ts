import { create } from "zustand";
import type { GlossaryEntry, SegmentStatus } from "./types";

/** Writing (editor + preview), review (segment table) or focus (editor only) — docs/03-ui.md. */
export type ViewMode = "write" | "review" | "focus";
export type ReviewFilter = "all" | SegmentStatus | "locked";

interface ViewState {
  mode: ViewMode;
  setMode: (mode: ViewMode) => void;
  reviewFilter: ReviewFilter;
  setReviewFilter: (filter: ReviewFilter) => void;
  /** Segment to scroll to and highlight in the preview after navigating (F8, review table). */
  focusKey: string | null;
  setFocusKey: (key: string | null) => void;
  glossaryOpen: boolean;
  /** Entry prefilled when the glossary is opened from the preview's context menu. */
  glossaryDraft: Partial<GlossaryEntry> | null;
  openGlossary: (draft?: Partial<GlossaryEntry>) => void;
  closeGlossary: () => void;
}

export const useView = create<ViewState>((set) => ({
  mode: "write",
  setMode: (mode) => set({ mode }),
  reviewFilter: "all",
  setReviewFilter: (reviewFilter) => set({ reviewFilter }),
  focusKey: null,
  setFocusKey: (focusKey) => set({ focusKey }),
  glossaryOpen: false,
  glossaryDraft: null,
  openGlossary: (draft) => set({ glossaryOpen: true, glossaryDraft: draft ?? null }),
  closeGlossary: () => set({ glossaryOpen: false, glossaryDraft: null }),
}));
