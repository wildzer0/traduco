import { api } from "../../lib/api";

export type DiagramTheme = "default" | "dark";

export async function sha256Hex(text: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

type Mermaid = typeof import("mermaid")["default"];
let loaded: Promise<Mermaid> | null = null;
let queue: Promise<unknown> = Promise.resolve();
let counter = 0;

/** The diagram engine itself could not be loaded (not a mistake in the diagram). */
export class DiagramEngineError extends Error {}

/** mermaid is large: load it only when a document actually has a diagram. */
function loadMermaid(): Promise<Mermaid> {
  loaded ??= import("mermaid").then(
    (m) => m.default,
    (cause: unknown) => {
      loaded = null; // try again next time
      throw new DiagramEngineError(cause instanceof Error ? cause.message : String(cause));
    },
  );
  return loaded;
}

/**
 * Render Mermaid code to an SVG string in the browser (ADR-012). Calls are serialised because
 * mermaid keeps global state. Labels are plain SVG text (no foreignObject) so the SVG can also be
 * rasterised to PNG without tainting the canvas.
 */
export function renderDiagram(code: string, theme: DiagramTheme): Promise<string> {
  const run = async () => {
    const mermaid = await loadMermaid();
    mermaid.initialize({
      startOnLoad: false,
      securityLevel: "strict",
      theme,
      htmlLabels: false,
      flowchart: { htmlLabels: false },
    });
    const id = `traduco-diagram-${counter++}`;
    try {
      const { svg } = await mermaid.render(id, code);
      return svg;
    } finally {
      document.getElementById(id)?.remove(); // mermaid leaves its scratch element behind on errors
      document.getElementById(`d${id}`)?.remove();
    }
  };
  const result = queue.then(run, run);
  queue = result.catch(() => {});
  return result;
}

function svgSize(svg: string): { width: number; height: number } {
  const viewBox = /viewBox="[\d.-]+ [\d.-]+ ([\d.]+) ([\d.]+)"/.exec(svg);
  if (viewBox) return { width: Number(viewBox[1]), height: Number(viewBox[2]) };
  const w = /\swidth="([\d.]+)/.exec(svg);
  const h = /\sheight="([\d.]+)/.exec(svg);
  return { width: Number(w?.[1] ?? 800), height: Number(h?.[1] ?? 600) };
}

/** PNG at 2x as base64 (without the data: prefix), or `null` if the browser refuses to rasterise. */
export async function svgToPngBase64(svg: string, scale = 2): Promise<string | null> {
  const { width, height } = svgSize(svg);
  const image = new Image();
  const ready = new Promise<void>((resolve, reject) => {
    image.onload = () => resolve();
    image.onerror = () => reject(new Error("svg not loadable"));
  });
  image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
  try {
    await ready;
    const canvas = document.createElement("canvas");
    canvas.width = Math.ceil(width * scale);
    canvas.height = Math.ceil(height * scale);
    const ctx = canvas.getContext("2d");
    if (!ctx) return null;
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(image, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/png").split(",")[1] ?? null;
  } catch {
    return null;
  }
}

const uploaded = new Set<string>();

/** Store the light-theme rendering of a diagram in the project cache so the export can use it. */
export async function cacheDiagram(projectId: string, hash: string, code: string): Promise<void> {
  const key = `${projectId}:${hash}`;
  if (uploaded.has(key)) return;
  uploaded.add(key);
  try {
    const svg = await renderDiagram(code, "default");
    const png = await svgToPngBase64(svg);
    if (!png) throw new Error("png");
    await api(`/projects/${encodeURIComponent(projectId)}/diagrams/${hash}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ svg, png_base64: png }),
    });
  } catch {
    uploaded.delete(key); // try again next time the section is saved
  }
}
