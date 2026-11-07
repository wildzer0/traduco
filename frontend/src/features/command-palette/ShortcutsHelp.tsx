import { useEffect } from "react";
import { useT } from "../../lib/i18n";
import { SHORTCUT_LIST } from "../../lib/shortcuts";
import { useView } from "../../lib/view-store";

/** `?` lists every shortcut; the list is the one in lib/shortcuts.ts. */
export function ShortcutsHelp() {
  const t = useT();
  const open = useView((s) => s.helpOpen);
  const close = useView((s) => s.setHelpOpen);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => (e.key === "Escape" || e.key === "?") && close(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, close]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-30 flex items-start justify-center bg-black/30 pt-[12vh]">
      <div
        role="dialog"
        aria-label={t("shortcuts.title")}
        className="w-[520px] max-w-[92vw] rounded-ui border border-border bg-surface p-4 shadow-lg"
      >
        <div className="flex items-center justify-between">
          <h2 className="m-0 text-base font-semibold">{t("shortcuts.title")}</h2>
          <button
            type="button"
            onClick={() => close(false)}
            className="rounded-ui px-2 py-1 hover:bg-surface-2"
          >
            {t("issues.close")}
          </button>
        </div>
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
          {SHORTCUT_LIST.map((item) => (
            <div key={item.label} className="contents">
              <dt>
                <kbd className="rounded-ui border border-border bg-bg px-1.5 py-0.5 text-[12px]">
                  {item.keys}
                </kbd>
              </dt>
              <dd className="m-0">{t(item.label)}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  );
}
