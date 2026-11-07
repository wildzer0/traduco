import { useEffect, useState } from "react";
import { getLlmStatus, getSettings, putSettings } from "../lib/api";
import { useT } from "../lib/i18n";
import { type Locale, type Theme, usePrefs } from "../lib/prefs";
import { useTranslationState } from "../lib/translation-store";

interface Props {
  onClose: () => void;
}

export function SettingsDrawer({ onClose }: Props) {
  const t = useT();
  const { theme, locale, setTheme, setLocale } = usePrefs();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const field = "mt-1 w-full rounded-ui border border-border bg-surface px-2 py-1";
  const [address, setAddress] = useState("");
  const [model, setModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [hasKey, setHasKey] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getSettings()
      .then((s) => {
        setAddress(s.llm_base_url);
        setModel(s.llm_model);
        setHasKey(s.has_api_key);
      })
      .catch(() => undefined);
  }, []);

  const saveAndVerify = async () => {
    setBusy(true);
    setResult(null);
    try {
      await putSettings({
        llm_base_url: address,
        llm_model: model,
        ...(apiKey ? { llm_api_key: apiKey } : {}),
      });
      setApiKey("");
      const status = await getLlmStatus();
      useTranslationState.getState().setLlm(status.online, status.model);
      const models = status.models.join(", ") || t("settings.verifyNoModels");
      if (!status.online)
        setResult({ ok: false, text: t("settings.verifyFail", { error: status.error ?? "" }) });
      else if (!status.models.includes(status.model))
        setResult({
          ok: false,
          text: t("settings.verifyNoModel", { model: status.model, models }),
        });
      else setResult({ ok: true, text: t("settings.verifyOk", { models }) });
    } catch (e) {
      setResult({ ok: false, text: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(false);
    }
  };
  return (
    <aside
      role="dialog"
      aria-label={t("settings.title")}
      className="fixed inset-y-0 right-0 z-10 w-[420px] max-w-full border-l border-border bg-surface p-4 shadow-lg"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">{t("settings.title")}</h2>
        <button type="button" onClick={onClose} className="rounded-ui px-2 py-1 hover:bg-surface-2">
          {t("settings.close")}
        </button>
      </div>
      <label className="mt-4 block">
        {t("settings.language")}
        <select
          className={field}
          value={locale}
          onChange={(e) => setLocale(e.target.value as Locale)}
        >
          <option value="it">{t("lang.it")}</option>
          <option value="en">{t("lang.en")}</option>
        </select>
      </label>
      <label className="mt-4 block">
        {t("settings.theme")}
        <select className={field} value={theme} onChange={(e) => setTheme(e.target.value as Theme)}>
          <option value="system">{t("settings.theme.system")}</option>
          <option value="light">{t("settings.theme.light")}</option>
          <option value="dark">{t("settings.theme.dark")}</option>
        </select>
      </label>
      <h3 className="mt-6 text-sm font-semibold">{t("settings.model")}</h3>
      <label className="mt-2 block">
        {t("settings.modelAddress")}
        <input
          className={field}
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="http://localhost:11434/v1"
        />
      </label>
      <label className="mt-3 block">
        {t("settings.modelName")}
        <input className={field} value={model} onChange={(e) => setModel(e.target.value)} />
      </label>
      <label className="mt-3 block">
        {t("settings.apiKey")}
        <input
          type="password"
          autoComplete="off"
          className={field}
          value={apiKey}
          placeholder={hasKey ? t("settings.apiKeySaved") : ""}
          onChange={(e) => setApiKey(e.target.value)}
        />
      </label>
      <button
        type="button"
        disabled={busy || !address.trim() || !model.trim()}
        onClick={() => void saveAndVerify()}
        className="mt-3 rounded-ui bg-accent px-3 py-1.5 text-accent-fg disabled:opacity-50"
      >
        {t("settings.saveVerify")}
      </button>
      {result && (
        <p role="status" className={`mt-2 ${result.ok ? "text-green" : "text-red"}`}>
          {result.text}
        </p>
      )}
      <p className="mt-3 text-[12px] text-muted">{t("settings.modelHelp")}</p>
    </aside>
  );
}
