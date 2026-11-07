import en from "../i18n/en.json";
import it from "../i18n/it.json";
import { type Locale, usePrefs } from "./prefs";

export type MessageKey = keyof typeof it;

const messages: Record<Locale, Record<MessageKey, string>> = { it, en };

export function translate(
  locale: Locale,
  key: MessageKey,
  vars: Record<string, string | number> = {},
): string {
  return messages[locale][key].replace(/\{(\w+)\}/g, (_, name: string) =>
    String(vars[name] ?? `{${name}}`),
  );
}

/** Returns a translate function bound to the current interface language. */
export function useT(): (key: MessageKey, vars?: Record<string, string | number>) => string {
  const locale = usePrefs((s) => s.locale);
  return (key, vars) => translate(locale, key, vars);
}
