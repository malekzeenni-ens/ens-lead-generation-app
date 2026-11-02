# ADR-025: Phone access through a loopback gateway and Tailscale

- **Status:** Accepted (operator decision, 2 November 2026)
- **Context:** The operator wants to use the app from a phone's browser while the PC runs it, at home and away. ADR-015 binds the API to `127.0.0.1` with a per-run token that only the desktop window receives, so a phone cannot reach it, and the token cannot be handed to a browser without handing it to anyone who loads the page.
- **Decision:** Keep ADR-015 as it is and add a second, opt-in listener, the *phone gateway*, on a fixed loopback port (default `127.0.0.1:8770`). Tailscale (`tailscale serve`) forwards `https://<pc>.<tailnet>.ts.net` to it, so the phone gets WireGuard encryption and a real TLS certificate while nothing in the app listens beyond loopback. The gateway serves the built frontend and the same API, but authenticates a paired phone instead of the session token, and refuses desktop-only routes.
- **Alternatives considered:** Binding to the LAN (`0.0.0.0`) with a self-signed certificate (reverses ADR-015, certificate warnings, reachable by every device on the Wi-Fi, home only); handing the session token to the phone (one leak gives full access, no revocation); remote desktop (works, but not usable at phone size).

## How a phone is trusted

- **Pairing:** the desktop issues a one-time code (8 characters from an alphabet without look-alikes, 5 minutes, at most 5 attempts). The QR code puts it in the URL fragment so it is never sent in a request line or logged.
- **Device credential:** pairing returns a random 256-bit secret in an `HttpOnly; Secure; SameSite=Strict` cookie scoped to `/api`. Only its SHA-256 hash is stored. A device expires after 30 days without use; every use extends it. The operator can revoke one device or all of them from the desktop, with immediate effect.
- **Every request:** the gateway checks the `Host` header against the configured Tailscale name or loopback (DNS rebinding), requires `Origin` to match and an `X-ENS-Request` header on every change (CSRF), and sends a strict content-security policy and `Cache-Control: no-store` on API responses.
- **Route policy:** a `DesktopOnly` dependency returns `403 DESKTOP_ONLY` on the gateway. Desktop-only: connections and keys, backups, exports, workspace settings changes, diagnostics, shutdown, the API schema, phone access management, and catalogue and template changes (they are read-only on the phone). A test walks every registered route so a new one cannot go unclassified.
- **Attribution:** audit events from the gateway record `actor = phone:<device id>`.

## Consequences

- The gateway runs in the backend process, so there is still one scheduler, one job manager and one database writer. It is started and stopped at runtime from Settings and is off by default.
- The phone needs the PC awake with the app open. Local AI still runs on the PC, unchanged.
- The packaged backend carries a copy of the built frontend to serve to phones.
- Tailscale is a third-party coordination service; it sees device names and addresses, not app traffic. Its free personal plan covers this use.

## Security/compliance impact

No lead data is stored on the phone (no service worker, `no-store`). Exports and backups cannot leave through the phone. Revocation does not depend on the phone. See `SECURITY_MODEL.md` and CMP-016.

## Rollback

Switch phone access off in Settings, or remove the `tailscale serve` mapping. Dropping the two pairing tables is a reversible migration.
