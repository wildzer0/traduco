import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { EditorState } from "@codemirror/state";
import { EditorView, keymap } from "@codemirror/view";
import { tags } from "@lezer/highlight";
import { useEffect, useRef } from "react";
import { blockIndexAtLine, lineOfBlock } from "./blocks";
import type { CommandId, EditorHandle } from "./commands";
import { parseDocument } from "./markdown-io";
import { commandEdits, insertImageRef } from "./markdown-transforms";
import type { SlashState } from "./SlashMenu";

interface Props {
  initial: string;
  onChange: (text: string) => void;
  onReady: (handle: EditorHandle) => void;
  onSlash: (state: SlashState | null) => void;
  label: string;
}

const highlight = HighlightStyle.define([
  { tag: tags.heading, fontWeight: "600", color: "var(--fg)" },
  { tag: tags.strong, fontWeight: "700" },
  { tag: tags.emphasis, fontStyle: "italic" },
  { tag: tags.link, color: "var(--accent)" },
  { tag: tags.url, color: "var(--accent)" },
  { tag: tags.monospace, fontFamily: "var(--font-mono)", color: "var(--muted)" },
  { tag: tags.quote, color: "var(--muted)" },
  { tag: [tags.processingInstruction, tags.contentSeparator], color: "var(--muted)" },
]);

const SLASH = /^\/([\p{L}\d ]*)$/u;

/** Markdown mode: CodeMirror 6 on the whole file, front matter included. */
export function MarkdownMode({ initial, onChange, onReady, onSlash, label }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const callbacks = useRef({ onChange, onReady, onSlash });
  callbacks.current = { onChange, onReady, onSlash };

  // Created once per mount; the shell remounts (key) to load other content.
  // biome-ignore lint/correctness/useExhaustiveDependencies: see above
  useEffect(() => {
    if (!host.current) return;
    const view = new EditorView({
      parent: host.current,
      state: EditorState.create({
        doc: initial,
        extensions: [
          history(),
          keymap.of([
            { key: "Mod-b", run: () => shortcut("bold") },
            { key: "Mod-i", run: () => shortcut("italic") },
            { key: "Mod-k", run: () => shortcut("link") },
            ...defaultKeymap,
            ...historyKeymap,
          ]),
          markdown({ base: markdownLanguage }),
          syntaxHighlighting(highlight),
          EditorView.lineWrapping,
          EditorView.contentAttributes.of({ "aria-label": label, spellcheck: "true" }),
          EditorView.updateListener.of((u) => {
            if (u.docChanged) callbacks.current.onChange(u.state.doc.toString());
            if (u.docChanged || u.selectionSet) reportSlash(u.view);
          }),
        ],
      }),
    });

    function reportSlash(v: EditorView) {
      const sel = v.state.selection.main;
      if (!sel.empty) return callbacks.current.onSlash(null);
      const line = v.state.doc.lineAt(sel.head);
      const match = SLASH.exec(line.text.slice(0, sel.head - line.from));
      if (!match) return callbacks.current.onSlash(null);
      const rect = v.coordsAtPos(sel.head);
      callbacks.current.onSlash({
        x: rect?.left ?? 0,
        y: rect?.bottom ?? 0,
        query: match[1] ?? "",
        consume: () => v.dispatch({ changes: { from: line.from, to: sel.head, insert: "" } }),
      });
    }

    function shortcut(cmd: CommandId): boolean {
      apply(cmd);
      return true;
    }

    function apply(cmd: CommandId) {
      const { from, to } = view.state.selection.main;
      const edits = commandEdits(view.state.doc.toString(), from, to, cmd);
      if (!edits) return;
      const last = edits[edits.length - 1];
      if (!last) return;
      view.dispatch({
        changes: edits.map((e) => ({ from: e.from, to: e.to, insert: e.insert })),
        selection: { anchor: last.anchor, head: last.head },
        scrollIntoView: true,
      });
      view.focus();
    }

    const bodyOffset = () => {
      const text = view.state.doc.toString();
      const { front } = parseDocument(text);
      return { text, frontLines: front ? front.split("\n").length - 1 : 0 };
    };

    callbacks.current.onReady({
      run: apply,
      focus: () => view.focus(),
      insertImage: (src, alt) => {
        const { to } = view.state.selection.main;
        const e = insertImageRef(to, src, alt);
        view.dispatch({
          changes: { from: e.from, to: e.to, insert: e.insert },
          selection: { anchor: e.anchor, head: e.head },
        });
        view.focus();
      },
      blockIndex: () => {
        const { text, frontLines } = bodyOffset();
        const body = parseDocument(text).body;
        const line = view.state.doc.lineAt(view.state.selection.main.head).number - 1 - frontLines;
        return blockIndexAtLine(body, Math.max(0, line));
      },
      setBlockIndex: (index) => {
        const { text, frontLines } = bodyOffset();
        const line = Math.min(
          view.state.doc.lines,
          lineOfBlock(parseDocument(text).body, index) + frontLines + 1,
        );
        const pos = view.state.doc.line(Math.max(1, line)).from;
        view.dispatch({
          selection: { anchor: pos },
          effects: EditorView.scrollIntoView(pos, { y: "center" }),
        });
      },
    });

    return () => view.destroy();
    // The editor is created once per mount; the shell remounts it (key) to load other content.
  }, []);

  return <div ref={host} className="cm-host" />;
}
