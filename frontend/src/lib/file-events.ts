import type { ProjectEvent } from "./types";

type Listener = (event: ProjectEvent) => void;
const listeners = new Set<Listener>();

/** Fan-out of project events from the single WebSocket to interested components. */
export function emitFileEvent(event: ProjectEvent): void {
  for (const l of [...listeners]) l(event);
}

export function onFileEvent(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/**
 * After the server rewrote the open section (accepted suggestion, source update), ask the editor
 * to compare itself with the disk now instead of waiting for the file watcher, which can be slow
 * (polling on WSL and network drives).
 */
export function recheckOpenFile(): void {
  emitFileEvent({ type: "hello" });
}
