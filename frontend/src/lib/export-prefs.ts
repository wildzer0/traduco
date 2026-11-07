import type { ExportFormat, ExportLanguage, ExportScope } from "./types";

const FORMATS: ExportFormat[] = ["docx", "pdf", "odt", "html", "epub", "md"];

export interface ExportChoice {
  scope: ExportScope;
  language: ExportLanguage;
  template: string;
  format: ExportFormat;
}

const KEY = "traduco.export";
const DEFAULT: ExportChoice = {
  scope: "project",
  language: "ufficiale",
  template: "",
  format: "docx",
};

/** Last choice made in the export panel, so "Export again" is one click (docs/03-ui.md). */
export function loadExportChoice(): ExportChoice {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return DEFAULT;
    const data = JSON.parse(raw) as Partial<ExportChoice>;
    return {
      scope: data.scope === "section" || data.scope === "chapter" ? data.scope : "project",
      language: typeof data.language === "string" && data.language ? data.language : "ufficiale",
      template: typeof data.template === "string" ? data.template : "",
      format: FORMATS.includes(data.format as ExportFormat)
        ? (data.format as ExportFormat)
        : "docx",
    };
  } catch {
    return DEFAULT;
  }
}

export function saveExportChoice(choice: ExportChoice): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(choice));
  } catch {
    // storage unavailable: the choice lasts for the session only
  }
}
