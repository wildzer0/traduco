import type {
  AssetSaved,
  BundledSkeleton,
  FileContent,
  LlmStatus,
  NodeResult,
  ProjectSummary,
  SkeletonReport,
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
