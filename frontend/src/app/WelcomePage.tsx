import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { keys, useProjects } from "../features/tree/queries";
import { ApiError, createProject, listSkeletons } from "../lib/api";
import { useT } from "../lib/i18n";
import { useNotices } from "../lib/notices";
import { usePrefs } from "../lib/prefs";

const LANGUAGES = ["it", "en", "de", "fr", "es", "pt", "nl", "pl", "ro", "sv", "cs"];

export function WelcomePage() {
  const t = useT();
  const locale = usePrefs((s) => s.locale);
  const setSettingsOpen = usePrefs((s) => s.setSettingsOpen);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const notify = useNotices((s) => s.show);
  const { data: projects = [] } = useProjects();
  const [creating, setCreating] = useState(false);
  const [nome, setNome] = useState("");
  const [source, setSource] = useState("it");
  const [official, setOfficial] = useState("en");
  // "" = empty project, "@file" = pasted/uploaded text, otherwise the id of a bundled skeleton
  const [structure, setStructure] = useState("");
  const [skeletonText, setSkeletonText] = useState("");
  const [skeletonError, setSkeletonError] = useState<string | null>(null);
  const { data: skeletons = [] } = useQuery({ queryKey: ["skeletons"], queryFn: listSkeletons });
  const names = new Intl.DisplayNames([locale], { type: "language" });

  const open = (id: string) =>
    navigate({ to: "/p/$projectId", params: { projectId: id }, search: {} });
  const create = useMutation({
    mutationFn: createProject,
    onSuccess: (p) => {
      qc.invalidateQueries({ queryKey: keys.projects });
      open(p.id);
    },
    onError: (e) => {
      if (e instanceof ApiError && e.code === "invalid_skeleton")
        setSkeletonError(t("welcome.skeletonError", { message: e.message }));
      else notify(t("error.generic", { message: e instanceof Error ? e.message : String(e) }));
    },
  });

  const field = "mt-1 w-full rounded-ui border border-border bg-surface px-2 py-1";
  return (
    <main className="mx-auto w-full max-w-xl overflow-y-auto p-8">
      <h1 className="text-xl font-semibold">{t("welcome.title")}</h1>
      <p className="mt-1 text-muted">{t("welcome.subtitle")}</p>

      <h2 className="mt-8 text-[11px] font-semibold uppercase tracking-wide text-muted">
        {t("welcome.projects")}
      </h2>
      {projects.length === 0 ? (
        <p className="mt-2 text-muted">{t("welcome.empty")}</p>
      ) : (
        <ul className="mt-2 list-none p-0">
          {projects.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => open(p.id)}
                className="w-full rounded-ui px-2 py-1 text-left hover:bg-surface-2"
              >
                {p.nome}{" "}
                <span className="text-muted">
                  · {p.lingua_sorgente} → {p.lingua_ufficiale}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-6 flex gap-2">
        <button
          type="button"
          onClick={() => setCreating(true)}
          className="rounded-ui bg-accent px-3 py-1.5 text-accent-fg"
        >
          {t("welcome.create")}
        </button>
        <button
          type="button"
          onClick={() => create.mutate({ esempio: true })}
          className="rounded-ui border border-border px-3 py-1.5 hover:bg-surface-2"
        >
          {t("welcome.example")}
        </button>
        <button
          type="button"
          onClick={() => setSettingsOpen(true)}
          className="ml-auto rounded-ui px-3 py-1.5 text-muted hover:bg-surface-2"
        >
          {t("sidebar.settings")}
        </button>
      </div>

      {creating && (
        <form
          className="mt-6 rounded-ui border border-border bg-surface p-4"
          onSubmit={(e) => {
            e.preventDefault();
            create.mutate({
              nome: nome.trim(),
              lingua_sorgente: source,
              lingua_ufficiale: official,
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
              // biome-ignore lint/a11y/noAutofocus: the form opens after an explicit click on "Create project"
              autoFocus
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
              onChange={(e) => {
                setStructure(e.target.value);
                setSkeletonError(null);
              }}
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
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  setSkeletonText(file ? await file.text() : "");
                  setSkeletonError(null);
                }}
              />
            </label>
          )}
          {skeletonError && (
            <p role="alert" className="mt-2 text-red">
              {skeletonError}
            </p>
          )}
          <div className="mt-4 flex gap-2">
            <button
              type="submit"
              disabled={
                !nome.trim() || source === official || (structure === "@file" && !skeletonText)
              }
              className="rounded-ui bg-accent px-3 py-1.5 text-accent-fg disabled:opacity-50"
            >
              {t("welcome.submit")}
            </button>
            <button
              type="button"
              onClick={() => setCreating(false)}
              className="rounded-ui px-3 py-1.5 hover:bg-surface-2"
            >
              {t("welcome.cancel")}
            </button>
          </div>
        </form>
      )}
    </main>
  );
}
