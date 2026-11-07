export interface ProjectSummary {
  id: string;
  nome: string;
  lingua_sorgente: string;
  lingua_ufficiale: string;
}

export interface TreeNode {
  kind: "chapter" | "section";
  path: string;
  name: string;
  title: string;
  children: TreeNode[];
}

export interface NodeResult {
  path: string | null;
  renamed: Record<string, string>;
}

export interface FileContent {
  path: string;
  content: string;
  hash: string;
}

export interface AssetSaved {
  path: string;
  markdown: string;
}

export interface ProjectEvent {
  type: "hello" | "file.changed" | "project.changed" | "glossary.changed";
  path?: string;
  change?: "added" | "modified" | "deleted";
  hash?: string | null;
  project?: string;
}
