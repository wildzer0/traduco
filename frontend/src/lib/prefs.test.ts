import { applyPrefs, usePrefs } from "./prefs";

describe("prefs", () => {
  it("sets and clears data-theme", () => {
    usePrefs.getState().setTheme("dark");
    expect(document.documentElement.dataset.theme).toBe("dark");
    usePrefs.getState().setTheme("system");
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });

  it("persists choices in localStorage and sets <html lang>", () => {
    usePrefs.getState().setLocale("en");
    expect(document.documentElement.lang).toBe("en");
    expect(JSON.parse(localStorage.getItem("traduco.prefs") ?? "{}").locale).toBe("en");
  });

  it("applyPrefs does not throw when storage is unavailable", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("denied");
    });
    expect(() => usePrefs.getState().setTheme("light")).not.toThrow();
    applyPrefs({ theme: "light", locale: "it" });
    vi.restoreAllMocks();
  });
});
