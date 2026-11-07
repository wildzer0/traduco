import type {
  AssetSaved,
  AssistAction,
  BundledSkeleton,
  Capabilities,
  ExportFormat,
  ExportLanguage,
  ExportScope,
  ExportStatus,
  FileContent,
  GlossaryEntry,
  ImportJob,
  ImportProposal,
  LlmStatus,
  NodeResult,
  ProjectSummary,
  ReviewData,
  SegmentRow,
  SkeletonReport,
  Suggestion,
  TemplateDetail,
  TemplateInfo,
  TemplateMapping,
  Tone,
  TranslationView,
  TreeNode,
} from "./types";

export interface Health {
  status: string;
  version: string;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details: Record<string, unknown> };
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) {
    let code = `http_${res.status}`;
    let message = res.statusText;
    let details: Record<string, unknown> = {};
    try {
      const body = (await res.json()) as ApiErrorBody;
      code = body.error.code;
      message = body.error.message;
      details = body.error.details ?? {};
    } catch {
      // non-JSON error body: keep the HTTP status text
    }
    throw new ApiError(res.status, code, message, details);
  }
  return (await res.json()) as T;
}

export const getHealth = (): Promise<Health> => api<Health>("/health");

function json(method: string, body: unknown, headers: Record<string, string> = {}): RequestInit {
  return {
    method,
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  };
}

const enc = encodeURIComponent;
const base = (id: string) => `/projects/${enc(id)}`;

export const listProjects = (): Promise<ProjectSummary[]> => api("/projects");

export const createProject = (body: {
  nome?: string;
  lingua_sorgente?: string;
  lingua_ufficiale?: string;
  esempio?: boolean;
  scheletro?: string;
  scheletro_testo?: string;
}): Promise<ProjectSummary> => api("/projects", json("POST", body));

export const getTree = (id: string): Promise<{ nodes: TreeNode[] }> => api(`${base(id)}/tree`);

export const createNode = (
  id: string,
  body: { kind: "chapter" | "section"; title: string; parent: string | null },
): Promise<NodeResult> => api(`${base(id)}/nodes`, json("POST", body));

export const renameNode = (id: string, path: string, title: string): Promise<NodeResult> =>
  api(`${base(id)}/nodes`, json("PATCH", { path, title }));

export const moveNode = (
  id: string,
  path: string,
  parent: string | null,
  index: number | null,
): Promise<NodeResult> =>
  api(`${base(id)}/nodes`, json("PATCH", { path, move: true, parent, index }));

export const deleteNode = (id: string, path: string): Promise<{ trash: string }> =>
  api(`${base(id)}/nodes?path=${enc(path)}`, { method: "DELETE" });

export const getFile = (id: string, path: string): Promise<FileContent> =>
  api(`${base(id)}/files?path=${enc(path)}`);

export const putFile = (
  id: string,
  path: string,
  content: string,
  hash: string,
): Promise<{ path: string; hash: string }> =>
  api(`${base(id)}/files?path=${enc(path)}`, json("PUT", { content }, { "If-Match": `"${hash}"` }));

export const uploadImage = (
  id: string,
  section: string,
  file: Blob,
  filename: string,
): Promise<AssetSaved> =>
  api(`${base(id)}/assets?section=${enc(section)}&filename=${enc(filename)}`, {
    method: "POST",
    body: file,
  });

/** URL of an image stored under a chapter's ``img/`` folder. */
export const assetUrl = (id: string, path: string): string =>
  `/api${base(id)}/assets?path=${enc(path)}`;

export const getTranslation = (projectId: string, path: string): Promise<TranslationView> =>
  api(`${base(projectId)}/translation?path=${enc(path)}`);

export const retranslate = (
  projectId: string,
  scope: "section" | "chapter" | "project",
  path?: string,
): Promise<{ sections: number; queued: number }> =>
  api(`${base(projectId)}/retranslate`, json("POST", { scope, path }));

export const getLlmStatus = (): Promise<LlmStatus> => api("/llm/status");

export const listSkeletons = (): Promise<BundledSkeleton[]> => api("/skeletons");

