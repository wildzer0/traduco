import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getFile, putFile, uploadImage } from "../../lib/api";
import { useAssist } from "../../lib/assist-store";
import { editorBridge } from "../../lib/editor-bridge";
import { useEditorStatus } from "../../lib/editor-status";
import { onFileEvent } from "../../lib/file-events";
import { useT } from "../../lib/i18n";
import { canonicalize } from "../../lib/markdown/canonical";
import { useNotices } from "../../lib/notices";
import { type EditorMode, usePrefs } from "../../lib/prefs";
import { usePreview } from "../../lib/preview-store";
import type { FileContent } from "../../lib/types";
import { keys } from "../tree/queries";
import { Autosaver, type SaveStatus } from "./autosaver";
import type { CommandId, EditorHandle } from "./commands";
import { DocumentMode } from "./DocumentMode";
import { MarkdownMode } from "./MarkdownMode";
import { parseDocument } from "./markdown-io";
import { SlashMenu, type SlashState } from "./SlashMenu";
import { Toolbar } from "./Toolbar";

interface PaneProps {
  projectId: string;
  path: string;
}

/** Loads a section and mounts an editing session; remounts it when the file is reloaded from disk. */
export function EditorPane({ projectId, path }: PaneProps) {
  const t = useT();
  const [epoch, setEpoch] = useState(0);
  const file = useQuery({
    queryKey: [...keys.file(projectId, path), epoch],
    queryFn: () => getFile(projectId, path),
    staleTime: Number.POSITIVE_INFINITY,
    gcTime: 0,
    retry: false,
  });
  if (file.isPending) return <p className="p-6 text-muted">{t("editor.loading")}</p>;
  if (file.isError) {
    const message = file.error instanceof Error ? file.error.message : String(file.error);
    return (
      <p role="alert" className="p-6 text-red">
        {t("editor.loadError", { message })}
      </p>
    );
  }
  return (
    <EditorSession
      key={`${path}:${epoch}`}
      projectId={projectId}
      path={path}
      initial={file.data}
      onReload={() => setEpoch((e) => e + 1)}
    />
  );
}

interface SessionProps extends PaneProps {
  initial: FileContent;
  onReload: () => void;
}

