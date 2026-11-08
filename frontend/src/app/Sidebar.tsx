import { BookA, FileText, Settings } from "lucide-react";
import { ResizeHandle } from "../components/ResizeHandle";
import { SkeletonPanel } from "../features/tree/SkeletonPanel";
import { Tree } from "../features/tree/Tree";
import { useT } from "../lib/i18n";
import { DEFAULTS, LIMITS, useLayout } from "../lib/layout";
import { usePrefs } from "../lib/prefs";
import { useView } from "../lib/view-store";

interface Props {
  projectId: string;
  selected: string | null;
  onSelect: (path: string | null) => void;
}

const itemClass =
  "flex w-full items-center gap-2 rounded-ui px-2 py-1.5 text-left text-muted hover:bg-surface-2 hover:text-fg";

export function Sidebar({ projectId, selected, onSelect }: Props) {
  const t = useT();
  const setSettingsOpen = usePrefs((s) => s.setSettingsOpen);
  const width = useLayout((s) => s.sidebar);
  const setWidth = useLayout((s) => s.setSidebar);
  const openGlossary = useView((s) => s.openGlossary);
  const setTemplatesOpen = useView((s) => s.setTemplatesOpen);
  return (
    <>
      <nav
        aria-label={t("sidebar.label")}
        style={{ width }}
        className="flex shrink-0 flex-col border-r border-border bg-bg p-3"
      >
        <h2 className="px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-muted">
          {t("sidebar.label")}
        </h2>
        <Tree projectId={projectId} selected={selected} onSelect={onSelect} />
        <SkeletonPanel projectId={projectId} onSelect={onSelect} />
        <div className="mt-2 border-t border-border pt-2">
          <button type="button" onClick={() => openGlossary()} className={itemClass}>
            <BookA size={15} strokeWidth={1.5} aria-hidden />
            {t("sidebar.glossary")}
          </button>
          <button type="button" onClick={() => setTemplatesOpen(true)} className={itemClass}>
            <FileText size={15} strokeWidth={1.5} aria-hidden />
            {t("sidebar.templates")}
          </button>
          <button type="button" onClick={() => setSettingsOpen(true)} className={itemClass}>
            <Settings size={15} strokeWidth={1.5} aria-hidden />
            {t("sidebar.settings")}
          </button>
        </div>
      </nav>
      <ResizeHandle
        label={t("layout.sidebarWidth")}
        value={width}
        min={LIMITS.sidebar[0]}
        max={LIMITS.sidebar[1]}
        step={16}
        onChange={setWidth}
        onReset={() => setWidth(DEFAULTS.sidebar)}
        className="relative -mx-[3px]"
      />
    </>
  );
}
