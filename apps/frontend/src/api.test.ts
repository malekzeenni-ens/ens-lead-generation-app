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

describe("api.ts desktop host failures", () => {
  it("surfaces the host's startup failure and asks the host again on the next request", async () => {
    window.__TAURI_INTERNALS__ = {};
    invokeMock
      .mockRejectedValueOnce("The local service could not start: boom. Details are in backend-stderr.log in the logs folder.")
      .mockResolvedValueOnce({
        baseUrl: "http://127.0.0.1:54321/api/v1",
        sessionToken: "tauri-session-token",
      });
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ status: "ok" }), { status: 200 })),
    );

    const { api, BackendUnavailableError } = await import("./api");
    const failure = api.health();
    await expect(failure).rejects.toBeInstanceOf(BackendUnavailableError);
    await expect(failure).rejects.toThrow(/could not start: boom/);
    await expect(api.health()).resolves.toEqual({ status: "ok" });
    expect(invokeMock).toHaveBeenCalledTimes(2);
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
      .mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify({}), { status: 200 })),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await import("./api");

    await api.suppressLead("lead-1", { reason: "no longer relevant" });

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ reason: "no longer relevant" }));
  });

  it("maps campaign deletion to the guarded cascade endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          deleted: true,
          campaign_id: "campaign-1",
          associated_leads: 2,
          leads_deleted: 2,
          shared_leads_retained: 0,
          outreach_batches_deleted: 1,
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await import("./api");

    await api.deleteCampaign("campaign-1");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8765/api/v1/campaigns/campaign-1");
    expect(init.method).toBe("DELETE");
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

  it("reports an unreachable backend instead of a raw network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const { api, ApiError } = await import("./api");
    const failure = api.health();
    await expect(failure).rejects.toBeInstanceOf(ApiError);
    await expect(failure).rejects.toMatchObject({ details: { code: "BACKEND_UNREACHABLE" } });
  });

  it("describes a non-JSON error response with its status and correlation ID", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<html>Bad gateway</html>", {
          status: 502,
          headers: { "X-Correlation-ID": "corr-502" },
        }),
      ),
    );
    const { api } = await import("./api");
    await expect(api.health()).rejects.toMatchObject({
      details: { code: "HTTP_502", correlation_id: "corr-502" },
    });
  });

  it("gives up on a request that does not answer in time", async () => {
    vi.useFakeTimers();
    try {
      vi.stubGlobal(
        "fetch",
        vi.fn(
          (_url: string, init: RequestInit) =>
            new Promise((_resolve, reject) => {
              init.signal?.addEventListener("abort", () => reject(new Error("aborted")));
            }),
        ),
      );
      const { api } = await import("./api");
      const pending = api.health();
      const expectation = expect(pending).rejects.toMatchObject({
        details: { code: "REQUEST_TIMEOUT" },
      });
      await vi.advanceTimersByTimeAsync(60_000);
      await expectation;
    } finally {
      vi.useRealTimers();
    }
  });

  it("resolves an empty 204 response without parsing a body", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    const { api } = await import("./api");
    await expect(api.health()).resolves.toBeUndefined();
  });

  it("maps outreach review and Zoho handoff actions to their API routes", async () => {
    const fetchMock = vi
      .fn()
      .mockImplementation(() =>
        Promise.resolve(new Response(JSON.stringify({}), { status: 200 })),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await import("./api");

    await api.createOutreachBatch({
      lead_ids: ["lead-1"],
      template_id: "template-1",
      campaign_id: "campaign-1",
    });
    await api.editOutreachDraft("draft-1", { subject: "Hello", body: "Personal note" });
    await api.approveOutreachDraft("draft-1");
    await api.rejectOutreachDraft("draft-1", "Not this week");
    await api.reopenOutreachDraft("draft-1");
    await api.prepareOutreachZohoHandoff("draft-1");
    await api.recordOutreachZohoOpenFailure("draft-1", "Composer unavailable");
    await api.confirmOutreachDraftSent("draft-1");

    const calls = fetchMock.mock.calls as Array<[string, RequestInit]>;
    expect(calls.map(([url]) => url)).toEqual([
      "http://127.0.0.1:8765/api/v1/outreach/batches",
      "http://127.0.0.1:8765/api/v1/outreach/drafts/draft-1",
      "http://127.0.0.1:8765/api/v1/outreach/drafts/draft-1/approve",
      "http://127.0.0.1:8765/api/v1/outreach/drafts/draft-1/reject",
      "http://127.0.0.1:8765/api/v1/outreach/drafts/draft-1/reopen",
      "http://127.0.0.1:8765/api/v1/outreach/drafts/draft-1/zoho-open",
      "http://127.0.0.1:8765/api/v1/outreach/drafts/draft-1/zoho-open-failed",
      "http://127.0.0.1:8765/api/v1/outreach/drafts/draft-1/sent-confirmed",
    ]);
    expect(calls[0]?.[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({
        lead_ids: ["lead-1"],
        template_id: "template-1",
        campaign_id: "campaign-1",
      }),
    });
    expect(calls[1]?.[1]).toMatchObject({ method: "PATCH" });
    expect(calls[3]?.[1].body).toBe(JSON.stringify({ reason: "Not this week" }));
    expect(calls[6]?.[1].body).toBe(JSON.stringify({ reason: "Composer unavailable" }));
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

describe("api.ts background jobs", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_ENS_API_URL", "http://127.0.0.1:8765/api/v1");
    vi.stubEnv("VITE_ENS_SESSION_TOKEN", "dev-session-token");
  });

  function job(overrides: Record<string, unknown>): Response {
    return new Response(
      JSON.stringify({
        id: "job-1",
        kind: "catalogue_enrichment",
        status: "running",
        progress_current: 0,
        progress_total: 3,
        result: null,
        error_code: null,
        error_message: null,
        cancellation_requested: false,
        created_at: "2026-10-18T10:00:00Z",
        started_at: null,
        completed_at: null,
        ...overrides,
      }),
      { status: 200 },
    );
  }

  it("follows a job to its result and reports progress on the way", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(job({ status: "queued" }))
      .mockResolvedValueOnce(job({ progress_current: 2 }))
      .mockResolvedValueOnce(
        job({ status: "succeeded", progress_current: 3, result: { products_enriched: 3 } }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { api } = await import("./api");
    const progress: number[] = [];

    const result = await api.runEnrichment(false, {
      pollIntervalMs: 1,
      onProgress: (current) => progress.push(current),
    });

    expect(result).toEqual({ products_enriched: 3 });
    expect(progress).toEqual([0, 2, 3]);
    expect((fetchMock.mock.calls[1] as [string])[0]).toBe("http://127.0.0.1:8765/api/v1/jobs/job-1");
  });

  it("asks the backend to cancel when aborted and reports the stop", async () => {
    const controller = new AbortController();
    controller.abort();
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(job({}))
      .mockResolvedValueOnce(job({ status: "cancelled", cancellation_requested: true }));
    vi.stubGlobal("fetch", fetchMock);
    const { api, JOB_CANCELLED } = await import("./api");

    await expect(
      api.runEnrichment(false, { pollIntervalMs: 1, signal: controller.signal }),
    ).rejects.toMatchObject({ details: { code: JOB_CANCELLED } });
    const [url, init] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8765/api/v1/jobs/job-1/cancel");
    expect(init.method).toBe("POST");
  });

  it("rejects with the job's own error when it fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValueOnce(
        job({
          status: "failed",
          error_code: "ENRICHMENT_PROTECTED_PROFILE",
          error_message: "Enrichment is paused while the engraving software is running.",
        }),
      ),
    );
    const { api } = await import("./api");
    await expect(api.autofillLeads(["lead-1"], { pollIntervalMs: 1 })).rejects.toMatchObject({
      message: "Enrichment is paused while the engraving software is running.",
      details: { code: "ENRICHMENT_PROTECTED_PROFILE" },
    });
  });
});
