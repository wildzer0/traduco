import { useRef } from "react";

interface Props {
  /** Accessible name, e.g. "Larghezza della barra laterale". */
  label: string;
  value: number;
  min: number;
  max: number;
  onChange: (next: number) => void;
  /** Double click, or Home: back to the default size. */
  onReset: () => void;
  /** Value units per pixel dragged (1 for pixels; 1 / area width for a share). */
  scale?: number;
  /** The handle is on the left edge of what it resizes: dragging left makes it bigger. */
  invert?: boolean;
  /** Keyboard step, in value units. */
  step: number;
  className?: string;
}

/**
 * A draggable divider. It also works from the keyboard (arrows, Shift for bigger steps, Home to
 * reset) and announces its value, so the layout is not mouse-only.
 */
export function ResizeHandle({
  label,
  value,
  min,
  max,
  onChange,
  onReset,
  scale = 1,
  invert = false,
  step,
  className = "",
}: Props) {
  const start = useRef<{ x: number; value: number } | null>(null);

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.currentTarget.setPointerCapture(e.pointerId);
    start.current = { x: e.clientX, value };
    document.body.style.userSelect = "none";
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!start.current) return;
    const dx = (e.clientX - start.current.x) * (invert ? -1 : 1);
    onChange(start.current.value + dx * scale);
  };
  const stop = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!start.current) return;
    start.current = null;
    document.body.style.userSelect = "";
    e.currentTarget.releasePointerCapture?.(e.pointerId);
  };
  const onKeyDown = (e: React.KeyboardEvent) => {
    const bigger = (e.shiftKey ? 5 : 1) * step;
    if (e.key === "ArrowLeft") onChange(value + (invert ? bigger : -bigger));
    else if (e.key === "ArrowRight") onChange(value + (invert ? -bigger : bigger));
    else if (e.key === "Home") onReset();
    else return;
    e.preventDefault();
  };

  return (
    // biome-ignore lint/a11y/useSemanticElements: an <hr> cannot be dragged or take the focus
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={Math.round(value * (scale < 1 ? 100 : 1))}
      aria-valuemin={Math.round(min * (scale < 1 ? 100 : 1))}
      aria-valuemax={Math.round(max * (scale < 1 ? 100 : 1))}
      tabIndex={0}
      title={label}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={stop}
      onPointerCancel={stop}
      onDoubleClick={onReset}
      onKeyDown={onKeyDown}
      className={`group z-10 w-1.5 shrink-0 cursor-col-resize touch-none bg-transparent outline-none hover:bg-accent/40 focus-visible:bg-accent/60 ${className}`}
    >
      <span className="absolute inset-y-0 -left-1 -right-1" aria-hidden />
    </div>
  );
}
