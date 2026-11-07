import * as Dropdown from "@radix-ui/react-dropdown-menu";
import {
  Bold,
  Code,
  Ellipsis,
  Heading,
  Image,
  Italic,
  List,
  Superscript,
  Table,
} from "lucide-react";
import { type MessageKey, useT } from "../../lib/i18n";
import type { EditorMode } from "../../lib/prefs";
import type { CommandId } from "./commands";

interface Props {
  mode: EditorMode;
  onMode: (mode: EditorMode) => void;
  onCommand: (command: CommandId) => void;
}

const btn =
  "flex size-8 items-center justify-center rounded-ui text-muted hover:bg-surface-2 hover:text-fg";
const menuItem =
  "cursor-default rounded-ui px-2 py-1 outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-fg";
/** Toolbar buttons must not take the focus (and the selection) away from the editor. */
const keepFocus = (e: React.MouseEvent) => e.preventDefault();
const ICON = { size: 16, strokeWidth: 1.5, "aria-hidden": true } as const;

function Menu({
  label,
  icon,
  items,
  onPick,
}: {
  label: string;
  icon: React.ReactNode;
  items: { id: CommandId; text: string }[];
  onPick: (id: CommandId) => void;
}) {
  return (
    <Dropdown.Root>
      <Dropdown.Trigger aria-label={label} title={label} className={btn}>
        {icon}
      </Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content
          sideOffset={4}
          className="z-20 min-w-40 rounded-ui border border-border bg-surface p-1 shadow-lg"
        >
          {items.map((i) => (
            <Dropdown.Item key={i.id} className={menuItem} onSelect={() => onPick(i.id)}>
              {i.text}
            </Dropdown.Item>
          ))}
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
}

export function Toolbar({ mode, onMode, onCommand }: Props) {
  const t = useT();
  const simple: { id: CommandId; label: MessageKey; icon: React.ReactNode }[] = [
    { id: "bold", label: "toolbar.bold", icon: <Bold {...ICON} /> },
    { id: "italic", label: "toolbar.italic", icon: <Italic {...ICON} /> },
    { id: "bulletList", label: "toolbar.list", icon: <List {...ICON} /> },
    { id: "table", label: "toolbar.table", icon: <Table {...ICON} /> },
    { id: "code", label: "toolbar.code", icon: <Code {...ICON} /> },
    { id: "footnote", label: "toolbar.footnote", icon: <Superscript {...ICON} /> },
  ];
  const item = (id: CommandId, label: MessageKey) => ({ id, text: t(label) });

  return (
    <div
      role="toolbar"
      aria-label={t("toolbar.label")}
      className="flex h-10 shrink-0 items-center gap-0.5 border-b border-border px-2"
    >
      <Menu
        label={t("toolbar.heading")}
        icon={<Heading {...ICON} />}
        items={[
          item("heading1", "toolbar.heading1"),
          item("heading2", "toolbar.heading2"),
          item("heading3", "toolbar.heading3"),
        ]}
        onPick={onCommand}
      />
      {simple.slice(0, 3).map((s) => (
        <button
          key={s.id}
          type="button"
          aria-label={t(s.label)}
          title={t(s.label)}
          className={btn}
          onMouseDown={keepFocus}
          onClick={() => onCommand(s.id)}
        >
          {s.icon}
        </button>
      ))}
      {simple.slice(3, 4).map((s) => (
        <button
          key={s.id}
          type="button"
          aria-label={t(s.label)}
          title={t(s.label)}
          className={btn}
          onMouseDown={keepFocus}
          onClick={() => onCommand(s.id)}
        >
          {s.icon}
        </button>
      ))}
      <button
        type="button"
        aria-label={t("toolbar.image")}
        title={t("toolbar.image")}
        className={btn}
        onMouseDown={keepFocus}
        onClick={() => onCommand("image")}
      >
        <Image {...ICON} />
      </button>
      {simple.slice(4).map((s) => (
        <button
          key={s.id}
          type="button"
          aria-label={t(s.label)}
          title={t(s.label)}
          className={btn}
          onMouseDown={keepFocus}
          onClick={() => onCommand(s.id)}
        >
          {s.icon}
        </button>
      ))}
      <Menu
        label={t("toolbar.more")}
        icon={<Ellipsis {...ICON} />}
        items={[
          item("quote", "toolbar.quote"),
          item("orderedList", "toolbar.orderedList"),
          item("diagram", "toolbar.diagram"),
          item("link", "toolbar.link"),
          item("rule", "toolbar.rule"),
        ]}
        onPick={onCommand}
      />
      <fieldset className="m-0 ml-auto flex min-w-0 rounded-ui border border-border p-0.5">
        <legend className="sr-only">{t("mode.label")}</legend>
        {(["document", "markdown"] as const).map((m) => (
          <button
            key={m}
            type="button"
            aria-pressed={mode === m}
            onClick={() => onMode(m)}
            className={`rounded-ui px-2 py-0.5 ${mode === m ? "bg-accent text-accent-fg" : "text-muted hover:text-fg"}`}
          >
            {t(m === "document" ? "mode.document" : "mode.markdown")}
          </button>
        ))}
      </fieldset>
    </div>
  );
}
