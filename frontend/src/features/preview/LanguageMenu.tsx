import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { useQuery } from "@tanstack/react-query";
import { Check, Globe } from "lucide-react";
import { listLanguages } from "../../lib/api";
import { useT } from "../../lib/i18n";
import { usePrefs } from "../../lib/prefs";
import { usePreview } from "../../lib/preview-store";
import { useView } from "../../lib/view-store";

/** Which target language the preview shows, with how far each one is translated (RF-21b…d). */
export function LanguageMenu({ projectId }: { projectId: string }) {
  const t = useT();
  const locale = usePrefs((s) => s.locale);
  const current = usePreview((s) => s.language);
  const setLanguage = usePreview((s) => s.setLanguage);
  const openLanguages = useView((s) => s.setLanguagesOpen);
  const { data = [] } = useQuery({
    queryKey: ["languages", projectId],
    queryFn: () => listLanguages(projectId),
    refetchInterval: 15_000,
  });
  const names = new Intl.DisplayNames([locale], { type: "language" });
  const name = (code: string) => {
    try {
      return names.of(code) ?? code;
    } catch {
      return code;
    }
  };
  const targets = data.filter((l) => l.role !== "source");
  const official = targets.find((l) => l.role === "official")?.code ?? null;
  const shown = current ?? official;
  const item =
    "flex cursor-default items-center justify-between gap-3 rounded-ui px-2 py-1 outline-none data-[highlighted]:bg-accent data-[highlighted]:text-accent-fg";
  return (
    <Dropdown.Root>
      <Dropdown.Trigger
        title={t("languages.title")}
        className="flex h-7 items-center gap-1 rounded-ui px-2 hover:bg-surface-2 hover:text-fg"
      >
        <Globe size={14} strokeWidth={1.5} aria-hidden />
        {shown ? name(shown) : t("languages.title")}
      </Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content
          align="end"
          sideOffset={4}
          className="z-20 min-w-52 rounded-ui border border-border bg-surface p-1 shadow-lg"
        >
          {targets.map((l) => (
            <Dropdown.Item
              key={l.code}
              className={item}
              onSelect={() => setLanguage(l.role === "official" ? null : l.code)}
            >
              <span className="flex items-center gap-1">
                {l.code === shown ? <Check size={12} aria-hidden /> : <span className="w-3" />}
                {name(l.code)}
              </span>
              <span className="text-[12px] opacity-70">{l.percent}%</span>
            </Dropdown.Item>
          ))}
          <Dropdown.Separator className="my-1 h-px bg-border" />
          <Dropdown.Item className={item} onSelect={() => openLanguages(true)}>
            {t("languages.manage")}
          </Dropdown.Item>
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
}
