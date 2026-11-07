import * as ContextMenu from "@radix-ui/react-context-menu";
import { Check, Lock, LockOpen, Pencil, Sparkles, Wand2 } from "lucide-react";
import { type ReactNode, type RefObject, useEffect, useLayoutEffect, useState } from "react";
import { useAssist } from "../../lib/assist-store";
import { useT } from "../../lib/i18n";
import { useNotices } from "../../lib/notices";
import type { SegmentRow, TranslationView } from "../../lib/types";
import { useView } from "../../lib/view-store";
import { AssistBox } from "./AssistBox";
import { useSegmentActions } from "./segment-actions";

interface Rect {
  top: number;
  height: number;
}
type Panel =
  | { kind: "edit"; key: string }
  | { kind: "instruct"; key: string; alternatives?: boolean }
  | { kind: "source"; key: string; text: string }
  | { kind: "assist"; key: string }
  | null;

const btn =
  "flex size-6 items-center justify-center rounded-ui text-muted hover:bg-surface-2 hover:text-fg";
const box =
  "absolute left-0 right-0 z-10 rounded-ui border border-border bg-surface p-2 text-[13px] shadow-lg";
const primary = "rounded-ui bg-accent px-2 py-1 text-accent-fg disabled:opacity-50";
const plain = "rounded-ui px-2 py-1 hover:bg-surface-2";
const menuItem =
  "cursor-default rounded-ui px-2 py-1 outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-fg";

/** Measure where the elements of some segments are, relative to the preview content. */
function useRects(article: RefObject<HTMLElement | null>, keys: string[], html: string) {
  const [rects, setRects] = useState<Record<string, Rect>>({});
  const wanted = keys.join("|");
  // biome-ignore lint/correctness/useExhaustiveDependencies: html changes whenever the blocks change
  useLayoutEffect(() => {
    const root = article.current;
    if (!root) return;
    const next: Record<string, Rect> = {};
    for (const key of wanted ? wanted.split("|") : []) {
      const el = root.querySelector<HTMLElement>(`[data-seg="${CSS.escape(key)}"]`);
      if (el) next[key] = { top: el.offsetTop, height: el.offsetHeight };
    }
    setRects(next);
  }, [article, wanted, html]);
  return rects;
}

const column = "relative mx-auto max-w-[calc(72ch+48px)] outline-none";

interface Props {
  /** Translation actions only exist on the translated view; the source view offers the companion. */
  enabled: boolean;
  projectId: string;
  path: string;
  view: TranslationView | undefined;
  article: RefObject<HTMLElement | null>;
  html: string;
  children: ReactNode;
}

/**
 * Wraps the translated preview: hover bar, inline editor, instruction box, proposals for locked
 * segments whose source changed, and the context menu (docs/03-ui.md, "Interazioni sui segmenti").
 */
