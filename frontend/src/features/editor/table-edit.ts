import type { CommandId } from "./commands";
import type { Edit } from "./markdown-transforms";

/** Commands that change the table under the cursor (RF-12). */
export const TABLE_COMMANDS = [
  "tableRowAbove",
  "tableRowBelow",
  "tableColLeft",
  "tableColRight",
  "tableDeleteRow",
  "tableDeleteCol",
  "tableAlignLeft",
  "tableAlignCenter",
  "tableAlignRight",
  "tableDelete",
] as const satisfies readonly CommandId[];

export const isTableCommand = (cmd: CommandId): boolean =>
  (TABLE_COMMANDS as readonly string[]).includes(cmd);

const isRow = (line: string) => line.trimStart().startsWith("|");
const isDivider = (cells: string[]) =>
  cells.length > 0 && cells.every((c) => /^:?-{1,}:?$/.test(c.trim()));

/** Split a pipe-table row into cells (an escaped `\|` stays inside its cell). */
export function splitRow(line: string): string[] {
  const body = line
    .trim()
    .replace(/^\|/, "")
    .replace(/(?<!\\)\|$/, "");
  const cells: string[] = [];
  let current = "";
  for (let i = 0; i < body.length; i++) {
    const ch = body[i] as string;
    if (ch === "\\" && body[i + 1] === "|") {
      current += "\\|";
      i++;
    } else if (ch === "|") {
      cells.push(current.trim());
      current = "";
    } else current += ch;
  }
  cells.push(current.trim());
  return cells;
}

const joinRow = (cells: string[]) => `| ${cells.join(" | ")} |`;
const alignOf = (cell: string) => {
  const c = cell.trim();
  return c.startsWith(":") && c.endsWith(":")
    ? "center"
    : c.endsWith(":")
      ? "right"
      : c.startsWith(":")
        ? "left"
        : "";
};
const divider = (align: string) =>
  align === "center" ? ":---:" : align === "right" ? "---:" : align === "left" ? ":---" : "---";

/** Column the caret is in: the number of unescaped pipes before it, minus the leading one. */
function columnAt(line: string, offset: number): number {
  let count = 0;
  const lead = line.length - line.trimStart().length;
  for (let i = lead; i < Math.min(offset, line.length); i++) {
    if (line[i] === "|" && line[i - 1] !== "\\") count++;
  }
  return Math.max(0, count - 1);
}

/**
 * The edit that applies a table command to the pipe table around `caret`, or `null` when the caret
 * is not in a table. The table is rewritten as a whole (cells keep their text, widths are not
 * aligned): the result is always valid Markdown.
 */
export function tableEdit(doc: string, caret: number, cmd: CommandId): Edit | null {
  if (!isTableCommand(cmd)) return null;
  const lines = doc.split("\n");
  let offset = 0;
  let at = -1;
  const starts: number[] = [];
  for (const [i, line] of lines.entries()) {
    starts.push(offset);
    if (caret >= offset && caret <= offset + line.length) at = i;
    offset += line.length + 1;
  }
  if (at < 0 || !isRow(lines[at] as string)) return null;
  let first = at;
  let last = at;
  while (first > 0 && isRow(lines[first - 1] as string)) first--;
  while (last < lines.length - 1 && isRow(lines[last + 1] as string)) last++;
  const rows = lines.slice(first, last + 1).map(splitRow);
  if (rows.length < 2 || !isDivider(rows[1] as string[])) return null; // not a table with a header
  const row = at - first;
  const col = Math.min(
    columnAt(lines[at] as string, caret - (starts[at] as number)),
    (rows[0] as string[]).length - 1,
  );
  const width = (rows[0] as string[]).length;
  const aligns = (rows[1] as string[]).map(alignOf);
  const body = rows.filter((_, i) => i !== 1);
  const bodyRow = row === 0 ? 0 : row - 1; // index among rows without the divider

  const blank = () => Array.from({ length: width }, () => "");
  let cells = body;
  let nextAligns = aligns;
  let newLine = -1; // line of a row that was just added: the caret goes there
  switch (cmd) {
    case "tableRowAbove":
    case "tableRowBelow": {
      // the header always stays first: a row "above" it goes just below it
      const index = cmd === "tableRowAbove" ? Math.max(1, bodyRow) : row === 0 ? 1 : bodyRow + 1;
      cells = [...body.slice(0, index), blank(), ...body.slice(index)];
      newLine = index + 1; // + the divider line
      break;
    }
    case "tableColLeft":
    case "tableColRight": {
      const index = cmd === "tableColLeft" ? col : col + 1;
      cells = body.map((r) => [...r.slice(0, index), "", ...r.slice(index)]);
      nextAligns = [...aligns.slice(0, index), "", ...aligns.slice(index)];
      break;
    }
    case "tableDeleteRow":
      if (row === 0 || body.length <= 2) return null; // keep the header and one row
      cells = body.filter((_, i) => i !== bodyRow);
      break;
    case "tableDeleteCol":
      if (width <= 1) return null;
      cells = body.map((r) => r.filter((_, i) => i !== col));
      nextAligns = aligns.filter((_, i) => i !== col);
      break;
    case "tableAlignLeft":
    case "tableAlignCenter":
    case "tableAlignRight":
      nextAligns = aligns.map((a, i) =>
        i === col
          ? cmd === "tableAlignLeft"
            ? "left"
            : cmd === "tableAlignCenter"
              ? "center"
              : "right"
          : a,
      );
      break;
    case "tableDelete": {
      const from = starts[first] as number;
      const to = (starts[last] as number) + (lines[last] as string).length;
      return { from, to, insert: "", anchor: from, head: from };
    }
    default:
      return null;
  }
  const header = cells[0] as string[];
  const rebuilt = [
    joinRow(header),
    joinRow(nextAligns.map(divider)),
    ...cells.slice(1).map(joinRow),
  ];
  const from = starts[first] as number;
  const to = (starts[last] as number) + (lines[last] as string).length;
  const insert = rebuilt.join("\n");
  const line = Math.min(rebuilt.length - 1, newLine >= 0 ? newLine : row);
  const pos = from + rebuilt.slice(0, line).reduce((n, l) => n + l.length + 1, 0) + 2;
  return { from, to, insert, anchor: pos, head: pos };
}
