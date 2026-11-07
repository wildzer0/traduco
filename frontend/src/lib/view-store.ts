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
  templatesOpen: boolean;
  setTemplatesOpen: (open: boolean) => void;
  exportOpen: boolean;
  /** Ctrl+E: open the panel and run the last choice at once. */
  exportAutoRun: boolean;
  setExportOpen: (open: boolean, autoRun?: boolean) => void;
  requirementsOpen: boolean;
  setRequirementsOpen: (open: boolean) => void;
  paletteOpen: boolean;
  /** `text` opens the palette ready to search the text of the project (Ctrl+Shift+F). */
  paletteMode: "all" | "text";
  setPalette: (open: boolean, mode?: "all" | "text") => void;
  helpOpen: boolean;
  setHelpOpen: (open: boolean) => void;
  languagesOpen: boolean;
  setLanguagesOpen: (open: boolean) => void;
  snippetsOpen: boolean;
  setSnippetsOpen: (open: boolean) => void;
  issuesOpen: boolean;
  setIssuesOpen: (open: boolean) => void;
  commentsOpen: boolean;
  setCommentsOpen: (open: boolean) => void;
  importOpen: boolean;
  setImportOpen: (open: boolean) => void;
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
  templatesOpen: false,
  setTemplatesOpen: (templatesOpen) => set({ templatesOpen }),
  exportOpen: false,
  exportAutoRun: false,
  setExportOpen: (exportOpen, autoRun = false) => set({ exportOpen, exportAutoRun: autoRun }),
  requirementsOpen: false,
  setRequirementsOpen: (requirementsOpen) => set({ requirementsOpen }),
  paletteOpen: false,
  paletteMode: "all",
  setPalette: (paletteOpen, paletteMode = "all") => set({ paletteOpen, paletteMode }),
  helpOpen: false,
  setHelpOpen: (helpOpen) => set({ helpOpen }),
  languagesOpen: false,
  setLanguagesOpen: (languagesOpen) => set({ languagesOpen }),
  snippetsOpen: false,
  setSnippetsOpen: (snippetsOpen) => set({ snippetsOpen }),
  issuesOpen: false,
  setIssuesOpen: (issuesOpen) => set({ issuesOpen }),
  commentsOpen: false,
  setCommentsOpen: (commentsOpen) => set({ commentsOpen }),
  importOpen: false,
  setImportOpen: (importOpen) => set({ importOpen }),
  glossaryOpen: false,
  glossaryDraft: null,
  openGlossary: (draft) => set({ glossaryOpen: true, glossaryDraft: draft ?? null }),
  closeGlossary: () => set({ glossaryOpen: false, glossaryDraft: null }),
}));