/** `null` when the project has no skeleton. */
export const getSkeletonCheck = async (id: string): Promise<SkeletonReport | null> => {
  try {
    return await api<SkeletonReport>(`${base(id)}/skeleton/check`);
  } catch (e) {
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
};

export const createMissing = (id: string): Promise<{ created: string[] }> =>
  api(`${base(id)}/skeleton/create-missing`, json("POST", {}));

// --- glossary, segments, review ------------------------------------------------------------

export const getGlossary = (id: string): Promise<GlossaryEntry[]> => api(`${base(id)}/glossary`);

export const putGlossary = (id: string, entries: GlossaryEntry[]): Promise<GlossaryEntry[]> =>
  api(`${base(id)}/glossary`, json("PUT", entries));

export type SegmentChange =
  | { target: string }
  | { locked: boolean }
  | { action: "approve" | "accept" | "dismiss" | "retranslate" | "diverge" };

export const putSegment = (
  id: string,
  path: string,
  key: string,
  change: SegmentChange,
): Promise<SegmentRow> =>
  api(`${base(id)}/segments/${enc(key)}?path=${enc(path)}`, json("PUT", change));

export const instructSegment = (
  id: string,
  path: string,
  key: string,
  instruction: string,
  alternatives = false,
): Promise<{ proposals: string[] }> =>
  api(
    `${base(id)}/segments/${enc(key)}/instruct?path=${enc(path)}`,
    json("POST", { instruction, alternatives }),
  );

export const backTranslate = (id: string, path: string, key: string): Promise<{ text: string }> =>
  api(`${base(id)}/segments/${enc(key)}/back-translate?path=${enc(path)}`, { method: "POST" });

export const applySource = (
  id: string,
  path: string,
  key: string,
  text: string,
): Promise<SegmentRow> =>
  api(`${base(id)}/segments/${enc(key)}/apply-source?path=${enc(path)}`, json("POST", { text }));

export const getReview = (id: string): Promise<ReviewData> => api(`${base(id)}/review`);

export const patchSectionMeta = (
  id: string,
  path: string,
  meta: { tono: Tone | null; contesto: string | null },
): Promise<{ tono: Tone | null; contesto: string }> =>
  api(`${base(id)}/sections/meta?path=${enc(path)}`, json("PATCH", meta));

export const patchProject = (
  id: string,
  body: { tono?: Tone; metadati?: Record<string, string>; revisioni?: ProjectRevision[] },
): Promise<Record<string, unknown>> => api(base(id), json("PATCH", body));

export interface ProjectRevision {
  rev: string;
  data: string;
  descrizione: string;
}

export const getProject = (id: string): Promise<{ tono: Tone } & Record<string, unknown>> =>
  api(base(id));

export interface ModelSettings {
  llm_base_url: string;
  llm_model: string;
  has_api_key: boolean;
}

export const getSettings = (): Promise<ModelSettings> => api("/settings");

export const putSettings = (body: {
  llm_base_url?: string;
  llm_model?: string;
  llm_api_key?: string;
}): Promise<ModelSettings> => api("/settings", json("PUT", body));

// --- writing companion ---------------------------------------------------------------------

export const assist = (
  id: string,
  body: { path: string; key: string; action: AssistAction; instruction?: string },
): Promise<{ original: string; proposal: string; changed: boolean }> =>
  api(`${base(id)}/assist`, json("POST", body));

export const applyAssist = (
  id: string,
  body: { path: string; key: string; text: string; suggestion_id?: string },
): Promise<{ path: string; key: string }> => api(`${base(id)}/assist/apply`, json("POST", body));

export const runCheck = (
  id: string,
  path: string,
  requirements: boolean,
): Promise<{ items: Suggestion[] }> =>
  api(`${base(id)}/check`, json("POST", { path, requirements }));

export const getCheck = (id: string, path: string): Promise<{ items: Suggestion[] }> =>
  api(`${base(id)}/check?path=${enc(path)}`);

export const dismissSuggestion = (id: string, path: string, suggestionId: string) =>
  api(`${base(id)}/check/dismiss`, json("POST", { path, suggestion_id: suggestionId }));

// --- templates and export ------------------------------------------------------------------

export const listTemplates = (id: string): Promise<TemplateInfo[]> => api(`${base(id)}/templates`);

export const getTemplate = (id: string, name: string): Promise<TemplateDetail> =>
  api(`${base(id)}/templates/${enc(name)}`);

export const uploadTemplate = (id: string, file: File): Promise<TemplateDetail> =>
  api(`${base(id)}/templates?filename=${enc(file.name)}`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: file,
  });

export const putTemplateMapping = (
  id: string,
  name: string,
  mapping: TemplateMapping,
): Promise<TemplateDetail> => api(`${base(id)}/templates/${enc(name)}`, json("PUT", mapping));

export const setDefaultTemplate = (id: string, name: string): Promise<{ default: string }> =>
  api(`${base(id)}/templates/${enc(name)}/default`, { method: "PUT" });

export const deleteTemplate = async (id: string, name: string): Promise<void> => {
  const res = await fetch(`/api${base(id)}/templates/${enc(name)}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError(res.status, `http_${res.status}`, res.statusText);
};

export const startExport = (
  id: string,
  body: {
    scope: ExportScope;
    path?: string;
    language: ExportLanguage;
    template?: string;
    format?: ExportFormat;
  },
): Promise<ExportStatus> => api(`${base(id)}/export`, json("POST", body));

export const getExport = (id: string, job: string): Promise<ExportStatus> =>
  api(`${base(id)}/export/${enc(job)}`);

export const exportDownloadUrl = (id: string, job: string): string =>
  `/api${base(id)}/export/${enc(job)}/download`;

export const addExampleTemplate = (id: string): Promise<TemplateDetail> =>
  api(`${base(id)}/templates/example`, { method: "POST" });

export const getCapabilities = (): Promise<Capabilities> => api("/capabilities");

// --- import of a revised document ----------------------------------------------------------
export const startImport = (id: string, file: File): Promise<ImportJob> =>
  api(`${base(id)}/import?filename=${enc(file.name)}`, {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: file,
  });

export const getImport = (id: string, job: string): Promise<ImportJob> =>
  api(`${base(id)}/import/${enc(job)}`);

export const decideProposal = (
  id: string,
  job: string,
  proposal: string,
  action: "accept" | "reject",
  source?: string,
): Promise<ImportProposal> =>
  api(
    `${base(id)}/import/${enc(job)}/proposals/${enc(proposal)}`,
    json("POST", { action, ...(source !== undefined ? { source } : {}) }),
  );

// --- template wizard -------------------------------------------------------------------------
export interface WizardOptions {
  page: "A4" | "Letter";
  font_body: string;
  font_heading: string;
  size_body: number;
  color: string;
  margin_cm: number;
  cover: boolean;
  cover_fields: string[];
  header_text: string;
  footer_text: string;
  page_numbers: boolean;
  logo_in_header: boolean;
  toc: boolean;
  revisions: boolean;
  language: "it" | "en";
}

export const wizardFonts = (): Promise<string[]> => api("/template-wizard/fonts");

export const createTemplateWithWizard = (
  id: string,
  body: { nome: string; opzioni: WizardOptions; logo_base64?: string },
): Promise<TemplateDetail> => api(`${base(id)}/templates/wizard`, json("POST", body));
