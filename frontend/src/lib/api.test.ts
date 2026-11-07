import { ApiError, getHealth } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("api client", () => {
  it("returns parsed JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok", version: "0.1.0" }))),
    );
    await expect(getHealth()).resolves.toEqual({ status: "ok", version: "0.1.0" });
    expect(fetch).toHaveBeenCalledWith("/api/health", undefined);
  });

  it("maps the standard error body to ApiError", async () => {
    const body = { error: { code: "http_404", message: "Not found", details: {} } };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 404 })),
    );
    await expect(getHealth()).rejects.toMatchObject({ status: 404, code: "http_404" });
    await expect(getHealth()).rejects.toBeInstanceOf(ApiError);
  });

  it("falls back to the HTTP status when the error body is not JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("boom", { status: 502 })));
    await expect(getHealth()).rejects.toMatchObject({ status: 502, code: "http_502" });
  });
});
