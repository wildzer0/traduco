import { diffWords } from "./diff";

const rebuild = (parts: ReturnType<typeof diffWords>, keep: "del" | "add") =>
  parts
    .filter((p) => p.type === "same" || p.type === keep)
    .map((p) => p.text)
    .join("");

describe("diffWords", () => {
  it("marks only the changed words", () => {
    const parts = diffWords(
      "Il sistema e' composto da una pompa",
      "Il sistema è composto da una pompa",
    );
    expect(parts.filter((p) => p.type !== "same")).toEqual([
      { type: "del", text: "e'" },
      { type: "add", text: "è" },
    ]);
  });

  it("gives back both texts", () => {
    const before = "Premi **Invio** per `salvare` il file adesso.";
    const after = "Premi **Invio** per salvare subito il file.";
    const parts = diffWords(before, after);
    expect(rebuild(parts, "del")).toBe(before);
    expect(rebuild(parts, "add")).toBe(after);
  });

  it("handles identical, empty and fully different texts", () => {
    expect(diffWords("uguale", "uguale")).toEqual([{ type: "same", text: "uguale" }]);
    expect(diffWords("", "nuovo")).toEqual([{ type: "add", text: "nuovo" }]);
    expect(diffWords("vecchio", "")).toEqual([{ type: "del", text: "vecchio" }]);
    expect(diffWords("a b", "c d").every((p) => p.type !== "same" || p.text.trim() === "")).toBe(
      true,
    );
  });

  it("keeps line breaks", () => {
    const parts = diffWords("uno\ndue", "uno\ntre");
    expect(rebuild(parts, "add")).toBe("uno\ntre");
  });
});