export function SegmentOverlay({ enabled, projectId, path, view, article, html, children }: Props) {
  const t = useT();
  const actions = useSegmentActions(projectId, path);
  const openGlossary = useView((s) => s.openGlossary);
  const [hovered, setHovered] = useState<string | null>(null);
  const [panel, setPanel] = useState<Panel>(null);
  const [diverged, setDiverged] = useState<string | null>(null);
  const [menuKey, setMenuKey] = useState<string | null>(null);
  const [selection, setSelection] = useState("");
  const rows = new Map<string, SegmentRow>((view?.segments ?? []).map((s) => [s.key, s]));
  const pending = (view?.segments ?? []).filter((s) => s.pending_target !== null);
  const wanted = [hovered, panel?.key, diverged, ...pending.map((s) => s.key)].filter(
    (k): k is string => k !== null && k !== undefined,
  );
  const rects = useRects(article, wanted, html);

  // the panel belongs to the section: close it when another one is opened
  // biome-ignore lint/correctness/useExhaustiveDependencies: reset on section change only
  useEffect(() => {
    setPanel(null);
    setDiverged(null);
  }, [path]);
  useEffect(() => {
    if (!diverged) return;
    const timer = setTimeout(() => setDiverged(null), 10_000);
    return () => clearTimeout(timer);
  }, [diverged]);

  const hover = (e: { target: EventTarget }) => {
    const key = (e.target as HTMLElement).closest<HTMLElement>("[data-seg]")?.dataset.seg;
    if (key) setHovered(key);
  };

  const current = hovered ? rows.get(hovered) : undefined;
  const bar = current && rects[current.key] && !panel;

  // "Improve the text" asked from the editor toolbar: resolve the block under the cursor to a segment
  const request = useAssist((s) => s.request);
  const clearRequest = useAssist((s) => s.clearRequest);
  const notify = useNotices((s) => s.show);
  // The request waits until the saved text has reached the preview (typing is flushed first).
  // biome-ignore lint/correctness/useExhaustiveDependencies: re-check whenever the preview changes
  useEffect(() => {
    if (!request) return;
    const root = article.current;
    const block = root?.querySelector<HTMLElement>(`[data-block="${request.blockIndex}"]`);
    const el = block?.dataset.seg ? block : block?.querySelector<HTMLElement>("[data-seg]");
    const key = el?.dataset.seg;
    if (key && rows.has(key)) {
      clearRequest();
      setPanel({ kind: "assist", key });
      return;
    }
    const timer = setTimeout(() => {
      clearRequest();
      notify(t("assist.noText"));
    }, 5000);
    return () => clearTimeout(timer);
  }, [request, html, view]);

  const lockToggle = (row: SegmentRow) => actions.change(row.key, { locked: !row.locked });

  return (
    <ContextMenu.Root>
      <ContextMenu.Trigger asChild>
        {/* biome-ignore lint/a11y/noStaticElementInteractions: hover and right-click are pointer shortcuts; every action is also reachable from the review mode */}
        <div
          className={column}
          tabIndex={-1}
          onMouseOver={hover}
          onFocus={hover}
          onContextMenu={(e) => {
            const key = (e.target as HTMLElement).closest<HTMLElement>("[data-seg]")?.dataset.seg;
            setMenuKey(key ?? null);
            setSelection(window.getSelection()?.toString().trim() ?? "");
          }}
          onKeyDown={(e) => {
            const row = enabled ? current : undefined;
            if (!row || panel || e.ctrlKey || e.metaKey || e.altKey) return;
            if (e.target !== e.currentTarget && (e.target as HTMLElement).tagName !== "BODY")
              return;
            const k = e.key.toLowerCase();
            if (k === "e") setPanel({ kind: "edit", key: row.key });
            else if (k === "i") setPanel({ kind: "instruct", key: row.key });
            else if (k === "l") void lockToggle(row);
            else if (k === "a") void actions.change(row.key, { action: "approve" });
            else return;
            e.preventDefault();
          }}
        >
          {children}

          {bar && current && (
            <div
              role="toolbar"
              aria-label={t("segment.actions")}
              className="absolute right-1 z-10 flex gap-0.5 rounded-ui border border-border bg-surface p-0.5 shadow"
              style={{ top: Math.max(0, rects[current.key]?.top ?? 0) - 26 }}
            >
              <button
                type="button"
                className={btn}
                title={t("assist.open")}
                aria-label={t("assist.open")}
                onClick={() => setPanel({ kind: "assist", key: current.key })}
              >
                <Wand2 size={14} strokeWidth={1.5} aria-hidden />
              </button>
              {enabled && (
                <>
                  <button
                    type="button"
                    className={btn}
                    title={`${t("segment.edit")} (E)`}
                    aria-label={t("segment.edit")}
                    onClick={() => setPanel({ kind: "edit", key: current.key })}
                  >
                    <Pencil size={14} strokeWidth={1.5} aria-hidden />
                  </button>
                  <button
                    type="button"
                    className={btn}
                    title={`${t("segment.instruct")} (I)`}
                    aria-label={t("segment.instruct")}
                    onClick={() => setPanel({ kind: "instruct", key: current.key })}
                  >
                    <Sparkles size={14} strokeWidth={1.5} aria-hidden />
                  </button>
                  <button
                    type="button"
                    className={btn}
                    aria-pressed={current.locked}
                    title={`${t(current.locked ? "segment.unlock" : "segment.lock")} (L)`}
                    aria-label={t(current.locked ? "segment.unlock" : "segment.lock")}
                    onClick={() => void lockToggle(current)}
                  >
                    {current.locked ? (
                      <Lock size={14} strokeWidth={1.5} aria-hidden />
                    ) : (
                      <LockOpen size={14} strokeWidth={1.5} aria-hidden />
                    )}
                  </button>
                  <button
                    type="button"
                    className={btn}
                    title={`${t("segment.approve")} (A)`}
                    aria-label={t("segment.approve")}
                    disabled={!current.target}
                    onClick={() => void actions.change(current.key, { action: "approve" })}
                  >
                    <Check size={14} strokeWidth={1.5} aria-hidden />
                  </button>
                </>
              )}
            </div>
          )}

          {pending.map((row) => {
            const r = rects[row.key];
            if (!r || panel?.key === row.key) return null;
            return (
              <div
                key={`pending-${row.key}`}
                data-testid="proposal"
                className={`${box} border-amber`}
                style={{ top: r.top + r.height + 2 }}
              >
                <p className="m-0 font-medium">{t("segment.proposal")}</p>
                <p className="m-0 mt-1 whitespace-pre-wrap">{row.pending_target}</p>
                <div className="mt-2 flex gap-2">
                  <button
                    type="button"
                    className={primary}
                    onClick={() => void actions.change(row.key, { action: "accept" })}
                  >
                    {t("segment.accept")}
                  </button>
                  <button
                    type="button"
                    className={plain}
                    onClick={() => void actions.change(row.key, { action: "dismiss" })}
                  >
                    {t("segment.ignore")}
                  </button>
                </div>
              </div>
            );
          })}

          {panel?.kind === "edit" && rows.get(panel.key) && rects[panel.key] && (
            <EditBox
              row={rows.get(panel.key) as SegmentRow}
              top={(rects[panel.key] as Rect).top}
              onCancel={() => setPanel(null)}
              onSave={async (text) => {
                const row = rows.get(panel.key) as SegmentRow;
                setPanel(null);
                await actions.change(row.key, { target: text });
                if (text.trim() !== row.target.trim()) setDiverged(row.key);
              }}
            />
          )}

          {panel?.kind === "assist" && rects[panel.key] && (
            <AssistBox
              projectId={projectId}
              path={path}
              segKey={panel.key}
              top={(rects[panel.key] as Rect).top}
              onClose={() => setPanel(null)}
            />
          )}

          {panel?.kind === "instruct" && rows.get(panel.key) && rects[panel.key] && (
            <InstructBox
              top={(rects[panel.key] as Rect).top}
              startWithAlternatives={panel.alternatives === true}
              onCancel={() => setPanel(null)}
              onPropose={(instruction, alternatives) =>
                actions.instruct(panel.key, instruction, alternatives)
              }
              onUse={async (text) => {
                setPanel(null);
                await actions.change(panel.key, { target: text });
              }}
            />
          )}

          {diverged && !panel && rects[diverged] && rows.get(diverged) && (
            <div
              role="status"
              className={box}
              style={{ top: (rects[diverged] as Rect).top + (rects[diverged] as Rect).height + 2 }}
            >
              <p className="m-0">{t("segment.sourceOutOfDate")}</p>
              <div className="mt-2 flex gap-2">
                <button
                  type="button"
                  className={primary}
                  onClick={async () => {
                    const proposal = await actions.backTranslate(diverged);
                    if (proposal) setPanel({ kind: "source", key: diverged, text: proposal.text });
                    setDiverged(null);
                  }}
                >
                  {t("segment.proposeSource")}
                </button>
                <button
                  type="button"
                  className={plain}
                  onClick={async () => {
                    const key = diverged;
                    setDiverged(null);
                    await actions.change(key, { action: "diverge" });
                  }}
                >
                  {t("segment.ignore")}
                </button>
              </div>
            </div>
          )}

          {panel?.kind === "source" && rects[panel.key] && (
            <SourceBox
              text={panel.text}
              top={(rects[panel.key] as Rect).top}
              onCancel={() => setPanel(null)}
              onApply={async (text) => {
                const key = panel.key;
                setPanel(null);
                await actions.applySource(key, text);
              }}
            />
          )}
        </div>
      </ContextMenu.Trigger>

      <ContextMenu.Portal>
        <ContextMenu.Content className="z-20 min-w-48 rounded-ui border border-border bg-surface p-1 shadow-lg">
          {menuKey && rows.has(menuKey) && (
            <>
              <ContextMenu.Item
                className={menuItem}
                onSelect={() => void actions.change(menuKey, { action: "retranslate" })}
              >
                {t("segment.retranslate")}
              </ContextMenu.Item>
              <ContextMenu.Item
                className={menuItem}
                onSelect={() => setPanel({ kind: "instruct", key: menuKey, alternatives: true })}
              >
                {t("segment.alternatives")}
              </ContextMenu.Item>
              <ContextMenu.Item
                className={menuItem}
                onSelect={() =>
                  void navigator.clipboard?.writeText(rows.get(menuKey)?.target ?? "")
                }
              >
                {t("segment.copy")}
              </ContextMenu.Item>
            </>
          )}
          {selection && (
            <ContextMenu.Item
              className={menuItem}
              onSelect={() =>
                openGlossary({
                  destinazione: view ? { [view.lang]: selection } : {},
                })
              }
            >
              {t("segment.addToGlossary", { text: selection })}
            </ContextMenu.Item>
          )}
        </ContextMenu.Content>
      </ContextMenu.Portal>
    </ContextMenu.Root>
  );
}

