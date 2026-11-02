import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { beginPending, clearPendingWork } from "../pendingWork";
import type { ApiErrorShape, MobileAccessStatus, TailscaleStatus } from "../types";
import { PendingWorkIndicator, REASSURE_AFTER_MS, SHOW_AFTER_MS } from "./PendingWorkIndicator";
import { PhoneAccessPanel } from "./PhoneAccessPanel";
import { PhoneGate } from "./PhoneGate";
import { PhoneMoreSheet, PhoneTabBar } from "./PhoneNavigation";

const unpairedListeners = new Set<() => void>();

vi.mock("../api", () => {
  class MockApiError extends Error {
    details: ApiErrorShape;
    constructor(details: ApiErrorShape) {
      super(details.message);
      this.details = details;
    }
  }
  return {
    ApiError: MockApiError,
    PHONE_NOT_PAIRED: "PHONE_NOT_PAIRED",
    PC_UNREACHABLE: "PC_UNREACHABLE",
    onPhoneUnpaired: (listener: () => void) => {
      unpairedListeners.add(listener);
      return () => unpairedListeners.delete(listener);
    },
    api: {
      mobileSession: vi.fn(),
      pairPhone: vi.fn(),
      mobileStatus: vi.fn(),
      mobileDevices: vi.fn(),
      tailscaleStatus: vi.fn(),
      updateMobileConfig: vi.fn(),
      issuePairingCode: vi.fn(),
      revokeMobileDevice: vi.fn(),
      revokeAllMobileDevices: vi.fn(),
      startTailscaleServe: vi.fn(),
      stopTailscaleServe: vi.fn(),
    },
  };
});
vi.mock("@tauri-apps/plugin-opener", () => ({ openUrl: vi.fn() }));

const { api, ApiError } = await import("../api");

function apiError(code: string, message = "Refused"): Error {
  return new ApiError({ code, message, details: {}, correlation_id: "" });
}

const device = {
  id: "device-1",
  name: "My iPhone",
  label: "Safari on iPhone",
  created_at: "2026-11-02T09:00:00Z",
  last_seen_at: "2026-11-02T09:30:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  unpairedListeners.clear();
  window.history.replaceState(null, "", "/");
});

afterEach(() => {
  vi.useRealTimers();
  clearPendingWork();
});

