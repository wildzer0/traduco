import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { compareIssues, type DiffOp, listIssues, restoreSection } from "../../lib/api";
import { useT } from "../../lib/i18n";

const DRAFT = "bozza";

/** Word-level comparison of two issues, or of an issue and the draft (RF-82). */
export function ComparePanel({
  projectId,
  from,
  to,
  onClose,
}: {
  projectId: string;
  from: string;
  to: string;
  onClose: () => void;
}) {
  const t = useT();
  const qc = useQueryClient();
  const [a, setA] = useState(from);
  const [b, setB] = useState(to);
  const [lang, setLang] = useState<"sorgente" | "ufficiale">("sorgente");
  const [current, setCurrent] = useState(0);
  const [restored, setRestored] = useState<string[]>([]);
  const body = useRef<HTMLDivElement>(null);
  const { data: issues = [] } = useQuery({
    queryKey: ["issues", projectId],
    queryFn: () => listIssues(projectId),
  });
  const { data, error } = useQuery({
    queryKey: ["compare", projectId, a, b, lang],
    queryFn: () => compareIssues(projectId, a, b, lang),
  });

  const [total, setTotal] = useState(0);
  // biome-ignore lint/correctness/useExhaustiveDependencies: scroll when the target or the data change
  useEffect(() => {
    const nodes = body.current?.querySelectorAll<HTMLElement>("[data-change]");
    setTotal(nodes?.length ?? 0);
    for (const [i, node] of Array.from(nodes ?? []).entries()) {
      node.dataset.current = String(i === current);
    }
    nodes?.[current]?.scrollIntoView?.({ block: "center" });
  }, [current, data]);
  // biome-ignore lint/correctness/useExhaustiveDependencies: a new comparison starts at the first change
  useEffect(() => setCurrent(0), [a, b, lang]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const select = "rounded-ui border border-border bg-bg px-2 py-1";
  const options = [
    ...issues.map((i) => (
      <option key={i.rev} value={i.rev}>
        {i.rev}
      </option>
    )),
    <option key={DRAFT} value={DRAFT}>
      {t("compare.draft")}
    </option>,
  ];
  const canRestore = a !== DRAFT && b === DRAFT;
  const move = (step: number) => total > 0 && setCurrent((current + step + total) % total);

  return (
    <div
      role="dialog"
      aria-label={t("compare.title")}
      className="fixed inset-4 z-20 flex flex-col rounded-ui border border-border bg-surface p-4 shadow-lg"
    >
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="m-0 mr-2 text-base font-semibold">{t("compare.title")}</h2>
        <label className="flex items-center gap-1">
          {t("compare.from")}
          <select className={select} value={a} onChange={(e) => setA(e.target.value)}>
            {options.filter((o) => o.key !== DRAFT)}
          </select>
        </label>
        <label className="flex items-center gap-1">
          {t("compare.to")}
          <select className={select} value={b} onChange={(e) => setB(e.target.value)}>
            {options}
          </select>
        </label>
        <select
          aria-label={t("export.language")}
          className={select}
          value={lang}
          onChange={(e) => setLang(e.target.value as "sorgente" | "ufficiale")}
        >
          <option value="sorgente">{t("compare.lang.sorgente")}</option>
          <option value="ufficiale">{t("compare.lang.ufficiale")}</option>
        </select>
        <span className="ml-auto" />
        <button
          type="button"
          className="rounded-ui border border-border px-2 py-1 hover:bg-surface-2"
          onClick={() => move(-1)}
        >
          {t("compare.prev")}
        </button>
        <button
          type="button"
          className="rounded-ui border border-border px-2 py-1 hover:bg-surface-2"
          onClick={() => move(1)}
        >
          {t("compare.next")}
        </button>
        <span className="text-[13px] text-muted" role="status">
          {total > 0 ? t("compare.count", { n: current + 1, total }) : ""}
        </span>
        <button type="button" className="rounded-ui px-2 py-1 hover:bg-surface-2" onClick={onClose}>
          {t("issues.close")}
        </button>
      </div>

      <div ref={body} className="mt-3 min-h-0 flex-1 overflow-y-auto">
        {error && (
          <p role="alert" className="text-red">
            {error instanceof Error ? error.message : String(error)}
          </p>
        )}
        {data && data.sections.length === 0 && <p className="text-muted">{t("compare.none")}</p>}
        {data?.sections.map((s) => (
          <section key={s.path} className="mb-4" aria-label={s.title}>
            <h3 className="m-0 flex items-center gap-2 text-[14px] font-semibold">
              {s.title}
              <span className="text-[12px] font-normal text-muted">
                {t(`compare.${s.status}` as "compare.added")} ·{" "}
                {t("compare.words", { plus: s.words_added, minus: s.words_removed })}
              </span>
              {canRestore && s.status !== "added" && (
                <button
                  type="button"
                  disabled={restored.includes(s.path)}
                  className="rounded-ui border border-border px-2 py-0.5 text-[12px] font-normal hover:bg-surface-2 disabled:opacity-60"
                  onClick={async () => {
                    await restoreSection(projectId, a, s.path);
                    setRestored([...restored, s.path]);
                    void qc.invalidateQueries();
                  }}
                >
                  {restored.includes(s.path) ? t("compare.restored") : t("compare.restore")}
                </button>
              )}
            </h3>
            <p className="m-0 mt-1 whitespace-pre-wrap leading-relaxed">
              {withOffsets(s.ops).map(({ op, at }) => {
                if (op.op === "equal") return <span key={`${s.path}:${at}`}>{op.text}</span>;
                return (
                  <span
                    key={`${s.path}:${at}`}
                    data-change=""
                    className={
                      op.op === "ins"
                        ? "rounded-sm bg-green/20 text-green data-[current=true]:ring-2 data-[current=true]:ring-accent"
                        : "rounded-sm bg-red/20 text-red line-through data-[current=true]:ring-2 data-[current=true]:ring-accent"
                    }
                  >
                    {op.text}
                  </span>
                );
              })}
            </p>
          </section>
        ))}
        {data && data.unchanged > 0 && (
          <p className="text-[13px] text-muted">
            {t("compare.unchanged", { count: data.unchanged })}
          </p>
        )}
      </div>
    </div>
  );
}

/** The position of each piece in the text is a stable key (the list has no other identity). */
function withOffsets(ops: DiffOp[]): { op: DiffOp; at: number }[] {
  let at = 0;
  return ops.map((op) => {
    const item = { op, at };
    at += op.text.length;
    return item;
  });
}
