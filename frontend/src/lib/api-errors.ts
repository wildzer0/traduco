import { ApiError } from "./api";
import type { MessageKey } from "./i18n";

/** Text for an error shown to the author: some codes have a message written for them. */
export function errorText(e: unknown, t: (key: MessageKey) => string): string {
  if (e instanceof ApiError && e.code === "off_topic") return t("assist.offTopic");
  return e instanceof Error ? e.message : String(e);
}
