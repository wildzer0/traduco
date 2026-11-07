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
  ) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) {
    let code = `http_${res.status}`;
    let message = res.statusText;
    try {
      const body = (await res.json()) as ApiErrorBody;
      code = body.error.code;
      message = body.error.message;
    } catch {
      // non-JSON error body: keep the HTTP status text
    }
    throw new ApiError(res.status, code, message);
  }
  return (await res.json()) as T;
}

export const getHealth = (): Promise<Health> => api<Health>("/health");
