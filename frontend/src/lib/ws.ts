import { useEffect, useRef } from "react";
import type { ProjectEvent } from "./types";

export function eventsUrl(
  projectId: string,
  loc: Pick<Location, "protocol" | "host"> = location,
): string {
  const scheme = loc.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${loc.host}/api/projects/${encodeURIComponent(projectId)}/events`;
}

export interface EventsOptions {
  /** Called for every event after the server's ``hello``. */
  onEvent: (event: ProjectEvent) => void;
  /** Called on every (re)connection: refetch what may have changed while disconnected. */
  onConnect?: () => void;
  create?: (url: string) => WebSocket;
}

/** Project event stream with automatic reconnection (1 s, doubling up to 15 s). Returns a closer. */
export function connectEvents(projectId: string, opts: EventsOptions): () => void {
  let socket: WebSocket | null = null;
  let closed = false;
  let attempt = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const open = () => {
    socket = (opts.create ?? ((u) => new WebSocket(u)))(eventsUrl(projectId));
    socket.onmessage = (m) => {
      const event = JSON.parse(String(m.data)) as ProjectEvent;
      if (event.type === "hello") {
        attempt = 0;
        opts.onConnect?.();
      } else opts.onEvent(event);
    };
    socket.onclose = () => {
      if (closed) return;
      timer = setTimeout(open, Math.min(1000 * 2 ** attempt++, 15_000));
    };
    socket.onerror = () => socket?.close();
  };
  open();

  return () => {
    closed = true;
    clearTimeout(timer);
    socket?.close();
  };
}

export function useProjectEvents(
  projectId: string | undefined,
  opts: Omit<EventsOptions, "create">,
): void {
  const latest = useRef(opts);
  latest.current = opts;
  useEffect(() => {
    if (!projectId) return;
    return connectEvents(projectId, {
      onEvent: (e) => latest.current.onEvent(e),
      onConnect: () => latest.current.onConnect?.(),
    });
  }, [projectId]);
}
