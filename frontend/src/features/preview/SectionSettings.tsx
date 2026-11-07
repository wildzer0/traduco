import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { useQueryClient } from "@tanstack/react-query";
import { SlidersHorizontal } from "lucide-react";
import { useState } from "react";
import { patchSectionMeta, retranslate } from "../../lib/api";
import { useT } from "../../lib/i18n";
import { useNotices } from "../../lib/notices";
import type { Tone, TranslationView } from "../../lib/types";
import { translationPrefix } from "./translation";

const TONES: Tone[] = ["formale", "neutro", "informale"];

/** Tone override and translator note of the open section (RF-25, RF-27). */
export function SectionSettings({
  projectId,
  path,
  view,
}: {
  projectId: string;
  path: string;
  view: TranslationView;
}) {
  const t = useT();
  const qc = useQueryClient();
  const notify = useNotices((s) => s.show);
  const [note, setNote] = useState<string | null>(null);

  const save = async (tono: Tone | null, contesto: string) => {
    try {
      await patchSectionMeta(projectId, path, { tono, contesto });
      // a changed tone applies to what the author has not fixed by hand
      if (tono !== view.tone) await retranslate(projectId, "section", path);
      await qc.invalidateQueries({ queryKey: translationPrefix(projectId, path) });
    } catch (e) {
      notify(e instanceof Error ? e.message : String(e));
    }
  };
  const item =
    "cursor-default rounded-ui px-2 py-1 outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-fg";
  const effective = view.tone ?? view.project_tone;
  return (
    <>
      <Dropdown.Root>
        <Dropdown.Trigger
          title={t("tone.section")}
          className="flex h-7 items-center gap-1 rounded-ui px-2 hover:bg-surface-2 hover:text-fg"
        >
          <SlidersHorizontal size={14} strokeWidth={1.5} aria-hidden />
          {t("tone.label")}: {t(`tone.${effective}` as "tone.formale")}
        </Dropdown.Trigger>
        <Dropdown.Portal>
          <Dropdown.Content
            align="end"
            sideOffset={4}
            className="z-20 min-w-48 rounded-ui border border-border bg-surface p-1 shadow-lg"
          >
            <Dropdown.Item className={item} onSelect={() => void save(null, view.note)}>
              {t("tone.followProject", { tone: t(`tone.${view.project_tone}` as "tone.formale") })}
              {view.tone === null ? " ✓" : ""}
            </Dropdown.Item>
            {TONES.map((tone) => (
              <Dropdown.Item
                key={tone}
                className={item}
                onSelect={() => void save(tone, view.note)}
              >
                {t(`tone.${tone}` as "tone.formale")}
                {view.tone === tone ? " ✓" : ""}
              </Dropdown.Item>
            ))}
            <Dropdown.Separator className="my-1 h-px bg-border" />
            <Dropdown.Item className={item} onSelect={() => setNote(view.note)}>
              {t("tone.note")}
            </Dropdown.Item>
          </Dropdown.Content>
        </Dropdown.Portal>
      </Dropdown.Root>
      {note !== null && (
        <div
          role="dialog"
          aria-label={t("tone.note")}
          className="absolute right-3 top-12 z-20 w-80 rounded-ui border border-border bg-surface p-3 shadow-lg"
        >
          <label className="block">
            {t("tone.noteLabel")}
            <textarea
              // biome-ignore lint/a11y/noAutofocus: the dialog opens after an explicit menu choice
              autoFocus
              rows={4}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="mt-1 w-full rounded-ui border border-border bg-bg p-1"
            />
          </label>
          <div className="mt-2 flex gap-2">
            <button
              type="button"
              className="rounded-ui bg-accent px-3 py-1 text-accent-fg"
              onClick={async () => {
                const text = note;
                setNote(null);
                await save(view.tone, text);
              }}
            >
              {t("tone.save")}
            </button>
            <button
              type="button"
              className="rounded-ui px-3 py-1 hover:bg-surface-2"
              onClick={() => setNote(null)}
            >
              {t("segment.cancel")}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
