import { afterEach, describe, expect, it, vi } from "vitest";
import { configureAccessTokenRecovery, request } from "./api";

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  configureAccessTokenRecovery(null);
  vi.unstubAllGlobals();
});

describe("authenticated API requests", () => {
  it("refreshes an expired access token and retries once", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse({ detail: "expired" }, 401))
      .mockResolvedValueOnce(jsonResponse({ ok: true }));
    const recover = vi.fn().mockResolvedValue("fresh-access-token");
    vi.stubGlobal("fetch", fetchMock);
    configureAccessTokenRecovery(recover);

    await expect(request<{ ok: boolean }>("/protected", "old-access-token")).resolves.toEqual({ ok: true });

    expect(recover).toHaveBeenCalledOnce();
    expect(recover).toHaveBeenCalledWith("old-access-token");
    const retryHeaders = new Headers(fetchMock.mock.calls[1][1]?.headers);
    expect(retryHeaders.get("Authorization")).toBe("Bearer fresh-access-token");
  });

  it("shares one refresh operation between concurrent 401 responses", async () => {
    let finishRecovery: ((token: string) => void) | undefined;
    const recover = vi.fn(() => new Promise<string>(resolve => { finishRecovery = resolve }));
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
      const authorization = new Headers(init?.headers).get("Authorization");
      return authorization === "Bearer old-token"
        ? jsonResponse({ detail: "expired" }, 401)
        : jsonResponse({ ok: true });
    });
    vi.stubGlobal("fetch", fetchMock);
    configureAccessTokenRecovery(recover);

    const first = request<{ ok: boolean }>("/first", "old-token");
    const second = request<{ ok: boolean }>("/second", "old-token");
    await vi.waitFor(() => expect(recover).toHaveBeenCalledOnce());
    finishRecovery?.("renewed-token");

    await expect(Promise.all([first, second])).resolves.toEqual([{ ok: true }, { ok: true }]);
    expect(recover).toHaveBeenCalledOnce();
  });

  it("returns a friendly session error when refresh is no longer possible", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({ detail: "expired" }, 401)));
    configureAccessTokenRecovery(vi.fn().mockResolvedValue(null));

    const failure = request("/protected", "old-token");
    await expect(failure).rejects.toMatchObject({
      status: 401,
      code: "SESSION_EXPIRED",
      message: "Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.",
    });
  });
});
