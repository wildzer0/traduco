import { useQuery } from "@tanstack/react-query";
import { getHealth } from "../lib/api";
import { useT } from "../lib/i18n";
import { useNotices } from "../lib/notices";

export function StatusBar() {
  const t = useT();
  const notice = useNotices((s) => s.message);
  const { data, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 15_000,
    retry: false,
  });
  const text = data
    ? t("status.backendOk", { version: data.version })
    : isError
      ? t("status.backendDown")
      : t("status.checking");
  const dot = data ? "bg-green" : isError ? "bg-red" : "bg-amber";
  return (
    <footer className="flex h-6 shrink-0 items-center gap-2 border-t border-border bg-surface px-3 text-[12px] text-muted">
      <span aria-hidden className={`size-2 rounded-full ${dot}`} />
      <span role="status">{text}</span>
      {notice && (
        <span role="alert" className="ml-auto truncate text-red">
          {notice}
        </span>
      )}
    </footer>
  );
}
