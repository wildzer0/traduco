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

  // Give every translatable block the key the backend assigns to its segment (segmenter.py), so
  // the translation status can be shown on it. Hidden paragraphs (tight lists) mark their item.
  md.core.ruler.push("traduco_segments", (state) => {
    const counters: Record<string, number> = {};
    const next = (prefix: string) => {
      counters[prefix] = (counters[prefix] ?? -1) + 1;
      return `${prefix}:${counters[prefix]}`;
    };
    const stack: string[] = [];
    const items: (typeof state.tokens)[number][] = [];
    let table = -1;
    let row = -1;
    let col = -1;
    for (const token of state.tokens) {
      if (token.nesting === 1) stack.push(token.type.replace(/_open$/, ""));
      else if (token.nesting === -1) stack.pop();
      if (token.nesting === 1 && token.type === "list_item_open") items.push(token);
      if (token.nesting === -1 && token.type === "list_item_close") items.pop();
      if (token.type === "table_open") {
        table += 1;
        row = -1;
      } else if (token.type === "tr_open") {
        row += 1;
        col = -1;
      } else if (token.type === "th_open" || token.type === "td_open") {
        col += 1;
        token.attrSet(
          "data-seg",
          token.type === "th_open" ? `th:${table}:${col}` : `td:${table}:${row - 1}:${col}`,
        );
      } else if (token.type === "heading_open") {
        token.attrSet("data-seg", next("h"));
      } else if (token.type === "paragraph_open") {
        const inside = stack
          .slice(0, -1)
          .filter((n) => /^(list_item|blockquote|footnote)$/.test(n));
        const kind = inside.at(-1);
        const key = next(
          kind === "footnote"
            ? "fn"
            : kind === "list_item"
              ? "li"
              : kind === "blockquote"
                ? "q"
                : "p",
        );
        const target = token.hidden ? items.at(-1) : token;
        target?.attrSet("data-seg", key);
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
