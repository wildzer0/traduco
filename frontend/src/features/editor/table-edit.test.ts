import { splitRow, tableEdit } from "./table-edit";

const TABLE = "| A | B |\n| --- | --- |\n| 1 | 2 |\n| 3 | 4 |";
const apply = (doc: string, caret: number, cmd: Parameters<typeof tableEdit>[2]) => {
  const e = tableEdit(doc, caret, cmd);
  return e ? doc.slice(0, e.from) + e.insert + doc.slice(e.to) : null;
};
const LINES = TABLE.split("\n");
const inRow = (n: number, col = 0) => {
  const start = LINES.slice(0, n).reduce((sum, l) => sum + l.length + 1, 0);
  return start + (col === 0 ? 3 : 7);
};

describe("table editing in Markdown", () => {
  it("splits cells and keeps an escaped pipe inside its cell", () => {
    expect(splitRow("| a \\| b | c |")).toEqual(["a \\| b", "c"]);
  });

  it("adds a row below and above, keeping the header first", () => {
    expect(apply(TABLE, inRow(2), "tableRowBelow")).toBe(
      "| A | B |\n| --- | --- |\n| 1 | 2 |\n|  |  |\n| 3 | 4 |",
    );
    expect(apply(TABLE, inRow(3), "tableRowAbove")).toBe(
      "| A | B |\n| --- | --- |\n| 1 | 2 |\n|  |  |\n| 3 | 4 |",
    );
    expect(apply(TABLE, inRow(0), "tableRowAbove")?.split("\n")[0]).toBe("| A | B |");
  });

  it("adds and deletes columns", () => {
    expect(apply(TABLE, inRow(2, 1), "tableColRight")).toBe(
      "| A | B |  |\n| --- | --- | --- |\n| 1 | 2 |  |\n| 3 | 4 |  |",
    );
    expect(apply(TABLE, inRow(2, 0), "tableColLeft")?.split("\n")[0]).toBe("|  | A | B |");
    expect(apply(TABLE, inRow(2, 1), "tableDeleteCol")).toBe("| A |\n| --- |\n| 1 |\n| 3 |");
  });

  it("deletes a body row but never the header or the last row", () => {
    expect(apply(TABLE, inRow(2), "tableDeleteRow")).toBe("| A | B |\n| --- | --- |\n| 3 | 4 |");
    expect(apply(TABLE, inRow(0), "tableDeleteRow")).toBeNull();
    expect(apply("| A |\n| --- |\n| 1 |", 14, "tableDeleteRow")).toBeNull();
  });

  it("aligns the column under the cursor", () => {
    expect(apply(TABLE, inRow(2, 1), "tableAlignRight")?.split("\n")[1]).toBe("| --- | ---: |");
    expect(apply(TABLE, inRow(2, 0), "tableAlignCenter")?.split("\n")[1]).toBe("| :---: | --- |");
  });

  it("removes the whole table, and does nothing outside one", () => {
    expect(apply(`Prima\n\n${TABLE}\n\nDopo`, 12, "tableDelete")).toBe("Prima\n\n\n\nDopo");
    expect(apply("Solo testo qui\n\naltro", 3, "tableRowBelow")).toBeNull();
    expect(apply("| a | b |\n| 1 | 2 |", 3, "tableRowBelow")).toBeNull(); // no divider: not a table
  });
});
