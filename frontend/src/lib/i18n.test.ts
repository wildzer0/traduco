import en from "../i18n/en.json";
import itMessages from "../i18n/it.json";
import { translate } from "./i18n";

describe("i18n", () => {
  it("has the same keys in it and en", () => {
    expect(Object.keys(en).sort()).toEqual(Object.keys(itMessages).sort());
  });

  it("has no empty messages and the same placeholders in both languages", () => {
    const vars = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort();
    for (const key of Object.keys(itMessages) as (keyof typeof itMessages)[]) {
      expect(itMessages[key].trim(), key).not.toBe("");
      expect(en[key].trim(), key).not.toBe("");
      expect(vars(en[key]), key).toEqual(vars(itMessages[key]));
    }
  });

  it("interpolates variables and keeps unknown placeholders visible", () => {
    expect(translate("en", "status.backendOk", { version: "1.2" })).toBe("Backend running · v1.2");
    expect(translate("it", "status.backendOk")).toContain("{version}");
  });
});
