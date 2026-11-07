import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { suggestFromMemory } from "../../lib/api";
import { useT } from "../../lib/i18n";

/** What the translation memory knows about this segment's source: exact and similar entries. */
export function MemoryBox({
  projectId,
  path,
  segKey,
  top,
  onUse,
  onClose,
}: {
  projectId: string;
  path: string;
  segKey: string;
  top: number;
  onUse: (text: string) => void;
  onClose: () => void;
}) {
  const t = useT();
  const { data, isLoading } = useQuery({
    queryKey: ["memory", projectId, path, segKey],
    queryFn: () => suggestFromMemory(projectId, path, segKey),
  });
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div
      role="dialog"
      aria-label={t("segment.memory")}
      className="absolute left-0 right-0 z-10 rounded-ui border border-border bg-surface p-2 text-[13px] shadow-lg"
      style={{ top }}
    >
      <p className="m-0 font-medium">{t("segment.memory")}</p>
      {!isLoading && data?.matches.length === 0 && (
        <p className="m-0 mt-1 text-muted">{t("segment.memoryNone")}</p>
      )}
      <ul className="m-0 mt-1 list-none space-y-2 p-0">
        {data?.matches.map((m) => (
          <li key={`${m.source}|${m.target}`}>
            <span className="text-[12px] text-muted">
              {Math.round(m.score * 100)}% · {m.source}
            </span>
            <p className="m-0 whitespace-pre-wrap">{m.target}</p>
            <button
              type="button"
              className="mt-1 rounded-ui bg-accent px-2 py-1 text-accent-fg"
              onClick={() => onUse(m.target)}
            >
              {t("segment.use")}
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="mt-2 rounded-ui px-2 py-1 hover:bg-surface-2"
        onClick={onClose}
      >
        {t("segment.cancel")}
      </button>
    </div>
  );
}