function EditorSession({ projectId, path, initial, onReload }: SessionProps) {
  const t = useT();
  const qc = useQueryClient();
  const notify = useNotices((s) => s.show);
  const setSave = useEditorStatus((s) => s.setSave);
  const mode = usePrefs((s) => s.editorMode);
  const setMode = usePrefs((s) => s.setEditorMode);

  const [version, setVersion] = useState(0); // bumped to remount the editor when the mode changes
  const [initialText, setInitialText] = useState(initial.content);
  const [status, setStatus] = useState<SaveStatus>("saved");
  const [slash, setSlash] = useState<SlashState | null>(null);
  const [empty, setEmpty] = useState(() => parseDocument(initial.content).body.trim() === "");
  const text = useRef(initial.content); // latest full file text, as the active editor has it
  const front = useRef("");
  const handle = useRef<EditorHandle | null>(null);
  const pendingBlock = useRef<number | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const saver = useMemo(
    () =>
      new Autosaver(
        { content: initial.content, hash: initial.hash },
        {
          save: (content, hash) => putFile(projectId, path, content, hash),
          onStatus: (s) => {
            setStatus(s);
            setSave(s);
          },
          normalize: canonicalize,
        },
      ),
    [projectId, path, initial, setSave],
  );

  // Leaving the section (or the page) writes pending changes.
  useEffect(
    () => () => {
      void saver.flush();
      setSave(null);
    },
    [saver, setSave],
  );
  // other parts of the app may ask for pending typing to be written (accepting a suggestion)
  useEffect(() => {
    editorBridge.flush = () => saver.flush();
    editorBridge.blockIndex = () => handle.current?.blockIndex() ?? 0;
    return () => {
      editorBridge.flush = async () => {};
      editorBridge.blockIndex = () => 0;
    };
  }, [saver]);
  useEffect(() => {
    const flush = () => void saver.flush();
    window.addEventListener("pagehide", flush);
    return () => window.removeEventListener("pagehide", flush);
  }, [saver]);

  // External changes (another editor, git checkout...).
  useEffect(() => {
    const check = (hash: string) => {
      if (saver.noteExternalChange(hash) === "reload") onReload();
    };
    return onFileEvent((ev) => {
      if (ev.type === "hello") {
        getFile(projectId, path)
          .then((f) => check(f.hash))
          .catch(() => {});
      } else if (ev.type === "file.changed" && ev.path === path && ev.hash) {
        check(ev.hash);
      }
    });
  }, [saver, projectId, path, onReload]);

  const bodyOf = useMemo(() => parseDocument(initialText), [initialText]);
  front.current = bodyOf.front;

  // The preview follows what is typed (a short delay keeps typing fast) and what is on screen.
  const setPreviewText = usePreview((st) => st.setText);
  const clearPreview = usePreview((st) => st.clear);
  const previewTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const scroller = useRef<HTMLDivElement>(null);
  useEffect(() => {
    setPreviewText(path, initial.content);
    return () => {
      clearTimeout(previewTimer.current);
      clearPreview();
    };
  }, [path, initial, setPreviewText, clearPreview]);

  const changed = useCallback(
    (full: string) => {
      text.current = full;
      saver.update(full);
      setEmpty(parseDocument(full).body.trim() === "");
      clearTimeout(previewTimer.current);
      previewTimer.current = setTimeout(() => setPreviewText(path, full), 120);
    },
    [saver, path, setPreviewText],
  );

  useEffect(() => {
    const box = scroller.current;
    if (!box) return;
    let frame = 0;
    const sync = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const block = handle.current?.topBlock(box.getBoundingClientRect().top + 8);
        if (block !== undefined) usePreview.getState().setTopBlock(block);
      });
    };
    box.addEventListener("scroll", sync, { passive: true });
    return () => {
      cancelAnimationFrame(frame);
      box.removeEventListener("scroll", sync);
    };
  }, []);

  const switchMode = useCallback(
    (next: EditorMode) => {
      if (next === mode) return;
      pendingBlock.current = handle.current?.blockIndex() ?? 0;
      const canonical = canonicalize(text.current);
      text.current = canonical;
      saver.update(canonical);
      setInitialText(canonical);
      setSlash(null);
      setMode(next);
      setVersion((v) => v + 1);
    },
    [mode, saver, setMode],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "/" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        switchMode(mode === "document" ? "markdown" : "document");
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [mode, switchMode]);

  const upload = useCallback(
    async (file: Blob, name: string) => {
      try {
        const saved = await uploadImage(projectId, path, file, name);
        handle.current?.insertImage(saved.markdown, "");
      } catch (e) {
        notify(t("image.error", { message: e instanceof Error ? e.message : String(e) }));
      }
    },
    [projectId, path, notify, t],
  );

  const run = useCallback((cmd: CommandId) => {
    if (cmd === "image") fileInput.current?.click();
    else handle.current?.run(cmd);
  }, []);

  const imageFiles = (list: FileList | null | undefined): File[] =>
    [...(list ?? [])].filter((f) => f.type.startsWith("image/"));

  const keepMine = async () => {
    const hash = saver.conflictHash ?? (await getFile(projectId, path)).hash;
    await saver.keepMine(hash);
    qc.invalidateQueries({ queryKey: keys.tree(projectId) });
  };

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: container-level handlers for blur, paste and drop; the focusable elements are inside
    <section
      className="flex min-h-0 flex-1 flex-col"
      onBlur={() => void saver.flush()}
      onPasteCapture={(e) => {
        const files = imageFiles(e.clipboardData.files);
        if (!files.length) return;
        e.preventDefault();
        for (const f of files) void upload(f, f.name);
      }}
      onDragOverCapture={(e) => {
        if ([...e.dataTransfer.items].some((i) => i.type.startsWith("image/"))) e.preventDefault();
      }}
      onDropCapture={(e) => {
        const files = imageFiles(e.dataTransfer.files);
        if (!files.length) return;
        e.preventDefault();
        for (const f of files) void upload(f, f.name);
      }}
    >
      <Toolbar
        mode={mode}
        onMode={switchMode}
        onCommand={run}
        onAssist={() => {
          const block = handle.current?.blockIndex() ?? 0;
          void saver.flush().then(() => useAssist.getState().requestAssist(block));
        }}
        onCheck={() => useAssist.getState().setCheckOpen(true)}
      />
      <input
        ref={fileInput}
        type="file"
        accept="image/png,image/jpeg,image/gif,image/webp,image/svg+xml"
        hidden
        data-testid="image-input"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void upload(f, f.name);
          e.target.value = "";
        }}
      />
      {status === "conflict" && (
        <div
          role="alert"
          className="flex items-center gap-3 border-b border-border bg-surface-2 px-3 py-2"
        >
          <span className="text-amber">{t("conflict.message")}</span>
          <button
            type="button"
            onClick={onReload}
            className="rounded-ui border border-border px-2 py-0.5 hover:bg-surface"
          >
            {t("conflict.reload")}
          </button>
          <button
            type="button"
            onClick={() => void keepMine()}
            className="rounded-ui border border-border px-2 py-0.5 hover:bg-surface"
          >
            {t("conflict.keep")}
          </button>
        </div>
      )}
      <div ref={scroller} className="editor-scroll relative min-h-0 flex-1 overflow-y-auto">
        {empty && (
          <p className="editor-hint pointer-events-none absolute text-muted">
            {t("editor.placeholder")}
          </p>
        )}
        {mode === "markdown" ? (
          <MarkdownMode
            key={`md-${version}`}
            initial={initialText}
            label={t("editor.body")}
            onChange={changed}
            onSlash={setSlash}
            onReady={(h) => {
              handle.current = h;
              if (pendingBlock.current !== null) h.setBlockIndex(pendingBlock.current);
              pendingBlock.current = null;
            }}
          />
        ) : (
          <DocumentMode
            key={`doc-${version}`}
            markdown={bodyOf.body}
            projectId={projectId}
            sectionPath={path}
            label={t("editor.body")}
            onChange={(body) => changed(front.current ? `${front.current}\n${body}` : body)}
            onEdit={() => saver.touch()}
            onSlash={setSlash}
            onReady={(h) => {
              handle.current = h;
              if (pendingBlock.current !== null) h.setBlockIndex(pendingBlock.current);
              pendingBlock.current = null;
            }}
          />
        )}
      </div>
      {slash && (
        <SlashMenu
          state={slash}
          onClose={() => setSlash(null)}
          onPick={(cmd) => {
            setSlash(null);
            run(cmd);
          }}
        />
      )}
    </section>
  );
}
