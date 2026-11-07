import { defaultValueCtx, Editor, rootCtx } from "@milkdown/kit/core";
import { listener, listenerCtx } from "@milkdown/kit/plugin/listener";
import { commonmark } from "@milkdown/kit/preset/commonmark";
import { gfm } from "@milkdown/kit/preset/gfm";
import { getMarkdown } from "@milkdown/kit/utils";

export interface DocumentEditorOptions {
  root: HTMLElement;
  /** Markdown body (front matter already removed). */
  markdown: string;
  /** Called with the serialized body whenever the user edits the document. */
  onChange?: (markdown: string) => void;
}

/** Document (WYSIWYG) mode: Milkdown on the same Markdown the other mode edits (ADR-002). */
export async function createDocumentEditor(opts: DocumentEditorOptions): Promise<Editor> {
  const { root, markdown, onChange } = opts;
  return Editor.make()
    .config((ctx) => {
      ctx.set(rootCtx, root);
      ctx.set(defaultValueCtx, markdown);
      if (onChange) {
        ctx.get(listenerCtx).markdownUpdated((_ctx, md, prev) => {
          if (md !== prev) onChange(md);
        });
      }
    })
    .use(commonmark)
    .use(gfm)
    .use(listener)
    .create();
}

export function serializeBody(editor: Editor): string {
  return editor.action(getMarkdown());
}
