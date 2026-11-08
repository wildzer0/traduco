import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Drawer } from "../../components/Drawer";
import {
  addComment,
  getTranslation,
  listComments,
  replyComment,
  setCommentStatus,
} from "../../lib/api";
import { useT } from "../../lib/i18n";
import { useView } from "../../lib/view-store";

const AUTHOR_KEY = "traduco.author";
const readAuthor = () => {
  try {
    return localStorage.getItem(AUTHOR_KEY) ?? "";
  } catch {
    return "";
  }
};

/** Review comments of the open section (RF-83): threads anchored to segments, with a status. */
export function CommentsPanel({ projectId, path }: { projectId: string; path: string | null }) {
  const t = useT();
  const qc = useQueryClient();
  const close = useView((s) => s.setCommentsOpen);
  const [author, setAuthor] = useState(readAuthor);
  const [key, setKey] = useState("");
  const [text, setText] = useState("");
  const [replies, setReplies] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const queryKey = ["comments", projectId, path];
  const { data } = useQuery({
    queryKey,
    queryFn: () => listComments(projectId, path as string),
    enabled: path !== null,
  });
  const { data: translation } = useQuery({
    queryKey: ["translation", projectId, path],
    queryFn: () => getTranslation(projectId, path as string),
    enabled: path !== null,
  });
  const segments = (translation?.segments ?? []).filter((s) => s.kind !== "title");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [close]);

  const guard = async (job: () => Promise<unknown>) => {
    setError(null);
    try {
      await job();
      try {
        localStorage.setItem(AUTHOR_KEY, author);
      } catch {
        // the name is only a convenience
      }
      await qc.invalidateQueries({ queryKey });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const field = "w-full rounded-ui border border-border bg-bg px-2 py-1";
  const who = author.trim() || "?";
  return (
    <Drawer title={t("comments.title")} onClose={() => close(false)} width={420}>
      {path === null && <p className="text-muted">{t("export.needPath")}</p>}
      {path !== null && (
        <>
          {data?.threads.length === 0 && <p className="mt-3 text-muted">{t("comments.none")}</p>}
          {data?.threads.map((thread) => (
            <article
              key={thread.id}
              className={`mt-3 rounded-ui border border-border p-2 ${thread.status === "resolved" ? "opacity-70" : ""}`}
              data-testid="thread"
            >
              <blockquote className="m-0 border-l-2 border-border pl-2 text-[13px] text-muted">
                {thread.source}
              </blockquote>
              {thread.lost && (
                <p className="m-0 mt-1 text-[12px] text-amber">{t("comments.lost")}</p>
              )}
              {thread.messages.map((m) => (
                <p key={m.at + m.text} className="m-0 mt-1 text-[13px]">
                  <strong>{m.author}</strong>{" "}
                  <span className="text-muted">{m.at.slice(0, 10)}</span>
                  <br />
                  {m.text}
                </p>
              ))}
              {thread.status === "open" && (
                <div className="mt-2 flex gap-1">
                  <input
                    className={field}
                    aria-label={t("comments.reply")}
                    placeholder={t("comments.reply")}
                    value={replies[thread.id] ?? ""}
                    onChange={(e) => setReplies({ ...replies, [thread.id]: e.target.value })}
                  />
                  <button
                    type="button"
                    disabled={!(replies[thread.id] ?? "").trim()}
                    className="rounded-ui border border-border px-2 hover:bg-surface-2 disabled:opacity-50"
                    onClick={() =>
                      guard(async () => {
                        await replyComment(projectId, thread.id, {
                          path,
                          author: who,
                          text: replies[thread.id] ?? "",
                        });
                        setReplies({ ...replies, [thread.id]: "" });
                      })
                    }
                  >
                    {t("comments.send")}
                  </button>
                </div>
              )}
              <button
                type="button"
                className="mt-2 text-[12px] underline underline-offset-2"
                onClick={() =>
                  guard(() =>
                    setCommentStatus(projectId, thread.id, {
                      path,
                      status: thread.status === "open" ? "resolved" : "open",
                    }),
                  )
                }
              >
                {thread.status === "open" ? t("comments.resolve") : t("comments.reopen")}
              </button>
            </article>
          ))}

          <fieldset className="mt-4 border-0 p-0">
            <legend className="text-sm font-semibold">{t("comments.add")}</legend>
            <label className="mt-1 block text-[13px]">
              {t("comments.segment")}
              <select className={field} value={key} onChange={(e) => setKey(e.target.value)}>
                <option value="" />
                {segments.map((s) => (
                  <option key={s.key} value={s.key}>
                    {s.source.slice(0, 60)}
                  </option>
                ))}
              </select>
            </label>
            <label className="mt-1 block text-[13px]">
              {t("comments.author")}
              <input className={field} value={author} onChange={(e) => setAuthor(e.target.value)} />
            </label>
            <label className="mt-1 block text-[13px]">
              {t("comments.text")}
              <textarea
                className={field}
                rows={3}
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
            </label>
            <button
              type="button"
              disabled={!key || !text.trim()}
              className="mt-2 rounded-ui bg-accent px-3 py-1 text-accent-fg disabled:opacity-50"
              onClick={() =>
                guard(async () => {
                  await addComment(projectId, { path, key, author: who, text });
                  setText("");
                  setKey("");
                })
              }
            >
              {t("comments.send")}
            </button>
          </fieldset>
          {error && (
            <p role="alert" className="m-0 mt-2 text-[13px] text-red">
              {error}
            </p>
          )}
        </>
      )}
    </Drawer>
  );
}
