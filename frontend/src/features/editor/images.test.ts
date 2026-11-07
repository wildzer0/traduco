import { imagePath, watchImages } from "./images";

describe("imagePath", () => {
  it("resolves relative to the section's folder", () => {
    expect(imagePath("capitoli/01-a/01-s.md", "img/x.png")).toBe("capitoli/01-a/img/x.png");
    expect(imagePath("capitoli/01-a/02-sub/01-s.md", "../img/x.png")).toBe(
      "capitoli/01-a/img/x.png",
    );
    expect(imagePath("capitoli/01-a/01-s.md", "./img/x.png")).toBe("capitoli/01-a/img/x.png");
  });

  it("leaves absolute and external references alone", () => {
    for (const src of [
      "https://x.org/a.png",
      "data:image/png;base64,AA",
      "/static/a.png",
      "//cdn/a.png",
      "",
    ]) {
      expect(imagePath("capitoli/01-a/01-s.md", src)).toBeNull();
    }
  });
});

describe("watchImages", () => {
  it("rewrites existing and later-added images, never external ones", async () => {
    const root = document.createElement("div");
    root.innerHTML = '<img src="img/a.png"><img src="https://x.org/b.png">';
    const stop = watchImages(root, "demo", "capitoli/01-a/01-s.md");
    const [a, b] = root.querySelectorAll("img");
    expect(a?.getAttribute("src")).toBe(
      "/api/projects/demo/assets?path=capitoli%2F01-a%2Fimg%2Fa.png",
    );
    expect(b?.getAttribute("src")).toBe("https://x.org/b.png");
    root.insertAdjacentHTML("beforeend", '<img src="img/c.png">');
    await new Promise((r) => setTimeout(r, 0));
    expect(root.querySelectorAll("img")[2]?.getAttribute("src")).toContain("img%2Fc.png");
    stop();
  });
});
