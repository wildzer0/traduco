/** Commands shared by the toolbar, the `/` menu and both editor modes (docs/03-ui.md). */
export type CommandId =
  | "bold"
  | "italic"
  | "heading1"
  | "heading2"
  | "heading3"
  | "bulletList"
  | "orderedList"
  | "table"
  | "image"
  | "code"
  | "footnote"
  | "quote"
  | "link"
  | "rule"
  | "diagram";

/** What the editor shell needs from whichever mode is active. */
export interface EditorHandle {
  run(command: CommandId): void;
  /** Insert an image reference (``img/name.png``) at the cursor. */
  insertImage(src: string, alt: string): void;
  focus(): void;
  /** Index of the top-level block under the cursor (used to keep position when switching mode). */
  blockIndex(): number;
  setBlockIndex(index: number): void;
}

export const DIAGRAM_TEMPLATE = "flowchart LR\n  A[Inizio] --> B[Fine]";
export const TABLE_TEMPLATE = "| Colonna 1 | Colonna 2 |\n| --- | --- |\n|  |  |";
