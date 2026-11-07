import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/ibm-plex-mono/400.css";
import "./styles/app.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./app/App";
import { applyPrefs, usePrefs } from "./lib/prefs";

const { theme, locale } = usePrefs.getState();
applyPrefs({ theme, locale });

// After an update the page may still name files of the previous build; a lazy chunk (diagram engine,
// editor…) then fails to load. Reload once to get the new page instead of showing a broken feature.
window.addEventListener("vite:preloadError", () => {
  try {
    if (sessionStorage.getItem("traduco.reloaded") === "1") return;
    sessionStorage.setItem("traduco.reloaded", "1");
  } catch {
    // no session storage: reload anyway, once per page load is enough
  }
  location.reload();
});

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element");
createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
