import type { Editor } from "@milkdown/kit/core";
import { editorViewCtx } from "@milkdown/kit/core";
import {
  createCodeBlockCommand,
  insertHrCommand,
  insertImageCommand,
  toggleEmphasisCommand,
  toggleLinkCommand,
  toggleStrongCommand,
  wrapInBlockquoteCommand,
  wrapInBulletListCommand,
  wrapInHeadingCommand,
  wrapInOrderedListCommand,
} from "@milkdown/kit/preset/commonmark";
import { insertTableCommand } from "@milkdown/kit/preset/gfm";
import { TextSelection } from "@milkdown/kit/prose/state";
import { callCommand, insert } from "@milkdown/kit/utils";
import { type CommandId, DIAGRAM_TEMPLATE, type EditorHandle } from "./commands";

/** Commands of Document (WYSIWYG) mode, implemented on Milkdown / ProseMirror. */
export function createDocumentHandle(editor: Editor): EditorHandle {
  const view = () => editor.ctx.get(editorViewCtx);

  /** Next footnote: a reference at the cursor and an empty definition at the end of the document. */
  const footnote = () => {
    const v = view();
    const { schema } = v.state;
    const refType = schema.nodes.footnote_reference;
    const defType = schema.nodes.footnote_definition;
    const para = schema.nodes.paragraph;
    if (!refType || !defType || !para) return;
    let max = 0;
    v.state.doc.descendants((node) => {
      if (node.type === refType || node.type === defType)
        max = Math.max(max, Number(node.attrs.label) || 0);
    });
    const label = String(max + 1);
    let tr = v.state.tr.replaceSelectionWith(refType.create({ label }));
    tr = tr.insert(tr.doc.content.size, defType.create({ label }, para.create()));
    v.dispatch(
      tr.setSelection(TextSelection.near(tr.doc.resolve(tr.doc.content.size - 2))).scrollIntoView(),
    );
    v.focus();
  };

  const exec = (cmd: CommandId) => {
    switch (cmd) {
      case "bold":
        return void editor.action(callCommand(toggleStrongCommand.key));
      case "italic":
        return void editor.action(callCommand(toggleEmphasisCommand.key));
      case "heading1":
      case "heading2":
      case "heading3":
        return void editor.action(callCommand(wrapInHeadingCommand.key, Number(cmd.slice(-1))));
      case "bulletList":
        return void editor.action(callCommand(wrapInBulletListCommand.key));
      case "orderedList":
        return void editor.action(callCommand(wrapInOrderedListCommand.key));
      case "quote":
        return void editor.action(callCommand(wrapInBlockquoteCommand.key));
      case "code":
        return void editor.action(callCommand(createCodeBlockCommand.key));
      case "link":
        return void editor.action(callCommand(toggleLinkCommand.key, { href: "https://" }));
      case "rule":
        return void editor.action(callCommand(insertHrCommand.key));
      case "table":
        return void editor.action(callCommand(insertTableCommand.key, { row: 2, col: 2 }));
      case "diagram":
        return void editor.action(insert(`\`\`\`mermaid\n${DIAGRAM_TEMPLATE}\n\`\`\``));
      case "footnote":
        return footnote();
      case "image":
        return; // needs a file: handled by the shell
    }
  };

  const run = (cmd: CommandId) => {
    exec(cmd);
    if (cmd !== "image") view().focus();
  };

  return {
    run,
    insertImage: (src, alt) =>
      void editor.action(callCommand(insertImageCommand.key, { src, alt })),
    focus: () => view().focus(),
    topBlock: (y) => {
      const v = view();
      const left = v.dom.getBoundingClientRect().left + 12;
      const hit = v.posAtCoords({ left, top: y });
      return hit ? v.state.doc.resolve(hit.pos).index(0) : 0;
    },
    blockIndex: () => view().state.selection.$from.index(0),
    setBlockIndex: (index) => {
      const v = view();
      let pos = 0;
      let target = 0;
      v.state.doc.forEach((node, offset, i) => {
        if (i <= index) {
          target = offset;
          pos = offset + node.nodeSize;
        }
      });
      const inside = Math.min(target + 1, Math.max(0, pos - 1));
      v.dispatch(
        v.state.tr.setSelection(TextSelection.near(v.state.doc.resolve(inside))).scrollIntoView(),
      );
    },
  };
}