function EditBox({
  row,
  top,
  onSave,
  onCancel,
}: {
  row: SegmentRow;
  top: number;
  onSave: (text: string) => void;
  onCancel: () => void;
}) {
  const t = useT();
  const [text, setText] = useState(row.target || row.source);
  return (
    <div className={box} style={{ top }}>
      <textarea
        // biome-ignore lint/a11y/noAutofocus: the box opens after an explicit edit action
        autoFocus
        aria-label={t("segment.editLabel")}
        rows={Math.min(8, Math.max(2, text.split("\n").length + 1))}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            onSave(text);
          }
          if (e.key === "Escape") onCancel();
        }}
        className="w-full resize-y rounded-ui border border-border bg-bg p-1"
      />
      <div className="mt-1 flex items-center gap-2">
        <button type="button" className={primary} onClick={() => onSave(text)}>
          {t("segment.saveLock")}
        </button>
        <button type="button" className={plain} onClick={onCancel}>
          {t("segment.cancel")}
        </button>
        <span className="ml-auto text-muted">{t("segment.editHint")}</span>
      </div>
    </div>
  );
}

function SourceBox({
  text: initial,
  top,
  onApply,
  onCancel,
}: {
  text: string;
  top: number;
  onApply: (text: string) => void;
  onCancel: () => void;
}) {
  const t = useT();
  const [text, setText] = useState(initial);
  return (
    <div className={box} style={{ top }}>
      <p className="m-0 font-medium">{t("segment.sourceProposal")}</p>
      <textarea
        aria-label={t("segment.sourceProposal")}
        rows={Math.min(8, Math.max(2, text.split("\n").length + 1))}
        value={text}
        onChange={(e) => setText(e.target.value)}
        className="mt-1 w-full resize-y rounded-ui border border-border bg-bg p-1"
      />
      <div className="mt-1 flex gap-2">
        <button
          type="button"
          className={primary}
          disabled={!text.trim()}
          onClick={() => onApply(text)}
        >
          {t("segment.applySource")}
        </button>
        <button type="button" className={plain} onClick={onCancel}>
          {t("segment.cancel")}
        </button>
      </div>
    </div>
  );
}

