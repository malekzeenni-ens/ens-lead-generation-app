import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn() }));

/** The phone gateway serves a production build with no Vite API env (ADR-025). */
function asPhone(): void {
  vi.stubEnv("PROD", true);
  vi.stubEnv("VITE_ENS_API_URL", "");
}

beforeEach(() => {
  vi.resetModules();
  delete window.__TAURI_INTERNALS__;
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("connection mode", () => {
  it("is the desktop inside Tauri, in development and in tests", async () => {
    const { connectionMode } = await import("./connection");
    expect(connectionMode()).toBe("desktop");
    asPhone();
    window.__TAURI_INTERNALS__ = {};
    expect(connectionMode()).toBe("desktop");
    delete window.__TAURI_INTERNALS__;
    vi.stubEnv("VITE_ENS_API_URL", "http://127.0.0.1:8765/api/v1");
    expect(connectionMode()).toBe("desktop");
  });

  it("is the phone for a production build without the Vite API env", async () => {
    asPhone();
    const { connectionMode } = await import("./connection");
    expect(connectionMode()).toBe("phone");
  });
});

describe("api.ts on a phone", () => {
  it("uses the same origin and the request header instead of a session token", async () => {
    asPhone();
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await import("./api");
    await api.health();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/health");
    expect(init.headers).toMatchObject({ "X-ENS-Request": "1" });
    expect(init.headers).not.toHaveProperty("X-Session-Token");
  });

  it("says the PC isn't reachable when the request cannot get through", async () => {
    asPhone();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const { api, PC_UNREACHABLE } = await import("./api");
    await expect(api.leads()).rejects.toMatchObject({ details: { code: PC_UNREACHABLE } });
  });

  it("treats Tailscale's bad-gateway answer as the PC being unreachable", async () => {
    asPhone();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Bad gateway", { status: 502 })));
    const { api, PC_UNREACHABLE } = await import("./api");
    await expect(api.leads()).rejects.toMatchObject({ details: { code: PC_UNREACHABLE } });
  });

  it("tells the app when the phone is no longer paired", async () => {
    asPhone();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ code: "PHONE_NOT_PAIRED", message: "Pair first", details: {}, correlation_id: "c" }),
          { status: 401 },
        ),
      ),
    );
    const { api, onPhoneUnpaired } = await import("./api");
    const listener = vi.fn();
    const stop = onPhoneUnpaired(listener);
    await expect(api.leads()).rejects.toBeTruthy();
    expect(listener).toHaveBeenCalledTimes(1);
    stop();
  });

  it("tracks changes and AI answers while the PC works, but not plain reads", async () => {
    asPhone();
    let finish: (response: Response) => void = () => undefined;
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url.endsWith("/health")
          ? Promise.resolve(new Response(JSON.stringify({ status: "ok" }), { status: 200 }))
          : new Promise<Response>((resolve) => {
              finish = resolve;
            }),
      ),
    );
    const { api } = await import("./api");
    const { currentPendingWork } = await import("./pendingWork");
    const kinds = () => currentPendingWork().map((item) => item.kind);

    await api.health();
    expect(kinds()).toEqual([]);

    const saving = api.addLeadNote("lead-1", "Asked for samples");
    await vi.waitFor(() => expect(kinds()).toEqual(["change"]));
    finish(new Response(JSON.stringify({ id: "lead-1" }), { status: 201 }));
    await saving;
    expect(kinds()).toEqual([]);

    const asking = api.sendAssistantMessage("conversation-1", "What should I offer?");
    await vi.waitFor(() => expect(kinds()).toEqual(["ai"]));
    finish(new Response(JSON.stringify({ id: "conversation-1", messages: [] }), { status: 200 }));
    await asking;
    expect(kinds()).toEqual([]);
  });
});

describe("pairing helpers", () => {
  it("reads the code from a QR link's fragment only on the pairing screen", async () => {
    const { codeFromLocation } = await import("./pairing");
    expect(codeFromLocation({ pathname: "/pair", hash: "#K7QM-4T9X" })).toBe("K7QM-4T9X");
    expect(codeFromLocation({ pathname: "/", hash: "#K7QM-4T9X" })).toBe("");
  });

  it("labels the browser and device for the PC's devices list", async () => {
    const { browserLabel } = await import("./pairing");
    expect(
      browserLabel(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1",
      ),
    ).toBe("Safari on iPhone");
    expect(
      browserLabel(
        "Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Mobile Safari/537.36",
      ),
    ).toBe("Chrome on Android");
  });
});
