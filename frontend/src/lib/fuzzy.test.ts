import { fuzzyScore } from "./fuzzy";

describe("fuzzy match", () => {
  it("needs the letters in order and ignores case and accents", () => {
    expect(fuzzyScore("qualita", "La Qualità del sistema")).not.toBeNull();
    expect(fuzzyScore("xyz", "Esporta")).toBeNull();
    expect(fuzzyScore("ats", "Esporta")).toBeNull();
    expect(fuzzyScore("", "qualunque")).toBe(0);
  });

  it("prefers a prefix and a closer match", () => {
    const exact = fuzzyScore("esp", "Esporta") as number;
    const loose = fuzzyScore("esp", "Gestione del sistema di progetto") as number;
    expect(exact).toBeGreaterThan(loose);
  });
});
