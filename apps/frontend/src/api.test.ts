import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ApiErrorShape } from "./types";

function readBlobText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      resolve(typeof reader.result === "string" ? reader.result : "");
    };
    reader.onerror = () => {
      reject(new Error(reader.error?.message ?? "Failed to read blob"));
    };
    reader.readAsText(blob);
  });
}

const invokeMock = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({
  invoke: (...args: unknown[]): unknown => invokeMock(...args),
}));

beforeEach(() => {
  vi.resetModules();
  invokeMock.mockReset();
  delete window.__TAURI_INTERNALS__;
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
  delete window.__TAURI_INTERNALS__;
});

describe("api.ts connection resolution", () => {
  it("resolves the base URL and session token via the Tauri backend_connection command", async () => {
    window.__TAURI_INTERNALS__ = {};
    invokeMock.mockResolvedValueOnce({
      baseUrl: "http://127.0.0.1:54321/api/v1",
      sessionToken: "tauri-session-token",
    });
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("./api");
    await api.health();

    expect(invokeMock).toHaveBeenCalledWith("backend_connection");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:54321/api/v1/health");
    expect(init.headers).toMatchObject({
      "X-Session-Token": "tauri-session-token",
      "Content-Type": "application/json",
    });
  });

  it("caches the resolved connection across multiple calls instead of re-resolving it", async () => {
    window.__TAURI_INTERNALS__ = {};
    invokeMock.mockResolvedValueOnce({
      baseUrl: "http://127.0.0.1:54321/api/v1",
      sessionToken: "tauri-session-token",
    });
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockImplementation(
          () => new Response(JSON.stringify({ status: "ok" }), { status: 200 }),
        ),
    );

    const { api } = await import("./api");
    await api.health();
    await api.health();

    expect(invokeMock).toHaveBeenCalledTimes(1);
  });

  it("falls back to the Vite env vars when not running inside Tauri", async () => {
    vi.stubEnv("VITE_ENS_API_URL", "http://127.0.0.1:8765/api/v1");
    vi.stubEnv("VITE_ENS_SESSION_TOKEN", "dev-session-token");
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("./api");
    await api.health();

    expect(invokeMock).not.toHaveBeenCalled();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8765/api/v1/health");
    expect(init.headers).toMatchObject({ "X-Session-Token": "dev-session-token" });
  });

  it("throws a descriptive error and makes no request when no backend connection is available", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { api } = await import("./api");
    await expect(api.health()).rejects.toThrow(/Start Etch N Shine\.cmd/);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("api.ts request handling", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_ENS_API_URL", "http://127.0.0.1:8765/api/v1");
    vi.stubEnv("VITE_ENS_SESSION_TOKEN", "dev-session-token");
  });

  it("resolves with the parsed JSON body on a successful response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 })),
    );
    const { api } = await import("./api");
    await expect(api.health()).resolves.toEqual({ status: "ok" });
  });

  it("serializes POST bodies as JSON and sends the configured HTTP method", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await import("./api");

    await api.suppressLead("lead-1", { reason: "no longer relevant" });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ reason: "no longer relevant" }));
  });

  it("throws an ApiError carrying the parsed error body on a non-ok response", async () => {
    const errorBody: ApiErrorShape = {
      code: "SESSION_TOKEN_INVALID",
      message: "The local application session is not authorised.",
      details: {},
      correlation_id: "corr-123",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify(errorBody), { status: 401 })),
    );
    const { api, ApiError } = await import("./api");

    const error: unknown = await api.health().catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as InstanceType<typeof ApiError>).details).toEqual(errorBody);
    expect((error as Error).message).toBe(errorBody.message);
  });
});

describe("api.ts exportLeads", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_ENS_API_URL", "http://127.0.0.1:8765/api/v1");
    vi.stubEnv("VITE_ENS_SESSION_TOKEN", "dev-session-token");
  });

  it("resolves the filename from Content-Disposition and returns the response blob", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("id,name\n1,Test", {
          status: 200,
          headers: { "Content-Disposition": 'attachment; filename="leads-export.csv"' },
        }),
      ),
    );
    const { api } = await import("./api");

    const result = await api.exportLeads("csv");

    expect(result.filename).toBe("leads-export.csv");
    expect(await readBlobText(result.blob)).toBe("id,name\n1,Test");
  });

  it("falls back to a default filename when Content-Disposition is absent", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("[]", { status: 200 })),
    );
    const { api } = await import("./api");

    const result = await api.exportLeads("json");

    expect(result.filename).toBe("etch-n-shine-leads.json");
  });
});