const QUICK = ["segment.quick.formal", "segment.quick.concise", "segment.quick.simple"] as const;

function InstructBox({
  top,
  startWithAlternatives,
  onPropose,
  onUse,
  onCancel,
}: {
  top: number;
  startWithAlternatives: boolean;
  onPropose: (
    instruction: string,
    alternatives: boolean,
  ) => Promise<{ proposals: string[] } | null>;
  onUse: (text: string) => void;
  onCancel: () => void;
}) {
  const t = useT();
  const [instruction, setInstruction] = useState("");
  const [proposals, setProposals] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [empty, setEmpty] = useState(false);

  const run = async (text: string, alternatives: boolean) => {
    setBusy(true);
    setEmpty(false);
    const result = await onPropose(text, alternatives);
    setBusy(false);
    setProposals(result?.proposals ?? []);
    setEmpty(result !== null && result.proposals.length === 0);
  };

  // biome-ignore lint/correctness/useExhaustiveDependencies: runs once when opened from "show alternatives"
  useEffect(() => {
    if (startWithAlternatives) void run(t("segment.variantsInstruction"), true);
  }, []);

  return (
    <div className={box} style={{ top }}>
      <label className="block">
        <span className="font-medium">{t("segment.whatToChange")}</span>
        <input
          // biome-ignore lint/a11y/noAutofocus: the box opens after an explicit action
          autoFocus
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && instruction.trim()) void run(instruction.trim(), false);
            if (e.key === "Escape") onCancel();
          }}
          className="mt-1 w-full rounded-ui border border-border bg-bg p-1"
        />
      </label>
      <div className="mt-1 flex flex-wrap gap-1">
        {QUICK.map((key) => (
          <button
            key={key}
            type="button"
            className="rounded-ui border border-border px-2 py-0.5 hover:bg-surface-2"
            disabled={busy}
            onClick={() => void run(t(key), false)}
          >
            {t(key)}
          </button>
        ))}
        <button
          type="button"
          className="rounded-ui border border-border px-2 py-0.5 hover:bg-surface-2"
          disabled={busy}
          onClick={() => void run(instruction.trim() || t("segment.variantsInstruction"), true)}
        >
          {t("segment.alternatives")}
        </button>
        <button type="button" className={`${plain} ml-auto`} onClick={onCancel}>
          {t("segment.cancel")}
        </button>
      </div>
      {busy && <p className="m-0 mt-2 text-muted">{t("segment.thinking")}</p>}
      {empty && <p className="m-0 mt-2 text-muted">{t("segment.noProposals")}</p>}
      <ul className="m-0 mt-2 list-none space-y-2 p-0">
        {proposals.map((p) => (
          <li key={p} className="rounded-ui border border-border p-2">
            <p className="m-0 whitespace-pre-wrap">{p}</p>
            <button type="button" className={`${primary} mt-1`} onClick={() => onUse(p)}>
              {t("segment.use")}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
