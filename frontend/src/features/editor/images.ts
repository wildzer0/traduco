import { assetUrl } from "../../lib/api";

const ABSOLUTE = /^(?:[a-z][a-z0-9+.-]*:|\/\/|\/)/i;

/** Project-relative path of an image referenced from a section (``img/a.png`` -> ``capitoli/01-a/img/a.png``). */
export function imagePath(sectionPath: string, src: string): string | null {
  if (!src || ABSOLUTE.test(src)) return null;
  const parts = sectionPath.split("/").slice(0, -1);
  for (const seg of src.split("/")) {
    if (seg === "..") parts.pop();
    else if (seg !== ".") parts.push(seg);
  }
  return parts.join("/");
}

/** Make relative ``<img>`` elements inside ``root`` load through the assets API; keeps them in sync. */
export function watchImages(root: HTMLElement, projectId: string, sectionPath: string): () => void {
  const fix = () => {
    for (const img of root.querySelectorAll("img")) {
      if (img.dataset.resolved === img.getAttribute("src")) continue;
      const original = img.getAttribute("src") ?? "";
      const path = imagePath(sectionPath, original);
      if (!path) continue;
      const resolved = assetUrl(projectId, path);
      img.dataset.original = original;
      img.dataset.resolved = resolved;
      img.setAttribute("src", resolved);
    }
  };
  fix();
  const observer = new MutationObserver(fix);
  observer.observe(root, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["src"],
  });
  return () => observer.disconnect();
}
