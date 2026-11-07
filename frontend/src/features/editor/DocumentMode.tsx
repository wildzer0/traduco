import type { Editor } from "@milkdown/kit/core";
import { editorViewCtx } from "@milkdown/kit/core";
import { useEffect, useRef } from "react";
import type { EditorHandle } from "./commands";
import { createDocumentEditor } from "./document-editor";
import { createDocumentHandle } from "./document-handle";
import { watchImages } from "./images";
import type { SlashState } from "./SlashMenu";

interface Props {
  /** Markdown body (front matter is kept by the shell). */
  markdown: string;
  projectId: string;
  sectionPath: string;
  onChange: (body: string) => void;
  onReady: (handle: EditorHandle) => void;
  onSlash: (state: SlashState | null) => void;
  label: string;
}

const SLASH = /^\/([\p{L}\d ]*)$/u;

/** Document mode: Milkdown (ProseMirror) editing the same Markdown as Markdown mode. */
export function DocumentMode({
  markdown,
  projectId,
  sectionPath,
  onChange,
  onReady,
  onSlash,
  label,
}: Props) {
  const host = useRef<HTMLDivElement>(null);
  const callbacks = useRef({ onChange, onReady, onSlash });
  callbacks.current = { onChange, onReady, onSlash };

  // Created once per mount; the shell remounts (key) to load other content.
  // biome-ignore lint/correctness/useExhaustiveDependencies: see above
  useEffect(() => {
    const root = host.current;
    if (!root) return;
    let cancelled = false;
    let editor: Editor | null = null;
    let stopImages = () => {};
    let detach = () => {};

    createDocumentEditor({
      root,
      markdown,
      label,
      onChange: (md) => callbacks.current.onChange(md),
    }).then((created) => {
      if (cancelled) return void created.destroy();
      editor = created;
      stopImages = watchImages(root, projectId, sectionPath);
      const view = created.ctx.get(editorViewCtx);

      const detect = () => {
        const { selection } = view.state;
        const para = selection.$from.parent;
        if (!selection.empty || para.type.name !== "paragraph")
          return callbacks.current.onSlash(null);
        const before = para.textBetween(0, selection.$from.parentOffset, undefined, "￼");
        const match = SLASH.exec(before);
        if (!match) return callbacks.current.onSlash(null);
        const rect = view.coordsAtPos(selection.from);
        callbacks.current.onSlash({
          x: rect.left,
          y: rect.bottom,
          query: match[1] ?? "",
          consume: () =>
            view.dispatch(view.state.tr.delete(selection.from - before.length, selection.from)),
        });
      };
      view.dom.addEventListener("keyup", detect);
      view.dom.addEventListener("mouseup", detect);
      detach = () => {
        view.dom.removeEventListener("keyup", detect);
        view.dom.removeEventListener("mouseup", detect);
      };
      callbacks.current.onReady(createDocumentHandle(created));
    });

    return () => {
      cancelled = true;
      stopImages();
      detach();
      if (editor) void editor.destroy();
    };
    // Created once per mount; the shell remounts (key) to load other content.
  }, []);

  return <div ref={host} className="doc-host" />;
}
