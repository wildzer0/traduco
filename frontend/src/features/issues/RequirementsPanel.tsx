import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { getRequirements } from "../../lib/api";
import { useT } from "../../lib/i18n";
import { useView } from "../../lib/view-store";

/** Requirement identifiers and their references (RF-84): what to fix, then the full list. */
export function RequirementsPanel({ projectId }: { projectId: string }) {
  const t = useT();
  const close = useView((s) => s.setRequirementsOpen);
  const navigate = useNavigate();
  const { data, refetch, isFetching } = useQuery({
    queryKey: ["requirements", projectId],
    queryFn: () => getRequirements(projectId),
  });
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  const open = (path: string) =>
    navigate({ to: "/p/$projectId", params: { projectId }, search: { s: path } });
  const link = "underline underline-offset-2";
  const name = (path: string) => path.split("/").pop()?.replace(/\.md$/, "") ?? path;

  return (
    <aside
      role="dialog"
      aria-label={t("requirements.title")}
      className="fixed inset-y-0 right-0 z-10 flex w-[460px] max-w-full flex-col overflow-y-auto border-l border-border bg-surface p-4 shadow-lg"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">{t("requirements.title")}</h2>
        <button
          type="button"
          onClick={() => close(false)}
          className="rounded-ui px-2 py-1 hover:bg-surface-2"
        >
          {t("issues.close")}
        </button>
      </div>
      <p className="mt-2 text-[13px] text-muted">{t("requirements.intro")}</p>
      <button
        type="button"
        disabled={isFetching}
        onClick={() => void refetch()}
        className="mt-1 self-start rounded-ui border border-border px-2 py-1 hover:bg-surface-2 disabled:opacity-50"
      >
        {t("requirements.refresh")}
      </button>

      {data && data.requirements.length === 0 && data.problems.length === 0 && (
        <p className="mt-3 text-muted">{t("requirements.none")}</p>
      )}
      {data && data.requirements.length > 0 && (
        <>
          <h3 className="mt-4 text-sm font-semibold">{t("requirements.problems")}</h3>
          {data.problems.length === 0 ? (
            <p className="m-0 text-green" role="status">
              {t("requirements.ok")}
            </p>
          ) : (
            <ul className="m-0 list-none space-y-1 p-0" aria-label={t("requirements.problems")}>
              {data.problems.map((p) => (
                <li key={`${p.kind}:${p.id}:${p.path}:${p.key}`} className="text-[13px]">
                  <code>{p.id}</code> —{" "}
                  {t(`requirements.problem.${p.kind}` as "requirements.problem.duplicate")}{" "}
                  <button type="button" className={link} onClick={() => open(p.path)}>
                    {name(p.path)}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <h3 className="mt-4 text-sm font-semibold">{t("requirements.all")}</h3>
          <ul className="m-0 list-none space-y-2 p-0">
            {data.requirements.map((r) => (
              <li key={r.id} className="text-[13px]">
                <code className="font-semibold">{r.id}</code>{" "}
                <button type="button" className={link} onClick={() => open(r.path)}>
                  {name(r.path)}
                </button>{" "}
                <span className="text-muted">
                  {t("requirements.refs", { count: r.referenced_by.length })}
                </span>
                <br />
                <span className="text-muted">{r.text.slice(0, 120)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </aside>
  );
}