describe("PhoneGate", () => {
  it("shows the workspace once the PC says this phone is paired", async () => {
    vi.mocked(api.mobileSession).mockResolvedValue({ channel: "phone", device });
    render(<PhoneGate>{(session) => <p>Workspace for {session.device?.name}</p>}</PhoneGate>);
    expect(await screen.findByText("Workspace for My iPhone")).toBeInTheDocument();
  });

  it("pairs with the code from a QR link and then shows the workspace", async () => {
    window.history.replaceState(null, "", "/pair#K7QM-4T9X");
    vi.mocked(api.mobileSession).mockRejectedValue(apiError("PHONE_NOT_PAIRED"));
    vi.mocked(api.pairPhone).mockResolvedValue({ channel: "phone", device });
    const user = userEvent.setup();
    render(<PhoneGate>{() => <p>Workspace</p>}</PhoneGate>);

    expect(await screen.findByRole("heading", { name: "Pair this phone" })).toBeInTheDocument();
    expect(screen.getByLabelText("Pairing code")).toHaveValue("K7QM-4T9X");
    await user.clear(screen.getByLabelText("Name this phone"));
    await user.type(screen.getByLabelText("Name this phone"), "My iPhone");
    await user.click(screen.getByRole("button", { name: "Pair" }));

    expect(api.pairPhone).toHaveBeenCalledWith("K7QM-4T9X", "My iPhone", expect.any(String));
    expect(await screen.findByText("Workspace")).toBeInTheDocument();
    expect(window.location.pathname).toBe("/");
  });

  it("explains a wrong code and keeps the form", async () => {
    vi.mocked(api.mobileSession).mockRejectedValue(apiError("PHONE_NOT_PAIRED"));
    vi.mocked(api.pairPhone).mockRejectedValue(apiError("PAIRING_CODE_WRONG", "That code doesn't match. 4 tries left."));
    const user = userEvent.setup();
    render(<PhoneGate>{() => <p>Workspace</p>}</PhoneGate>);
    await user.type(await screen.findByLabelText("Pairing code"), "AAAA-AAAA");
    await user.click(screen.getByRole("button", { name: "Pair" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("4 tries left");
  });

  it("says the PC isn't reachable and tries again on request", async () => {
    vi.mocked(api.mobileSession)
      .mockRejectedValueOnce(apiError("PC_UNREACHABLE", "Your PC isn't reachable."))
      .mockResolvedValueOnce({ channel: "phone", device });
    const user = userEvent.setup();
    render(<PhoneGate>{() => <p>Workspace</p>}</PhoneGate>);
    expect(await screen.findByRole("heading", { name: "Your PC isn't reachable" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Workspace")).toBeInTheDocument();
  });

  it("returns to pairing when the phone is revoked mid-session", async () => {
    vi.mocked(api.mobileSession).mockResolvedValue({ channel: "phone", device });
    render(<PhoneGate>{() => <p>Workspace</p>}</PhoneGate>);
    await screen.findByText("Workspace");
    act(() => {
      for (const listener of unpairedListeners) listener();
    });
    expect(await screen.findByRole("heading", { name: "Pair this phone" })).toBeInTheDocument();
  });
});

describe("PendingWorkIndicator", () => {
  it("stays hidden for quick work, then says what the PC is doing", () => {
    vi.useFakeTimers();
    render(<PendingWorkIndicator />);
    const status = screen.getByRole("status");
    let handle: ReturnType<typeof beginPending> | undefined;
    act(() => {
      handle = beginPending("change");
    });
    expect(status).toHaveAttribute("data-visible", "false");

    act(() => {
      vi.advanceTimersByTime(SHOW_AFTER_MS + 300);
    });
    expect(status).toHaveTextContent("Saving on your PC…");

    act(() => {
      vi.advanceTimersByTime(REASSURE_AFTER_MS);
    });
    expect(status).toHaveTextContent("taking a while");

    act(() => {
      handle?.end();
    });
    expect(status).toHaveAttribute("data-visible", "false");
  });

  it("puts an AI answer or a job ahead of a save, with job progress", () => {
    vi.useFakeTimers();
    render(<PendingWorkIndicator />);
    act(() => {
      beginPending("change");
      const job = beginPending("job");
      job.progress(3, 10);
    });
    act(() => {
      vi.advanceTimersByTime(SHOW_AFTER_MS + 300);
    });
    const status = screen.getByRole("status");
    expect(status).toHaveTextContent("Working on your PC… 3 of 10");
    expect(status).toHaveTextContent("+1");

    act(() => {
      beginPending("ai");
    });
    act(() => {
      vi.advanceTimersByTime(SHOW_AFTER_MS + 300);
    });
    expect(status).toHaveTextContent("Thinking on your PC…");
    act(() => {
      vi.advanceTimersByTime(REASSURE_AFTER_MS);
    });
    expect(status).toHaveTextContent("carries on on your PC");
  });
});

describe("Phone navigation", () => {
  it("shows the daily work as tabs with badges, and the rest under More", async () => {
    const onSelect = vi.fn();
    const onMore = vi.fn();
    const user = userEvent.setup();
    render(
      <PhoneTabBar
        active="leads"
        onSelect={onSelect}
        moreOpen={false}
        onMore={onMore}
        shortlistBadge={10}
        draftsBadge={4}
      />,
    );
    const nav = screen.getByRole("navigation", { name: "Workspace navigation" });
    expect(within(nav).getByLabelText("10 awaiting a decision")).toBeInTheDocument();
    expect(within(nav).getByLabelText("4 awaiting approval")).toBeInTheDocument();
    expect(within(nav).getByRole("button", { name: /More/ })).toHaveAttribute("aria-current", "page");
    await user.click(within(nav).getByRole("button", { name: /Pipeline/ }));
    expect(onSelect).toHaveBeenCalledWith("pipeline");
    await user.click(within(nav).getByRole("button", { name: /More/ }));
    expect(onMore).toHaveBeenCalled();
  });

  it("opens screens from the More sheet and closes on Esc", async () => {
    const onSelect = vi.fn();
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<PhoneMoreSheet active="overview" onSelect={onSelect} onClose={onClose} />);
    const sheet = screen.getByRole("dialog", { name: "More" });
    expect(within(sheet).getByRole("button", { name: /Catalogue/ })).toHaveTextContent("View only");
    await user.click(within(sheet).getByRole("button", { name: /Campaigns/ }));
    expect(onSelect).toHaveBeenCalledWith("campaigns");
    expect(onClose).toHaveBeenCalled();
    onClose.mockClear();
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});

describe("PhoneAccessPanel", () => {
  const off: MobileAccessStatus = {
    enabled: false,
    running: false,
    port: 8770,
    public_host: "",
    phone_url: null,
    error: null,
    paired_devices: 0,
    phone_app_ready: true,
  };
  const on: MobileAccessStatus = {
    ...off,
    enabled: true,
    running: true,
    public_host: "ens-pc.tail1a2b.ts.net",
    phone_url: "https://ens-pc.tail1a2b.ts.net/",
  };
  const serving: TailscaleStatus = {
    installed: true,
    running: true,
    dns_name: "ens-pc.tail1a2b.ts.net",
    serving: true,
    install_url: "https://tailscale.com/download/windows",
  };

  it("switches phone access on", async () => {
    vi.mocked(api.mobileStatus).mockResolvedValueOnce(off).mockResolvedValue(on);
    vi.mocked(api.mobileDevices).mockResolvedValue([]);
    vi.mocked(api.tailscaleStatus).mockResolvedValue(serving);
    vi.mocked(api.updateMobileConfig).mockResolvedValue(on);
    const user = userEvent.setup();
    render(<PhoneAccessPanel />);
    expect(await screen.findByText("Off")).toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: /Allow paired phones to connect/ }));
    expect(api.updateMobileConfig).toHaveBeenCalledWith({ enabled: true });
    expect(await screen.findByText(/On your phone, open/)).toHaveTextContent("https://ens-pc.tail1a2b.ts.net/");
  });

  it("asks for Tailscale when it isn't installed", async () => {
    vi.mocked(api.mobileStatus).mockResolvedValue(on);
    vi.mocked(api.mobileDevices).mockResolvedValue([]);
    vi.mocked(api.tailscaleStatus).mockResolvedValue({ ...serving, installed: false, running: false, serving: false });
    render(<PhoneAccessPanel />);
    expect(await screen.findByText("Tailscale isn't installed on this PC.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Get Tailscale/ })).toBeInTheDocument();
  });

  it("shows a pairing QR code and code, then notices the new phone", async () => {
    vi.mocked(api.mobileStatus).mockResolvedValue(on);
    vi.mocked(api.mobileDevices).mockResolvedValueOnce([]).mockResolvedValue([device]);
    vi.mocked(api.tailscaleStatus).mockResolvedValue(serving);
    vi.mocked(api.issuePairingCode).mockResolvedValue({
      code: "K7QM-4T9X",
      expires_at: new Date(Date.now() + 300_000).toISOString(),
      pair_url: "https://ens-pc.tail1a2b.ts.net/pair#K7QM-4T9X",
    });
    const user = userEvent.setup();
    render(<PhoneAccessPanel />);
    await user.click(await screen.findByRole("button", { name: "Pair a phone" }));
    expect(await screen.findByText("K7QM-4T9X")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /QR code/ })).toBeInTheDocument();
    expect(screen.getByRole("timer")).toHaveTextContent(/Expires in [45]:/);
    await waitFor(() => expect(screen.queryByText("K7QM-4T9X")).not.toBeInTheDocument(), { timeout: 5000 });
    expect(await screen.findByText("My iPhone")).toBeInTheDocument();
  });

  it("removes a paired phone", async () => {
    vi.mocked(api.mobileStatus).mockResolvedValue({ ...on, paired_devices: 1 });
    vi.mocked(api.mobileDevices).mockResolvedValueOnce([device]).mockResolvedValue([]);
    vi.mocked(api.tailscaleStatus).mockResolvedValue(serving);
    vi.mocked(api.revokeMobileDevice).mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<PhoneAccessPanel />);
    await user.click(await screen.findByRole("button", { name: "Remove" }));
    expect(api.revokeMobileDevice).toHaveBeenCalledWith("device-1");
    expect(await screen.findByText("No phones paired.")).toBeInTheDocument();
  });
});
