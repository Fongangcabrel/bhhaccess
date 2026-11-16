import { ApiClient, ApiError, deviceHeader } from "../api/client";

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

afterEach(() => vi.unstubAllGlobals());

describe("ApiClient", () => {
  it("sends the bearer token and JSON body", async () => {
    const fn = mockFetch(200, { ok: true });
    await new ApiClient(() => "tok", vi.fn()).post("/scan", { a: 1 });
    const [url, init] = fn.mock.calls[0];
    expect(url).toBe("/api/scan");
    expect(init.headers.Authorization).toBe("Bearer tok");
    expect(init.body).toBe('{"a":1}');
  });

  it("sends the device token header (not a bearer) for paired phones, and signs out on 401", async () => {
    const fn = mockFetch(401, { detail: "Appareil non reconnu" });
    const onUnauthorized = vi.fn();
    await expect(new ApiClient(() => "dev-tok", onUnauthorized, "/api", deviceHeader).get("/device/checkpoints"))
      .rejects.toBeInstanceOf(ApiError);
    const [, init] = fn.mock.calls[0];
    expect(init.headers["X-Device-Token"]).toBe("dev-tok");
    expect(init.headers.Authorization).toBeUndefined();
    expect(onUnauthorized).toHaveBeenCalled();
  });

  it("accepts 204 No Content answers (no JSON body)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true, status: 204, json: async () => { throw new SyntaxError("Unexpected end of JSON input"); },
    }));
    await expect(new ApiClient(() => "tok", vi.fn()).post("/presence/unblock", {})).resolves.toBeUndefined();
  });

  it("signs the user out on 401 when a token was sent", async () => {
    mockFetch(401, { detail: "Session invalide" });
    const onUnauthorized = vi.fn();
    await expect(new ApiClient(() => "tok", onUnauthorized).get("/auth/me")).rejects.toThrow("Session invalide");
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });

  it("does not sign out on a failed login (no token yet)", async () => {
    mockFetch(401, { detail: "Identifiants invalides" });
    const onUnauthorized = vi.fn();
    await expect(new ApiClient(() => null, onUnauthorized).post("/auth/login", {})).rejects.toBeInstanceOf(ApiError);
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it("turns a network failure into a readable error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed")));
    await expect(new ApiClient(() => null, vi.fn()).get("/zones")).rejects.toThrow("Serveur injoignable");
  });
});
