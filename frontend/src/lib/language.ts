/**
 * The target language the author is looking at (`null` = the official one). Requests about
 * translations carry it, so every existing call works on the language chosen in the preview.
 */
export const languageContext: { lang: string | null } = { lang: null };

/** `&lang=xx` when an additional language is chosen, otherwise nothing. */
export const langParam = (): string =>
  languageContext.lang ? `&lang=${encodeURIComponent(languageContext.lang)}` : "";
