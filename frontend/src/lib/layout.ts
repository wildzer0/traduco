import { create } from "zustand";

const KEY = "traduco.layout";

/** Sizes the author chose by dragging; they survive a reload (this browser only). */
interface Stored {
  sidebar: number; // px
  split: number; // share of the editor in the editor + preview area (0..1)
  drawer: number | null; // px; null = each panel's own width
}

export const DEFAULTS: Stored = { sidebar: 264, split: 0.5, drawer: null };
export const LIMITS = {
  sidebar: [180, 520],
  split: [0.25, 0.75],
  drawer: [320, 1100],
} as const;

const clamp = (value: number, [min, max]: readonly [number, number]) =>
  Math.min(max, Math.max(min, value));

function load(): Stored {
  try {
    const data = JSON.parse(localStorage.getItem(KEY) ?? "{}") as Partial<Stored>;
    return {
      sidebar:
        typeof data.sidebar === "number" ? clamp(data.sidebar, LIMITS.sidebar) : DEFAULTS.sidebar,
      split: typeof data.split === "number" ? clamp(data.split, LIMITS.split) : DEFAULTS.split,
      drawer: typeof data.drawer === "number" ? clamp(data.drawer, LIMITS.drawer) : DEFAULTS.drawer,
    };
  } catch {
    return DEFAULTS;
  }
}

interface LayoutState extends Stored {
  setSidebar: (px: number) => void;
  setSplit: (share: number) => void;
  setDrawer: (px: number | null) => void;
  reset: () => void;
}

function save(state: Stored) {
  try {
    localStorage.setItem(
      KEY,
      JSON.stringify({ sidebar: state.sidebar, split: state.split, drawer: state.drawer }),
    );
  } catch {
    // storage unavailable: the sizes last for the session
  }
}

export const useLayout = create<LayoutState>((set, get) => ({
  ...load(),
  setSidebar: (px) => {
    set({ sidebar: clamp(px, LIMITS.sidebar) });
    save(get());
  },
  setSplit: (share) => {
    set({ split: clamp(share, LIMITS.split) });
    save(get());
  },
  setDrawer: (px) => {
    set({ drawer: px === null ? null : clamp(px, LIMITS.drawer) });
    save(get());
  },
  reset: () => {
    set(DEFAULTS);
    save(DEFAULTS);
  },
}));
