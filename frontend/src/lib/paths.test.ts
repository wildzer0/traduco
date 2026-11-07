import { isInside, parentOf, remapPath } from "./paths";

describe("remapPath", () => {
  const renamed = {
    "capitoli/01-a": "capitoli/02-a",
    "capitoli/01-a/01-x.md": "capitoli/02-a/02-x.md",
  };

  it("follows an exact rename", () => {
    expect(remapPath("capitoli/01-a/01-x.md", renamed)).toBe("capitoli/02-a/02-x.md");
  });

  it("follows a renamed ancestor", () => {
    expect(remapPath("capitoli/01-a/03-y.md", renamed)).toBe("capitoli/02-a/03-y.md");
  });

  it("leaves unrelated paths alone and does not match on name prefixes", () => {
    expect(remapPath("capitoli/01-ab/01-x.md", renamed)).toBe("capitoli/01-ab/01-x.md");
    expect(remapPath("capitoli/09-z", renamed)).toBe("capitoli/09-z");
  });
});

describe("parentOf / isInside", () => {
  it("returns null for top-level chapters", () => {
    expect(parentOf("capitoli/01-a")).toBeNull();
    expect(parentOf("capitoli/01-a/01-x.md")).toBe("capitoli/01-a");
    expect(parentOf("capitoli/01-a/02-b/01-x.md")).toBe("capitoli/01-a/02-b");
  });

  it("isInside is path-segment aware", () => {
    expect(isInside("capitoli/01-a/x.md", "capitoli/01-a")).toBe(true);
    expect(isInside("capitoli/01-ab", "capitoli/01-a")).toBe(false);
    expect(isInside("capitoli/01-a", "capitoli/01-a")).toBe(true);
  });
});
