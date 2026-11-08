import { type ReactNode, useEffect } from "react";
import { useT } from "../lib/i18n";
import { LIMITS, useLayout } from "../lib/layout";
import { ResizeHandle } from "./ResizeHandle";

/**
 * The side panels of the app. The title and the close button stay in view while the content
 * scrolls, and the panel can be made wider or narrower by dragging its left edge.
 */
export function Drawer({
  title,
  onClose,
  width = 420,
  closeOnEscape = true,
  children,
}: {
  title: string;
  onClose: () => void;
  /** Width in pixels until the author drags it. */
  width?: number;
  /** False while something on top of the panel (a dialog) uses Escape itself. */
  closeOnEscape?: boolean;
  children: ReactNode;
}) {
  const t = useT();
  const chosen = useLayout((s) => s.drawer);
  const setDrawer = useLayout((s) => s.setDrawer);
  const size = chosen ?? width;
  const max = Math.min(LIMITS.drawer[1], Math.max(LIMITS.drawer[0], window.innerWidth - 80));

  useEffect(() => {
    if (!closeOnEscape) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, closeOnEscape]);

  return (
    <aside
      role="dialog"
      aria-label={title}
      style={{ width: size }}
      className="fixed inset-y-0 right-0 z-10 flex max-w-full flex-col border-l border-border bg-surface shadow-pop"
    >
      <ResizeHandle
        label={t("layout.drawerWidth")}
        value={size}
        min={LIMITS.drawer[0]}
        max={max}
        step={24}
        invert
        onChange={(px) => setDrawer(Math.min(px, max))}
        onReset={() => setDrawer(null)}
        className="absolute inset-y-0 left-0 -translate-x-1/2"
      />
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-border px-4 py-2">
        <h2 className="m-0 min-w-0 truncate text-base font-semibold">{title}</h2>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 rounded-ui px-2 py-1 hover:bg-surface-2"
        >
          {t("drawer.close")}
        </button>
      </header>
      <div className="flex min-h-0 flex-1 flex-col overflow-y-auto p-4">{children}</div>
    </aside>
  );
}
