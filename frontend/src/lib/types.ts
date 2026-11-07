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

export type Tone = "formale" | "neutro" | "informale";

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
  /** Tone set in the section front matter, or `null` to follow the project. */
  tone: Tone | null;
  project_tone: Tone;
  note: string;
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

export type SkeletonStatus = "ok" | "missing" | "empty" | "out_of_order" | "misplaced";

export interface SkeletonItem {
  id: string;
  title: string;
  mandatory: boolean;
  status: SkeletonStatus;
  path: string | null;
  guide: string;
}

export interface SkeletonReport {
  conform: boolean;
  items: SkeletonItem[];
  extra: string[];
}

export interface BundledSkeleton {
  id: string;
  nome: string;
}

export interface GlossaryEntry {
  sorgente: string;
  destinazione: Record<string, string>;
  vietati: Record<string, string[]>;
  non_tradurre: boolean;
  note: string;
}

export interface ReviewRow extends SegmentRow {
  path: string;
  section: string;
}

export interface ReviewData {
  segments: ReviewRow[];
  counts: Partial<Record<SegmentStatus, number>>;
}

export type AssistAction =
  | "correct"
  | "rephrase"
  | "concise"
  | "simple"
  | "formale"
  | "neutro"
  | "informale";

export interface Suggestion {
  id: string;
  key: string;
  source_hash: string;
  category: string;
  message: string;
  suggestion: string;
  origin: "model" | "rule" | "guide";
  status: "open" | "dismissed" | "applied";
}

export interface TemplateInfo {
  name: string;
  default: boolean;
  has_mapping: boolean;
}

export interface TemplateStyle {
  id: string;
  name: string;
  kind: "paragraph" | "table";
  custom: boolean;
  outline_level: number | null;
  has_numbering: boolean;
}

export interface TemplateMapping {
  contenuto: string;
  stili: Record<string, string>;
  numerazione_titoli: boolean;
  campi_mancanti_ammessi: boolean;
}

export interface TemplateDetail {
  name: string;
  styles: TemplateStyle[];
  placeholders: { name: string; where: string; count: number }[];
  fields: string[];
  has_content: boolean;
  has_revisions: boolean;
  has_toc: boolean;
  roles: string[];
  mapping: TemplateMapping;
  problems: string[];
}

export type ExportFormat = "docx" | "pdf" | "odt";
export type ExportScope = "section" | "chapter" | "project";
export type ExportLanguage = "ufficiale" | "sorgente";

export interface ExportStatus {
  id: string;
  state: "running" | "done" | "failed";
  progress: number;
  message: string;
  warnings: string[];
  error: { code: string; message: string; details: Record<string, unknown> } | null;
  filename: string | null;
}

export interface ModelDownload {
  state: "none" | "unavailable" | "downloading" | "ready" | "error";
  model?: string;
  completed?: number;
  total?: number | null;
  error?: string;
}

export interface Capabilities {
  pandoc: { available: boolean };
  libreoffice: { available: boolean };
  formats: ExportFormat[];
  model: ModelDownload;
}
