import { useEffect, useMemo, useState } from "react";
import { type MessageKey, useT } from "../../lib/i18n";
import type { CommandId } from "./commands";

/** Where the `/` menu opens and how to remove the typed `/query` before running a command. */
export interface SlashState {
  x: number;
  y: number;
  query: string;
  consume: () => void;
}

const ITEMS: { id: CommandId; label: MessageKey }[] = [
  { id: "heading1", label: "toolbar.heading1" },
  { id: "heading2", label: "toolbar.heading2" },
  { id: "heading3", label: "toolbar.heading3" },
  { id: "bulletList", label: "toolbar.list" },
  { id: "table", label: "toolbar.table" },
  { id: "image", label: "toolbar.image" },
  { id: "diagram", label: "toolbar.diagram" },
  { id: "footnote", label: "toolbar.footnote" },
  { id: "quote", label: "toolbar.quote" },
  { id: "code", label: "toolbar.code" },
  { id: "rule", label: "toolbar.rule" },
];

interface Props {
  state: SlashState;
  onPick: (command: CommandId) => void;
  onClose: () => void;
}

export function SlashMenu({ state, onPick, onClose }: Props) {
  const t = useT();
  const [index, setIndex] = useState(0);
  const items = useMemo(() => {
    const q = state.query.toLowerCase();
    return ITEMS.map((i) => ({ ...i, text: t(i.label) })).filter((i) =>
      i.text.toLowerCase().includes(q),
    );
  }, [state.query, t]);

  // biome-ignore lint/correctness/useExhaustiveDependencies: the highlighted row restarts at the top for each query
  useEffect(() => setIndex(0), [state.query]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const stop = () => {
        e.preventDefault();
        e.stopPropagation();
      };
      if (e.key === "ArrowDown") {
        stop();
        setIndex((i) => (items.length ? (i + 1) % items.length : 0));
      } else if (e.key === "ArrowUp") {
        stop();
        setIndex((i) => (items.length ? (i - 1 + items.length) % items.length : 0));
      } else if (e.key === "Escape") {
        stop();
        onClose();
      } else if ((e.key === "Enter" || e.key === "Tab") && items[index]) {
        stop();
        state.consume();
        onPick(items[index].id);
      }
    };
    window.addEventListener("keydown", onKey, true); // before the editor sees Enter/arrows
    return () => window.removeEventListener("keydown", onKey, true);
  }, [items, index, onClose, onPick, state]);

  return (
    <div
      role="listbox"
      aria-label={t("slash.label")}
      style={{ position: "fixed", left: state.x, top: state.y + 4 }}
      className="z-20 max-h-64 min-w-44 overflow-y-auto rounded-ui border border-border bg-surface p-1 shadow-lg"
    >
      {items.length === 0 && <div className="px-2 py-1 text-muted">{t("slash.empty")}</div>}
      {items.map((item, i) => (
        <div
          key={item.id}
          role="option"
          aria-selected={i === index}
          tabIndex={-1}
          onMouseDown={(e) => {
            e.preventDefault(); // keep the editor focused
            state.consume();
            onPick(item.id);
          }}
          onKeyDown={() => {}}
          className={`cursor-default rounded-ui px-2 py-1 ${i === index ? "bg-accent text-accent-fg" : ""}`}
        >
          {item.text}
        </div>
      ))}
    </div>
  );
}
