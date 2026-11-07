import { useEffect, useState } from "react";
import { useCapabilities } from "../lib/capabilities";
import { useT } from "../lib/i18n";
import { usePrefs } from "../lib/prefs";

const DISMISSED = "traduco.modelNoticeDismissed";

function wasDismissed(): boolean {
  try {
    return sessionStorage.getItem(DISMISSED) === "1";
  } catch {
    return false;
  }
}

/**
 * First-run guidance (RF-74): the model is downloading in the background, the download failed, or
 * there is no Ollama. The editor keeps working in every case.
 */
export function ModelBanner() {
  const t = useT();
  const { data } = useCapabilities();
  const setSettingsOpen = usePrefs((s) => s.setSettingsOpen);
  const [dismissed, setDismissed] = useState(wasDismissed);
  const model = data?.model;

  // a new download starts: show the banner again
  useEffect(() => {
    if (model?.state === "downloading") setDismissed(false);
  }, [model?.state]);

  if (!model || model.state === "none" || model.state === "ready") return null;
  if (dismissed && model.state !== "downloading") return null;

  const percent = model.total ? Math.floor(((model.completed ?? 0) * 100) / model.total) : null;
  const dismiss = () => {
    setDismissed(true);
    try {
      sessionStorage.setItem(DISMISSED, "1");
    } catch {
      // the notice just comes back next time
    }
  };

  return (
    <div
      role="status"
      data-testid="model-banner"
      data-state={model.state}
      className="border-b border-border bg-surface-2 px-4 py-2 text-[13px]"
    >
      {model.state === "downloading" && (
        <>
          <p className="m-0">
            {percent === null
              ? t("model.downloadingUnknown", { model: model.model ?? "" })
              : t("model.downloading", { model: model.model ?? "", pct: percent })}
          </p>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-border">
            <div
              className="h-full bg-accent transition-all"
              style={{ width: `${percent ?? 5}%` }}
              data-testid="model-progress"
            />
          </div>
        </>
      )}
      {model.state === "error" && (
        <p className="m-0 text-amber">
          {t("model.error", { error: model.error ?? "" })} {t("model.errorHint")}
        </p>
      )}
      {model.state === "unavailable" && <p className="m-0">{t("model.unavailable")}</p>}
      {model.state !== "downloading" && (
        <div className="mt-1 flex gap-3">
          <button
            type="button"
            className="underline underline-offset-2"
            onClick={() => setSettingsOpen(true)}
          >
            {t("model.settings")}
          </button>
          <button type="button" className="underline underline-offset-2" onClick={dismiss}>
            {t("model.dismiss")}
          </button>
        </div>
      )}
    </div>
  );
}
