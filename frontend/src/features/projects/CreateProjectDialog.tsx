import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Modal } from "../../components/Modal";
import { listSkeletons } from "../../lib/api";
import { useT } from "../../lib/i18n";
import { usePrefs } from "../../lib/prefs";
import type { FolderInfo } from "../../lib/types";

const LANGUAGES = ["it", "en", "de", "fr", "es", "pt", "nl", "pl", "ro", "sv", "cs"];

export interface NewProject {
  nome: string;
  lingua_sorgente: string;
  lingua_ufficiale: string;
  scheletro?: string;
  scheletro_testo?: string;
  cartella: string | null;
}

/** The form that makes a project: name, languages, starting structure and the folder it goes in. */
export function CreateProjectDialog({
  folders,
  folder,
  error,
  busy,
  onSubmit,
  onClose,
}: {
  folders: FolderInfo[];
  folder: string | null;
  error: string | null;
  busy: boolean;
  onSubmit: (project: NewProject) => void;
  onClose: () => void;
}) {
  const t = useT();
  const locale = usePrefs((s) => s.locale);
  const [nome, setNome] = useState("");
  const [source, setSource] = useState("it");
  const [official, setOfficial] = useState("en");
  const [where, setWhere] = useState<string | null>(folder);
  // "" = empty project, "@file" = uploaded text, otherwise the id of a bundled skeleton
  const [structure, setStructure] = useState("");
  const [skeletonText, setSkeletonText] = useState("");
  const { data: skeletons = [] } = useQuery({ queryKey: ["skeletons"], queryFn: listSkeletons });
  const names = new Intl.DisplayNames([locale], { type: "language" });
  const field = "mt-1 w-full rounded-ui border border-border bg-bg px-2 py-1";
  const invalid = !nome.trim() || source === official || (structure === "@file" && !skeletonText);

  return (
    <Modal title={t("welcome.create")} onClose={onClose} width={500}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (invalid) return;
          onSubmit({
            nome: nome.trim(),
            lingua_sorgente: source,
            lingua_ufficiale: official,
            cartella: where,
            ...(structure === "@file"
              ? { scheletro_testo: skeletonText }
              : structure
                ? { scheletro: structure }
                : {}),
          });
        }}
      >
        <label className="block">
          {t("welcome.name")}
          <input
            required
            className={field}
            value={nome}
            onChange={(e) => setNome(e.target.value)}
          />
        </label>
        {(
          [
            ["welcome.source", source, setSource],
            ["welcome.official", official, setOfficial],
          ] as const
        ).map(([label, value, set]) => (
          <label key={label} className="mt-3 block">
            {t(label)}
            <select className={field} value={value} onChange={(e) => set(e.target.value)}>
              {LANGUAGES.map((code) => (
                <option key={code} value={code}>
                  {names.of(code) ?? code}
                </option>
              ))}
            </select>
          </label>
        ))}
        <label className="mt-3 block">
          {t("welcome.structure")}
          <select
            className={field}
            value={structure}
            onChange={(e) => setStructure(e.target.value)}
          >
            <option value="">{t("welcome.structureEmpty")}</option>
            {skeletons.map((s) => (
              <option key={s.id} value={s.id}>
                {s.nome}
              </option>
            ))}
            <option value="@file">{t("welcome.structureFile")}</option>
          </select>
        </label>
        {structure === "@file" && (
          <label className="mt-3 block">
            {t("welcome.skeletonFile")}
            <input
              type="file"
              accept=".yaml,.yml,text/yaml,text/plain"
              className={field}
              onChange={async (e) => setSkeletonText((await e.target.files?.[0]?.text()) ?? "")}
            />
          </label>
        )}
        <label className="mt-3 block">
          {t("projects.colFolder")}
          <select
            className={field}
            value={where ?? ""}
            onChange={(e) => setWhere(e.target.value || null)}
          >
            <option value="">{t("projects.top")}</option>
            {folders
              .slice()
              .sort((a, b) => a.percorso.join("/").localeCompare(b.percorso.join("/")))
              .map((f) => (
                <option key={f.id} value={f.id}>
                  {f.percorso.join(" › ")}
                </option>
              ))}
          </select>
        </label>
        {error && (
          <p role="alert" className="mt-2 text-red">
            {error}
          </p>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-ui px-3 py-1.5 hover:bg-surface-2"
          >
            {t("welcome.cancel")}
          </button>
          <button
            type="submit"
            disabled={invalid || busy}
            className="rounded-ui bg-accent px-3 py-1.5 text-accent-fg disabled:opacity-50"
          >
            {t("welcome.submit")}
          </button>
        </div>
      </form>
    </Modal>
  );
}
