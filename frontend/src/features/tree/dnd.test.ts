import type { TreeNode } from "../../lib/types";
import { computeDrop, flattenTree } from "./dnd";

const sec = (path: string): TreeNode => ({
  kind: "section",
  path,
  name: path,
  title: path,
  children: [],
});
const chap = (path: string, children: TreeNode[] = []): TreeNode => ({
  kind: "chapter",
  path,
  name: path,
  title: path,
  children,
});

const tree = [
  chap("capitoli/01-a", [
    sec("capitoli/01-a/01-x.md"),
    sec("capitoli/01-a/02-y.md"),
    chap("capitoli/01-a/03-sub", [sec("capitoli/01-a/03-sub/01-z.md")]),
  ]),
  chap("capitoli/02-b", [sec("capitoli/02-b/01-w.md")]),
];
const all = new Set(["capitoli/01-a", "capitoli/02-b", "capitoli/01-a/03-sub"]);

describe("flattenTree", () => {
  it("lists every row with depth, parent and sibling index", () => {
    const rows = flattenTree(tree, all);
    expect(
      rows.map((r) => [
        r.node.path.split("/").pop(),
        r.depth,
        r.parent?.split("/").pop() ?? null,
        r.index,
      ]),
    ).toEqual([
      ["01-a", 0, null, 0],
      ["01-x.md", 1, "01-a", 0],
      ["02-y.md", 1, "01-a", 1],
      ["03-sub", 1, "01-a", 2],
      ["01-z.md", 2, "03-sub", 0],
      ["02-b", 0, null, 1],
      ["01-w.md", 1, "02-b", 0],
    ]);
  });

  it("hides the children of collapsed chapters", () => {
    expect(flattenTree(tree, new Set()).map((r) => r.node.path)).toEqual([
      "capitoli/01-a",
      "capitoli/02-b",
    ]);
  });
});

describe("computeDrop", () => {
  const rows = flattenTree(tree, all);

  it("section dropped on a chapter goes inside it, at the top", () => {
    expect(computeDrop(rows, "capitoli/01-a/01-x.md", "capitoli/02-b")).toEqual({
      parent: "capitoli/02-b",
      index: 0,
    });
  });

  it("section dropped on a section takes its place in that parent (down = after, up = before)", () => {
    expect(computeDrop(rows, "capitoli/01-a/01-x.md", "capitoli/01-a/02-y.md")).toEqual({
      parent: "capitoli/01-a",
      index: 1,
    });
    expect(computeDrop(rows, "capitoli/01-a/02-y.md", "capitoli/01-a/01-x.md")).toEqual({
      parent: "capitoli/01-a",
      index: 0,
    });
  });

  it("section dropped on a section of another chapter lands there", () => {
    expect(computeDrop(rows, "capitoli/02-b/01-w.md", "capitoli/01-a/02-y.md")).toEqual({
      parent: "capitoli/01-a",
      index: 1,
    });
  });

  it("chapter over chapter reorders top-level chapters", () => {
    expect(computeDrop(rows, "capitoli/02-b", "capitoli/01-a")).toEqual({ parent: null, index: 0 });
  });

  it("chapter over a section moves it into that section's chapter", () => {
    expect(computeDrop(rows, "capitoli/02-b", "capitoli/01-a/01-x.md")).toEqual({
      parent: "capitoli/01-a",
      index: 0,
    });
  });

  it("refuses to drop a chapter into itself or its descendants, or on itself", () => {
    expect(computeDrop(rows, "capitoli/01-a", "capitoli/01-a/03-sub")).toBeNull();
    expect(computeDrop(rows, "capitoli/01-a", "capitoli/01-a/01-x.md")).toBeNull();
    expect(computeDrop(rows, "capitoli/01-a", "capitoli/01-a")).toBeNull();
  });

  it("ignores unknown rows", () => {
    expect(computeDrop(rows, "capitoli/nope", "capitoli/01-a")).toBeNull();
  });
});
