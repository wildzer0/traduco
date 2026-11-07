import MarkdownIt from "markdown-it";
import footnote from "markdown-it-footnote";
import { imagePath } from "../../features/editor/images";
import { assetUrl } from "../api";

export interface RenderOptions {
  projectId: string;
  /** Project-relative path of the section: relative image references resolve against its folder. */
  sectionPath: string;
}

const esc = (s: string) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

/**
 * Preview renderer (docs/02-architettura.md: same rules as the backend's markdown-it-py).
 * Raw HTML in the source is escaped, never emitted: sections can come from untrusted repositories.
 * Top-level blocks get ``data-block`` so the editor can scroll the preview to the matching block.
 */
export function createRenderer(opts: RenderOptions): (body: string) => string {
  const md = new MarkdownIt({ html: false, linkify: false, typographer: false }).use(
    footnote as unknown as (md: InstanceType<typeof MarkdownIt>) => void,
  );

  md.core.ruler.push("traduco_blocks", (state) => {
    let index = -1;
    let lastLine = -1;
    for (const token of state.tokens) {
      if (token.level === 0 && token.map && token.nesting >= 0 && token.type !== "inline") {
        if (token.map[0] !== lastLine) {
          index += 1;
          lastLine = token.map[0];
        }
        token.attrSet("data-block", String(index));
      }
    }
    return true;
  });

  const defaultImage = md.renderer.rules.image;
  md.renderer.rules.image = (tokens, idx, options, env, self) => {
    const token = tokens[idx];
    if (token) {
      const resolved = imagePath(opts.sectionPath, String(token.attrGet("src") ?? ""));
      if (resolved) token.attrSet("src", assetUrl(opts.projectId, resolved));
    }
    return defaultImage
      ? defaultImage(tokens, idx, options, env, self)
      : self.renderToken(tokens, idx, options);
  };

  const defaultFence = md.renderer.rules.fence;
  md.renderer.rules.fence = (tokens, idx, options, env, self) => {
    const token = tokens[idx];
    if (token && token.info.trim() === "mermaid") {
      const block = token.attrGet("data-block");
      const attr = block === null ? "" : ` data-block="${block}"`;
      return `<div class="mermaid-block"${attr} data-code="${esc(token.content)}"><pre>${esc(token.content)}</pre></div>\n`;
    }
    return defaultFence
      ? defaultFence(tokens, idx, options, env, self)
      : self.renderToken(tokens, idx, options);
  };

  const defaultLinkOpen = md.renderer.rules.link_open;
  md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
    const token = tokens[idx];
    if (token && /^https?:/i.test(String(token.attrGet("href") ?? ""))) {
      token.attrSet("target", "_blank");
      token.attrSet("rel", "noopener noreferrer");
    }
    return defaultLinkOpen
      ? defaultLinkOpen(tokens, idx, options, env, self)
      : self.renderToken(tokens, idx, options);
  };

  return (body) => md.render(body);
}
