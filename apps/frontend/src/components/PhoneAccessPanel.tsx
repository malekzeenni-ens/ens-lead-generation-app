import qrcode from "qrcode-generator";
import { ExternalLink, QrCode, RefreshCw, Smartphone, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, api } from "../api";
import { openExternalUrl } from "../external";
import type { MobileAccessStatus, MobileDevice, PairingCode, TailscaleStatus } from "../types";
import { DangerConfirm, LoadingState, StatusPill, type StatusTone } from "./DesignSystem";

function message(caught: unknown): string {
  return caught instanceof Error ? caught.message : "Something went wrong. Try again.";
}

/** The pairing link as a QR code, drawn as SVG squares so no markup is injected. */
export function PairingQr({ value }: { value: string }) {
  const cells = useMemo(() => {
    const code = qrcode(0, "M");
    code.addData(value);
    code.make();
    const count = code.getModuleCount();
    const dark: [number, number][] = [];
    for (let row = 0; row < count; row += 1) {
      for (let column = 0; column < count; column += 1) {
        if (code.isDark(row, column)) dark.push([column, row]);
      }
    }
    return { count, dark };
  }, [value]);
  const size = cells.count + 8;
  return (
    <svg
      className="pairing-qr"
      viewBox={`-4 -4 ${size} ${size}`}
      role="img"
      aria-label="QR code that opens the pairing page on your phone"
      shapeRendering="crispEdges"
    >
      <rect x={-4} y={-4} width={size} height={size} fill="#ffffff" />
      {cells.dark.map(([x, y]) => (
        <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill="#07131e" />
      ))}
    </svg>
  );
}

function secondsLeft(expiresAt: string, now: number): number {
  return Math.max(0, Math.round((new Date(expiresAt).getTime() - now) / 1000));
}

function overview(
  status: MobileAccessStatus,
  tailscale: TailscaleStatus | null,
): { tone: StatusTone; label: string; detail: string } {
  if (!status.enabled) return { tone: "neutral", label: "Off", detail: "Phones can't reach this PC." };
  if (status.error) return { tone: "warning", label: "Needs attention", detail: status.error };
  if (!status.phone_app_ready) {
    return {
      tone: "warning",
      label: "Needs attention",
      detail: "The phone app files aren't built. Run npm run frontend:build, then refresh.",
    };
  }
  if (tailscale && !tailscale.installed) {
    return { tone: "warning", label: "Needs attention", detail: "Tailscale isn't installed on this PC." };
  }
  if (tailscale && !tailscale.running) {
    return { tone: "warning", label: "Needs attention", detail: "Tailscale isn't signed in on this PC." };
  }
  if (tailscale && !tailscale.serving) {
    return { tone: "warning", label: "Needs attention", detail: "Set up the phone address below." };
  }
  const phones = status.paired_devices === 1 ? "1 phone paired" : `${status.paired_devices} phones paired`;
  return { tone: "success", label: "On", detail: phones };
}

