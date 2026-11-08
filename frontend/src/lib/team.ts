import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { api } from "./api";

export interface Me {
  mode: "desktop" | "team";
  user: { sub: string; name: string; email: string; roles: string[]; permissions: string[] } | null;
}

export interface Person {
  sub: string;
  name: string;
  path: string | null;
  editing: boolean;
}

/** Who is using Traduco. Desktop mode (or a server without `/api/me`) answers "nobody to log in". */
export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => api<Me>("/me").catch((): Me => ({ mode: "desktop", user: null })),
    staleTime: Number.POSITIVE_INFINITY,
    retry: false,
  });
}

export const loginUrl = (next: string) => `/api/auth/login?next=${encodeURIComponent(next)}`;

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
  window.location.href = "/";
}

const BEAT_MS = 15_000;
/** While someone else holds the section, look again soon: it frees up when they leave. */
const WAIT_MS = 4_000;

/** Tell the server the person left (a closed tab or another page), so the lock is freed at once. */
function leave(projectId: string) {
  const url = `/api/projects/${encodeURIComponent(projectId)}/presence`;
  const body = new Blob([JSON.stringify({ path: null })], { type: "application/json" });
  if (!navigator.sendBeacon?.(url, body)) {
    void fetch(url, {
      method: "POST",
      body,
      keepalive: true,
      headers: { "Content-Type": "application/json" },
    }).catch(() => {});
  }
}

/** Free the locks of this person when they leave the project or close the page. */
export function useLeaveOnExit(projectId: string) {
  const { data: me } = useMe();
  const team = me?.mode === "team" && me.user !== null;
  useEffect(() => {
    if (!team) return;
    const onHide = () => leave(projectId);
    window.addEventListener("pagehide", onHide);
    return () => {
      window.removeEventListener("pagehide", onHide);
      leave(projectId);
    };
  }, [team, projectId]);
}

/**
 * Tell the server where the person is (every 15 s, which also keeps the lock of the section they
 * are editing) and get back who else is in the project. Only in team mode.
 */
export function usePresence(projectId: string, path: string | null) {
  const { data: me } = useMe();
  const team = me?.mode === "team" && me.user !== null;
  const canEdit = me?.user?.permissions.includes("edit_source") ?? false;
  const { data } = useQuery({
    queryKey: ["presence", projectId, path, canEdit],
    queryFn: () =>
      api<{ me: string; people: Person[] }>(`/projects/${encodeURIComponent(projectId)}/presence`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path, edit: canEdit && path !== null }),
      }),
    enabled: team,
    refetchInterval: (query) =>
      query.state.data?.people.some(
        (p) => p.sub !== query.state.data?.me && p.editing && p.path === path,
      )
        ? WAIT_MS
        : BEAT_MS,
    staleTime: 0,
    gcTime: 0,
  });
  const people = data?.people ?? [];
  const others = people.filter((p) => p.sub !== data?.me);
  const holder = path ? others.find((p) => p.editing && p.path === path) : undefined;
  return { team, people: others, lockedBy: holder?.name ?? null };
}
