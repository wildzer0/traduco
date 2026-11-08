import { useState } from "react";
import { Modal } from "../../components/Modal";
import { useT } from "../../lib/i18n";
import type { FolderInfo, TrashEntry } from "../../lib/types";
import { childrenOf } from "./organize";

const primary = "rounded-ui bg-accent px-3 py-1.5 text-accent-fg disabled:opacity-50";
const danger = "rounded-ui bg-red px-3 py-1.5 text-white disabled:opacity-50";
const plain = "rounded-ui px-3 py-1.5 hover:bg-surface-2";

/** Ask for one name (new folder, rename, name of a copy). */
export function NameDialog({
  title,
  label,
  initial = "",
  confirm,
  option,
  onSubmit,
  onClose,
}: {
  title: string;
  label: string;
  initial?: string;
  confirm: string;
  /** An extra yes/no under the name (for example "structure only"). */
  option?: string;
  onSubmit: (name: string, option: boolean) => void;
  onClose: () => void;
}) {
  const t = useT();
  const [name, setName] = useState(initial);
  const [checked, setChecked] = useState(false);
  return (
    <Modal title={title} onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) onSubmit(name.trim(), checked);
        }}
      >
        <label className="block">
          {label}
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            onFocus={(e) => e.currentTarget.select()}
            className="mt-1 w-full rounded-ui border border-border bg-bg px-2 py-1"
          />
        </label>
        {option && (
          <label className="mt-3 flex items-center gap-2 text-[13px]">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
            />
            {option}
          </label>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" onClick={onClose} className={plain}>
            {t("welcome.cancel")}
          </button>
          <button type="submit" disabled={!name.trim()} className={primary}>
            {confirm}
          </button>
        </div>
      </form>
    </Modal>
  );
}

export function ConfirmDialog({
  title,
  message,
  confirm,
  destructive = false,
  onConfirm,
  onClose,
}: {
  title: string;
  message: string;
  confirm: string;
  destructive?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const t = useT();
  return (
    <Modal title={title} onClose={onClose}>
      <p className="m-0 text-[14px]">{message}</p>
      <div className="mt-4 flex justify-end gap-2">
        <button type="button" onClick={onClose} className={plain}>
          {t("welcome.cancel")}
        </button>
        <button type="button" onClick={onConfirm} className={destructive ? danger : primary}>
          {confirm}
        </button>
      </div>
    </Modal>
  );
}

/** Pick a folder (or the top level) from the whole tree. */
export function MoveDialog({
  title,
  folders,
  current,
  blocked = new Set<string>(),
  onPick,
  onClose,
}: {
  title: string;
  folders: FolderInfo[];
  current: string | null;
  /** Folders that cannot be chosen (a folder cannot go inside itself). */
  blocked?: Set<string>;
  onPick: (folder: string | null) => void;
  onClose: () => void;
}) {
  const t = useT();
  const [chosen, setChosen] = useState<string | null>(current);
  const rows: { id: string | null; label: string; depth: number }[] = [
    { id: null, label: t("projects.top"), depth: 0 },
  ];
  const walk = (parent: string | null, depth: number) => {
    for (const f of childrenOf(folders, parent)) {
      if (blocked.has(f.id)) continue;
      rows.push({ id: f.id, label: f.nome, depth });
      walk(f.id, depth + 1);
    }
  };
  walk(null, 1);
  return (
    <Modal title={title} onClose={onClose}>
      <div role="radiogroup" aria-label={title} className="max-h-72 overflow-y-auto">
        {rows.map((row) => (
          <label
            key={row.id ?? "top"}
            style={{ paddingLeft: 8 + row.depth * 16 }}
            className="flex cursor-pointer items-center gap-2 rounded-ui py-1 pr-2 hover:bg-surface-2"
          >
            <input
              type="radio"
              name="folder"
              checked={chosen === row.id}
              onChange={() => setChosen(row.id)}
            />
            {row.label}
          </label>
        ))}
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <button type="button" onClick={onClose} className={plain}>
          {t("welcome.cancel")}
        </button>
        <button type="button" onClick={() => onPick(chosen)} className={primary}>
          {t("projects.moveHere")}
        </button>
      </div>
    </Modal>
  );
}

/** What was deleted, with a way back (or a way to get rid of it for good). */
export function TrashDialog({
  entries,
  locale,
  onRestore,
  onPurge,
  onClose,
}: {
  entries: TrashEntry[];
  locale: string;
  onRestore: (entry: TrashEntry) => void;
  onPurge: (entry: TrashEntry) => void;
  onClose: () => void;
}) {
  const t = useT();
  return (
    <Modal title={t("projects.trashTitle")} onClose={onClose} width={560}>
      {entries.length === 0 ? (
        <p className="m-0 text-muted">{t("projects.trashEmpty")}</p>
      ) : (
        <ul className="m-0 max-h-80 list-none space-y-2 overflow-y-auto p-0">
          {entries.map((e) => (
            <li
              key={e.name}
              className="flex items-center gap-2 rounded-ui border border-border p-2"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate font-medium">{e.nome}</div>
                <div className="text-[12px] text-muted">
                  {t("projects.deletedAt", {
                    when: new Date(e.deleted_at).toLocaleString(locale, {
                      dateStyle: "medium",
                      timeStyle: "short",
                    }),
                  })}
                </div>
              </div>
              <button
                type="button"
                onClick={() => onRestore(e)}
                className={`${plain} border border-border`}
              >
                {t("projects.restore")}
              </button>
              <button type="button" onClick={() => onPurge(e)} className={`${plain} text-red`}>
                {t("projects.purge")}
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-4 flex justify-end">
        <button type="button" onClick={onClose} className={plain}>
          {t("drawer.close")}
        </button>
      </div>
    </Modal>
  );
}
