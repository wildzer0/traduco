import { resolveStops } from "./snippet-text";

describe("snippet tab-stops", () => {
  it("fills the defaults and finds the first stop", () => {
    const r = resolveStops("**X** Il sistema ${2:fare} ${1:deve}. $0");
    expect(r.text).toBe("**X** Il sistema fare deve. ");
    expect(r.first && r.text.slice(r.first.from, r.first.to)).toBe("deve");
  });

  it("puts the final stop $0 after the numbered ones and leaves plain text alone", () => {
    const r = resolveStops("a $0 b $1");
    expect(r.text).toBe("a  b ");
    expect(r.first).toEqual({ from: 5, to: 5 });
    expect(resolveStops("costa $ 5 e {{campo}}")).toEqual({
      text: "costa $ 5 e {{campo}}",
      first: null,
    });
  });
});