export function PhoneAccessPanel() {
  const [status, setStatus] = useState<MobileAccessStatus | null>(null);
  const [tailscale, setTailscale] = useState<TailscaleStatus | null>(null);
  const [devices, setDevices] = useState<MobileDevice[]>([]);
  // The phones already paired when the code was shown, so a new one is noticed.
  const [pairing, setPairing] = useState<{ code: PairingCode; known: Set<string> } | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [adminUrl, setAdminUrl] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [nextStatus, nextDevices, nextTailscale] = await Promise.all([
        api.mobileStatus(),
        api.mobileDevices(),
        api.tailscaleStatus(),
      ]);
      setStatus(nextStatus);
      setDevices(nextDevices);
      setTailscale(nextTailscale);
    } catch (caught) {
      setError(message(caught));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  // While a code is showing, watch for the phone to finish pairing and count down.
  useEffect(() => {
    if (!pairing) return;
    const tick = window.setInterval(() => setNow(Date.now()), 1000);
    const poll = window.setInterval(() => {
      void api.mobileDevices().then((next) => {
        setDevices(next);
        if (next.some((device) => !pairing.known.has(device.id))) {
          setPairing(null);
          void load();
        }
      }).catch(() => undefined);
    }, 3000);
    return () => {
      window.clearInterval(tick);
      window.clearInterval(poll);
    };
  }, [pairing, load]);

  async function run(action: () => Promise<unknown>): Promise<void> {
    setWorking(true);
    setError(null);
    setAdminUrl(null);
    try {
      await action();
      await load();
    } catch (caught) {
      setError(message(caught));
      if (caught instanceof ApiError && typeof caught.details.details.admin_url === "string") {
        setAdminUrl(caught.details.details.admin_url);
      }
    } finally {
      setWorking(false);
    }
  }

  if (!status) {
    return error ? <p className="form-error" role="alert">{error}</p> : <LoadingState label="Loading phone access" />;
  }
  const summary = overview(status, tailscale);
  const remaining = pairing ? secondsLeft(pairing.code.expires_at, now) : 0;

  return (
    <section className="form-panel settings-grid__wide phone-access" aria-labelledby="phone-access-heading">
      <div className="subsection-heading">
        <div>
          <h3 id="phone-access-heading">Phone access</h3>
          <p>Use the app from your phone's browser while this PC runs it, through Tailscale.</p>
        </div>
        <StatusPill tone={summary.tone}>{summary.label}</StatusPill>
      </div>
      <p className="supporting-copy">{summary.detail}</p>

      <label className="toggle-row">
        <input
          id="phone-access-enabled"
          type="checkbox"
          checked={status.enabled}
          disabled={working}
          onChange={(event) => {
            const enabled = event.target.checked;
            void run(() => api.updateMobileConfig({ enabled }));
          }}
        />
        <span>
          <strong>Allow paired phones to connect</strong>
          <small>Off by default. Turning it off disconnects every phone at once.</small>
        </span>
      </label>

      {status.enabled ? (
        <>
          <div className="phone-access__step">
            <h4>Phone address</h4>
            {!tailscale ? (
              <LoadingState label="Checking Tailscale" />
            ) : !tailscale.installed ? (
              <p>
                Install Tailscale on this PC and on your phone, and sign in to the same account on both.{" "}
                <button type="button" className="tertiary-action" onClick={() => void openExternalUrl(tailscale.install_url)}>
                  Get Tailscale <ExternalLink size={14} aria-hidden="true" />
                </button>
              </p>
            ) : !tailscale.running ? (
              <p>Tailscale is installed but not signed in. Open Tailscale on this PC and sign in.</p>
            ) : tailscale.serving && status.phone_url ? (
              <div className="phone-access__address">
                <p>
                  On your phone, open <strong>{status.phone_url}</strong>
                </p>
                <button type="button" className="tertiary-action" disabled={working} onClick={() => void run(() => api.stopTailscaleServe())}>
                  Remove phone address
                </button>
              </div>
            ) : (
              <div className="phone-access__address">
                <p>This PC is <strong>{tailscale.dns_name}</strong> on Tailscale. Set up its HTTPS address for phones.</p>
                <button type="button" className="secondary-action" disabled={working} onClick={() => void run(() => api.startTailscaleServe())}>
                  Set up phone address
                </button>
              </div>
            )}
            <button type="button" className="tertiary-action" disabled={working} onClick={() => void load()}>
              <RefreshCw size={14} aria-hidden="true" /> Check again
            </button>
          </div>

          <div className="phone-access__step">
            <h4>Pair a phone</h4>
            {pairing && remaining > 0 ? (
              <div className="phone-access__pairing">
                {pairing.code.pair_url ? <PairingQr value={pairing.code.pair_url} /> : null}
                <div>
                  <p>Scan with your phone's camera, or open the phone address and type:</p>
                  <p className="phone-access__code" aria-label={`Pairing code ${pairing.code.code.split("").join(" ")}`}>
                    {pairing.code.code}
                  </p>
                  <p className="supporting-copy" role="timer">
                    Expires in {Math.floor(remaining / 60)}:{String(remaining % 60).padStart(2, "0")}. Works once.
                  </p>
                  <button type="button" className="tertiary-action" onClick={() => setPairing(null)}>Cancel</button>
                </div>
              </div>
            ) : (
              <button
                type="button"
                className="primary-action"
                disabled={working || !status.running}
                onClick={() =>
                  void run(async () => {
                    setNow(Date.now());
                    const code = await api.issuePairingCode();
                    setPairing({ code, known: new Set(devices.map((device) => device.id)) });
                  })
                }
              >
                <QrCode size={17} aria-hidden="true" /> {pairing ? "Show a new code" : "Pair a phone"}
              </button>
            )}
          </div>
        </>
      ) : null}

      <div className="phone-access__step">
        <h4>Paired phones</h4>
        {devices.length === 0 ? (
          <p className="supporting-copy">No phones paired.</p>
        ) : (
          <>
            <ul className="phone-devices" aria-label="Paired phones">
              {devices.map((device) => (
                <li key={device.id}>
                  <Smartphone size={18} aria-hidden="true" />
                  <span>
                    <strong>{device.name}</strong>
                    <small>
                      {device.label ? `${device.label} · ` : ""}last used {new Date(device.last_seen_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" })}
                    </small>
                  </span>
                  <button
                    type="button"
                    className="tertiary-action"
                    disabled={working}
                    onClick={() => void run(() => api.revokeMobileDevice(device.id))}
                  >
                    <Trash2 size={14} aria-hidden="true" /> Remove
                  </button>
                </li>
              ))}
            </ul>
            {devices.length > 1 ? (
              <DangerConfirm
                intensity="two-step"
                label="Remove all phones"
                disabled={working}
                onConfirm={() => void run(() => api.revokeAllMobileDevices())}
              />
            ) : null}
          </>
        )}
      </div>

      {error ? (
        <p className="form-error" role="alert">
          {error}
          {adminUrl ? (
            <>
              {" "}
              <button type="button" className="tertiary-action" onClick={() => void openExternalUrl(adminUrl)}>
                Open Tailscale settings
              </button>
            </>
          ) : null}
        </p>
      ) : null}
    </section>
  );
}
