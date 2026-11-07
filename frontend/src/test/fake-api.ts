import type { ProjectSummary, TreeNode } from "../lib/types";

export interface Call {
  method: string;
  url: string;
  body: unknown;
  headers: Record<string, string>;
}

type Handler = (call: Call) => { status?: number; body: unknown } | undefined;

/** Install a fetch stub that answers /api requests from handlers; returns the recorded calls. */
export function installFakeApi(handlers: Handler[]): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const raw = init?.body;
      const call: Call = {
        method: (init?.method ?? "GET").toUpperCase(),
        url,
        body: typeof raw === "string" ? JSON.parse(raw) : raw,
        headers: (init?.headers ?? {}) as Record<string, string>,
      };
      calls.push(call);
      for (const h of handlers) {
        const r = h(call);
        if (r) return new Response(JSON.stringify(r.body), { status: r.status ?? 200 });
      }
      return new Response(
        JSON.stringify({
          error: { code: "not_found", message: `no handler for ${url}`, details: {} },
        }),
        { status: 404 },
      );
    }),
  );
  return calls;
}

export const health: Handler = (c) =>
  c.url === "/api/health" ? { body: { status: "ok", version: "0.1.0" } } : undefined;

export const project = (id = "demo", nome = "Demo"): ProjectSummary => ({
  id,
  nome,
  lingua_sorgente: "it",
  lingua_ufficiale: "en",
});

export const section = (path: string, title: string): TreeNode => ({
  kind: "section",
  path,
  name: path.split("/").pop() ?? path,
  title,
  children: [],
});

export const chapter = (path: string, title: string, children: TreeNode[] = []): TreeNode => ({
  kind: "chapter",
  path,
  name: path.split("/").pop() ?? path,
  title,
  children,
});

export const demoTree = (): TreeNode[] => [
  chapter("capitoli/01-intro", "Introduzione", [
    section("capitoli/01-intro/01-scopo.md", "Scopo"),
    section("capitoli/01-intro/02-ambito.md", "Ambito"),
  ]),
  chapter("capitoli/02-inst", "Installazione", [
    section("capitoli/02-inst/01-req.md", "Requisiti"),
  ]),
];
