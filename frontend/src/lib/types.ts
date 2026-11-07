export interface ProjectSummary {
  id: string;
  nome: string;
  lingua_sorgente: string;
  lingua_ufficiale: string;
}

export interface TreeNode {
  kind: "chapter" | "section";
  path: string;
  name: string;
  title: string;
  children: TreeNode[];
}

export interface NodeResult {
  path: string | null;
  renamed: Record<string, string>;
}

export interface FileContent {
  path: string;
  content: string;
  hash: string;
}

export interface AssetSaved {
  path: string;
  markdown: string;
}

export interface ProjectEvent {
  type:
    | "hello"
    | "file.changed"
    | "project.changed"
    | "glossary.changed"
    | "segment.queued"
    | "segment.updated"
    | "job.progress"
    | "llm.status";
  path?: string;
  change?: "added" | "modified" | "deleted";
  hash?: string | null;
  project?: string;
  /** segment.* events */
  lang?: string;
  key?: string;
  status?: string;
  /** job.progress */
  pending?: number;
  /** llm.status */
  online?: boolean;
  model?: string;
}

export type SegmentStatus = "queued" | "translated" | "needs_review" | "approved" | "diverged";

export interface SegmentRow {
  key: string;
  kind: string;
  line: number | null;
  end: number | null;
  source: string;
  target: string;
  status: SegmentStatus;
  locked: boolean;
  reason: string;
  pending_target: string | null;
}

export interface TranslationView {
  path: string;
  lang: string;
  /** The whole file with every translated segment substituted (untranslated ones keep the source). */
  markdown: string;
  segments: SegmentRow[];
  pending: number;
}

export interface LlmStatus {
  online: boolean;
  model: string;
  models: string[];
  error?: string;
  pending?: number;
}
