import { blockIndexAtLine, blockStartLines, lineOfBlock } from "./blocks";

const doc = [
  "# Titolo", // 0
  "", // 1
  "Paragrafo uno", // 2
  "su due righe", // 3
  "", // 4
  "- a", // 5
  "- b", // 6
  "  - annidato", // 7
  "", // 8
  "| x | y |", // 9
  "| - | - |", // 10
  "| 1 | 2 |", // 11
  "", // 12
  "```js", // 13
  "", // 14
  "const a = 1;", // 15
  "```", // 16
  "", // 17
  "> citazione", // 18
].join("\n");

describe("block map", () => {
  it("finds one start line per top-level block", () => {
    expect(blockStartLines(doc)).toEqual([0, 2, 5, 9, 13, 18]);
  });

  it("maps lines to the block that contains them, including blank lines inside code", () => {
    expect(blockIndexAtLine(doc, 0)).toBe(0);
    expect(blockIndexAtLine(doc, 3)).toBe(1);
    expect(blockIndexAtLine(doc, 7)).toBe(2);
    expect(blockIndexAtLine(doc, 11)).toBe(3);
    expect(blockIndexAtLine(doc, 14)).toBe(4);
    expect(blockIndexAtLine(doc, 18)).toBe(5);
  });

  it("maps blocks back to their first line and clamps out-of-range indexes", () => {
    expect(lineOfBlock(doc, 2)).toBe(5);
    expect(lineOfBlock(doc, 99)).toBe(18);
    expect(lineOfBlock(doc, -1)).toBe(0);
  });

  it("handles an empty document", () => {
    expect(blockStartLines("")).toEqual([]);
    expect(blockIndexAtLine("", 0)).toBe(0);
    expect(lineOfBlock("", 3)).toBe(0);
  });
});
