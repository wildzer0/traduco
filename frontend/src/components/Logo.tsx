/** The mark: a T whose bar is split in two halves (the text and its translation). */
export function LogoMark({ size = 22 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      aria-hidden="true"
      focusable="false"
      className="shrink-0"
    >
      <rect x="3" y="5" width="12" height="6.5" rx="3.25" fill="currentColor" />
      <rect x="17" y="5" width="12" height="6.5" rx="3.25" fill="var(--accent)" />
      <rect x="12.75" y="13.5" width="6.5" height="14.5" rx="3.25" fill="currentColor" />
    </svg>
  );
}

/** Mark and name, the name large enough to be the first thing the eye finds. */
export function Brand({ size = "md" }: { size?: "md" | "lg" }) {
  const lg = size === "lg";
  return (
    <span className="inline-flex items-center gap-2 text-fg">
      <LogoMark size={lg ? 32 : 24} />
      <span
        className={`font-semibold leading-none tracking-[-0.03em] ${lg ? "text-[26px]" : "text-[19px]"}`}
      >
        Traduco
      </span>
    </span>
  );
}
