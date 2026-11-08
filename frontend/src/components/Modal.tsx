import { type ReactNode, useEffect, useRef } from "react";

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * A window over the page. The focus goes into it and stays there (Tab wraps around), Escape and a
 * click outside close it, and the focus goes back to where it was.
 */
export function Modal({
  title,
  onClose,
  width = 460,
  children,
}: {
  title: string;
  onClose: () => void;
  width?: number;
  children: ReactNode;
}) {
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    // after a menu closes it gives the focus back to its button: take it again
    const timer = setTimeout(() => {
      const first = box.current?.querySelector<HTMLElement>("input, select, textarea, button");
      if (box.current && !box.current.contains(document.activeElement)) first?.focus();
    }, 0);
    const first = box.current?.querySelector<HTMLElement>("input, select, textarea, button");
    first?.focus();

    // on the document, not on the window: whatever has the focus, Escape and Tab belong to the dialog
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab" || !box.current) return;
      const items = [...box.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
      const head = items[0];
      const tail = items[items.length - 1];
      if (!head || !tail) return;
      const active = document.activeElement;
      if (!box.current.contains(active)) {
        e.preventDefault();
        head.focus();
      } else if (e.shiftKey && active === head) {
        e.preventDefault();
        tail.focus();
      } else if (!e.shiftKey && active === tail) {
        e.preventDefault();
        head.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      clearTimeout(timer);
      document.removeEventListener("keydown", onKey);
      before?.focus?.();
    };
  }, [onClose]);

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: the backdrop is a convenience, Escape does the same
    <div
      className="fixed inset-0 z-30 flex items-start justify-center overflow-y-auto bg-black/40 p-4 pt-[12vh]"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        ref={box}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        style={{ width }}
        className="max-w-full rounded-ui border border-border bg-surface p-4 shadow-lg"
      >
        <h2 className="m-0 mb-3 text-base font-semibold">{title}</h2>
        {children}
      </div>
    </div>
  );
}
