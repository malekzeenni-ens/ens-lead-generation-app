# Mobile access plan

**Plan date:** 2 November 2026
**Source:** Operator request: "run it on my machine, then open it from my phone".
**Status:** Proposed. Not started. Operator agreed on 2 November 2026 that some areas can be read-only on the phone (section 4.3); the transport choice (2.1) is still open.
**Branch:** `mobile/access`, one commit per item.
**Scope:** An opt-in way to use the app from a phone's browser while the PC runs it, and a phone layout for the daily workflow screens. The desktop app, its loopback binding and its per-run session token (ADR-015) stay exactly as they are. No scoring, campaign, outreach or data-model changes beyond one table for paired phones.

## 1. Goals

From the operator's point of view:

- open the app on the phone and work through today's list: shortlist, follow-ups, drafts to approve;
- send an approved draft from the phone's own mail app, then confirm it was sent;
- look up a lead and ask the AI assistant about it;
- never expose the app to anyone else on the Wi-Fi, and switch phone access off with one control;
- not need to re-learn anything: same screens, same words, same safety rules, laid out for a thumb.

Not goals: an app-store app, offline use, notifications, or managing connections, secrets and backups from the phone.

## 2. Decisions for the operator

### 2.1 How the phone reaches the PC (recommended: Tailscale)

| | **A. Tailscale (recommended)** | B. Home Wi-Fi only |
|---|---|---|
| What it is | Free private network between your own devices. Install on PC and phone, sign in to the same account. | The phone talks to the PC's Wi-Fi address directly. |
| Backend binding | Stays on `127.0.0.1`. Tailscale forwards to it. | Must listen on the network card: ADR-015 reversed. |
| Encryption | WireGuard, plus a real HTTPS certificate (`https://<pc>.<tailnet>.ts.net`) issued automatically. | Self-signed certificate: the phone shows a warning and has to be told to trust it, or plain HTTP that anyone on the Wi-Fi can read. |
| Who can reach it | Only devices signed into your Tailscale account. | Anyone on the Wi-Fi can reach the login. |
| Away from home | Works on 4G/5G too. | Home only. |
| "Add to Home Screen" app icon | Yes (needs HTTPS). | Only with the trusted certificate. |

This plan is written for **A**. Option B would replace items M1 and M7 with a network bind and certificate setup, and keep everything else.

### 2.2 What the phone may do

The proposed split is in section 4.3. In short, the phone can do the daily work: review, decide, approve, send by mail app, and ask the AI. It can't change connections, secrets, backups, exports or appearance-wide settings. Confirm or adjust the table before M3.

## 3. Architecture

```
 Phone browser
     │  https://ens-pc.tailnet.ts.net        (Tailscale: WireGuard + real TLS)
     ▼
 tailscale serve  (on the PC)
     │  http://127.0.0.1:8770                (loopback only, fixed port)
     ▼
 ┌───────────────────────── backend process ─────────────────────────┐
 │  Phone gateway app            │  Desktop app (unchanged)           │
 │  · serves the built frontend  │  · 127.0.0.1:<ephemeral>           │
 │  · paired-phone cookie auth   │  · per-run session token           │
 │  · Host + Origin checks       │  · Tauri CORS origins              │
 │  · route policy (4.3)         │                                    │
 │            └──────── same services, database, jobs, Ollama ───────┘│
 └────────────────────────────────────────────────────────────────────┘
```

- **One process, two listeners.** `cli.py` runs a second `uvicorn.Server` beside the first, only when phone access is switched on. The gateway is a second FastAPI app built from the same routers. It shares `app.state` (database, job manager, assistant managers), so there's one scheduler and one database writer.
- **Auth is swapped, not duplicated.** The gateway sets `dependency_overrides[require_session_token] = require_paired_device`. Every route that is `Authenticated` today becomes phone-authenticated on the gateway with no edits to the route.
- **Same origin.** The gateway serves `apps/frontend/dist` at `/` and the API at `/api/v1`, so the phone needs no CORS and the session cookie can be `SameSite=Strict`.
- **The PC must be on, awake and running the app.** The phone shows a clear "Your PC isn't reachable" screen otherwise. The runbook covers Windows sleep settings.
- **The AI still runs on the PC.** Ollama stays on loopback. LightBurn/xTool protection still applies. The phone just waits for the answer.

## 4. Security design

### 4.1 Pairing a phone

1. Desktop: Settings → Connections → Phone access → **Pair a phone**. The backend creates a one-time code (8 characters, no look-alike letters), valid for 5 minutes. The screen shows it as a QR code and as text.
2. The QR code opens `https://<pc>.ts.net/pair#ABCD-2345`. The code is in the `#` part, so it's never sent in a URL, logged, or kept in history as a request.
3. The phone asks for a name ("Malek's iPhone", pre-filled from the browser) and posts the code once.
4. The backend issues a device ID and a 256-bit secret, stores only its SHA-256 hash, and sets the cookie: `ens_device`, `HttpOnly; Secure; SameSite=Strict; Path=/api`, valid for 30 days and renewed on use.
5. Five wrong codes cancel the pairing; codes are compared in constant time.

### 4.2 Every request from the phone

- **Device cookie** must match a paired, unrevoked device (constant-time compare against the hash).
- **Host header** must be the configured `*.ts.net` name (`TrustedHostMiddleware`), which blocks DNS-rebinding pages.
- **Changes** (POST/PUT/PATCH/DELETE) must carry `Origin` equal to the gateway origin and an `X-ENS-Request: 1` header, as a CSRF guard on top of `SameSite=Strict`.
- **Optional second check:** `tailscale serve` adds `Tailscale-User-Login`. The gateway can require it to match the operator's login. It's forgeable by a local process, so it complements the cookie rather than replacing it.
- **Headers:** a strict content-security policy (self only, no inline script), `Cache-Control: no-store` on all API responses, and the existing `nosniff` and `no-referrer`.

### 4.3 What the phone may call

Routes get one new marker, `DesktopOnly`, a dependency that does nothing on the desktop app and returns `403 DESKTOP_ONLY` ("Do this on your PC") on the gateway.

| Area | Phone | Notes |
|---|---|---|
| Today, summary, jobs status | ✅ | |
| Leads: list, detail, stage moves, notes, follow-ups, holds | ✅ | Suppression and reason prompts are unchanged, enforced server-side. |
| Shortlist: accept, skip, defer, replace | ✅ | |
| Email drafts: edit, approve, reject, reopen, open in mail, confirm sent | ✅ | `mailto:` opens the phone's mail app (set Zoho Mail as default). |
| AI assistant and lead assistant, including attachments | ✅ | Same size limits. Photos from the phone are attachments. |
| Campaigns: view, run, edit weekly settings | ✅ | Creating a campaign is allowed; the stepper already fits a phone. |
| Catalogue and templates | 👁 read only | Editing long texts on a phone invites mistakes; revisit later. |
| Lead export (CSV) | ❌ | Puts personal data on the phone. |
| Backups, verify, restore | ❌ | |
| Connections: Meta, Google Places, cloud polish keys | ❌ | Meta OAuth's callback is loopback-only anyway. |
| Workspace settings, diagnostics, shutdown | ❌ | |
| Phone access itself (pair, revoke, switch off) | ❌ | A lost phone must not be able to keep itself paired. |

### 4.4 Control and record

- **Off by default.** Turning it off stops the gateway listener immediately; paired phones stay listed but can't connect.
- **Devices list** in Settings: name, paired, last seen, **Revoke** (immediate). Revoking all is one button.
- **Audit:** actions from a phone record `channel = phone` and the device ID in the existing audit trail, which shows "from Malek's iPhone" in lead history. No IP addresses or user agents are stored beyond a short browser/OS label.
- **Logs:** structured events with IDs and kinds only: `mobile_gateway_started`, `mobile_gateway_stopped`, `mobile_pairing_code_issued`, `mobile_pairing_succeeded`, `mobile_pairing_failed` (with attempt count), `mobile_device_revoked`, `mobile_request_rejected` (with reason: `host`, `origin`, `device`, `desktop_only`). Never the code, cookie or secret.

## 5. Mobile layout

### 5.1 Shell

Phone layout applies below 600 px wide (today's 900 px top-bar layout stays for narrow desktop windows and tablets).

- **Header (52 px):** logo, the current screen's title, search icon (opens the Ctrl+K palette full-screen), and a dot showing the PC connection.
- **Bottom tab bar:** Today · Shortlist · Pipeline · Drafts · More. Gold badges show work that needs you, same rules as the sidebar. **More** opens a sheet with Campaigns, All leads, Catalogue, Templates, Settings.
- **AI button:** sits above the tab bar, bottom-right. The assistant opens full-screen, with the input pinned above the keyboard.
- **Drawers become full-screen sheets** with a back arrow and the action buttons pinned to the bottom.
- **Tables become card lists:** name, status pill, one key fact, one primary action. Pagination becomes "Load more".
- **Touch:** 44 px minimum targets, 16 px inputs (so iOS doesn't zoom), safe-area padding for notches and the home bar, no hover-only controls. Swipes are shortcuts only, never the only way to do something.
- **Installable:** a web app manifest and icons, so "Add to Home Screen" opens it like an app without the browser bar. No service worker caching of data: nothing about leads is kept on the phone.

### 5.2 Screens

```
┌─────────────────────────┐ ┌─────────────────────────┐ ┌─────────────────────────┐
│ ◆  Today          ⌕  ●  │ │ ←  Draft 3 of 12     ⋯  │ │ ←  Bramble Café      ⋯  │
├─────────────────────────┤ ├─────────────────────────┤ ├─────────────────────────┤
│ Good morning, Malek     │ │ To  hello@bramble.cafe  │ │ Qualified · Score 82    │
│                         │ │ Re  Engraved coasters   │ │ Next: follow up today   │
│ ┌─────────────────────┐ │ │─────────────────────────│ │─────────────────────────│
│ │ ● 4 drafts to       │ │ │ Hi Sam,                 │ │ [Details][Notes][History│
│ │   approve      Open›│ │ │ I noticed your new      │ │                         │
│ └─────────────────────┘ │ │ brunch menu…            │ │ ✆ 01234 567890      Call│
│ ┌─────────────────────┐ │ │                         │ │ ✉ hello@bramble…   Email│
│ │ ● 2 follow-ups due  │ │ │                         │ │ ◎ @bramblecafe          │
│ │   today        Open›│ │ │                         │ │                         │
│ └─────────────────────┘ │ │                         │ │ Why it scored           │
│ ┌─────────────────────┐ │ │                         │ │ [Public email][Café]    │
│ │ ● Shortlist ready   │ │ │                         │ │                         │
│ │   (10)         Open›│ │ ├─────────────────────────┤ ├─────────────────────────┤
│ └─────────────────────┘ │ │ [ Reject ] [ Approve ✓ ]│ │ [ Move to… ] [Follow-up]│
│                    (✦)  │ └─────────────────────────┘ └─────────────────────────┘
├─────────────────────────┤      Drafts: one at a time,       Lead: summary strip,
│ ⌂    ☆    ▤    ✉²   ⋯  │      actions pinned to thumb      tap-to-call / email
└─────────────────────────┘
```

| Screen | Phone behaviour |
|---|---|
| **Today** | Action cards stacked in priority order; funnel and totals collapse under "This week". |
| **Shortlist** | One card per lead, Accept and Skip as two large buttons; More menu holds Defer and Replace. |
| **Pipeline** | Stage chips across the top (scrollable) and a card list underneath, instead of the board. "Move to…" on each card. Drag-and-drop is off on touch. |
| **Lead detail** | Full-screen. Summary strip, tabs, tap-to-call and tap-to-email, privacy and audit collapsed. |
| **Email drafts** | List → one draft at a time with "3 of 12". Approve/Reject pinned at the bottom. After **Open in mail**, the app shows "Did you send it?" with **Yes, sent** / **Not yet** when you come back. |
| **AI assistant** | Full-screen chat. Context chip shows the lead it was opened from. Attach a photo from the camera roll. |
| **Campaigns** | List of cards with Run and status. The create stepper is one step per screen. |
| **Settings** | Appearance (theme, density for this phone) and "Signed in as Malek's iPhone · Sign out this phone". Everything else shows "Manage this on your PC". |

## 6. Delivery

Gates per item: Ruff, mypy and pytest for backend items; TypeScript, ESLint (zero warnings) and Vitest for frontend items; Rust check for host items. `npm.cmd run quality` at each phase boundary. Each item gets a `DELIVERY_LOG.md` entry; user-visible changes go in `CHANGELOG.md`. Screenshots for the visual check stay in the scratchpad, never in the repo.

### Phase M0: Decision record

- **M0. ADR-025 "Phone access through a loopback gateway".** It records the decision in 2.1, why ADR-015 still holds (no non-loopback bind), the route policy and pairing model. It updates `SECURITY_MODEL.md` (new threats: lost phone, stolen cookie, rebinding, CSRF) and `CONTROL_REGISTER.md`. *Size: S.*

### Phase M1: Backend gateway

- **M1. Second listener.** Adds the settings `mobile_access_enabled` (default off), `mobile_gateway_port` (default 8770, loopback only, same validator as `host`) and `mobile_public_host` (`*.ts.net` name). `cli.py` runs both servers in one event loop; turning the setting on or off starts or stops the gateway without restarting the desktop listener. Tests: the gateway refuses to start with a non-loopback host; stopping it leaves the desktop API up. *Size: M.*
- **M2. Paired devices.** A migration adds `mobile_devices` (id, name, label, secret_hash, created_at, last_seen_at, revoked_at) and `mobile_pairing_codes` (hash, expires_at, attempts). Adds a pairing service, `require_paired_device`, desktop-only routes to issue a code, list devices and revoke one or all, and a gateway-only `POST /mobile/pair` plus `POST /mobile/sign-out`. Tests: expiry, single use, five-attempt lockout, revoked device rejected, secret never in any response or log. *Size: M.*
- **M3. Route policy.** Adds the `DesktopOnly` dependency on each ❌ route in 4.3, and read-only enforcement for catalogue and template writes. One table-driven test walks every registered route on the gateway and asserts the expected outcome, so a new route can't slip through unclassified. *Size: M.*
- **M4. Gateway hardening.** Trusted Host, Origin and `X-ENS-Request` checks; CSP, `no-store` and security headers; static serving of the built frontend with an SPA fallback; the optional Tailscale login check. Tests for each rejection reason. *Size: S.*
- **M5. Audit and logs.** Adds `channel` and `device_id` on audit events from the gateway, the lead-history wording, and the structured log events in 4.4. *Size: S.*

### Phase M2: Desktop controls

- **M6. Settings → Connections → Phone access.** Adds a status card in the D7 style ("Off", "On · 1 phone paired", "Needs attention: Tailscale not found"), the on/off switch, **Pair a phone** with a QR code and a countdown, and the devices list with Revoke and Revoke all. Tailscale is detected by running `tailscale status --json` (read-only); the address is filled in from it. *Size: M.*
- **M7. Tailscale setup helper.** A "Set up" button runs `tailscale serve --bg --https=443 http://127.0.0.1:8770` after confirming, and "Turn off" runs `tailscale serve reset` for that path. This lives in the backend's system service with a fixed command line, never user-supplied arguments. If Tailscale isn't installed, it links to the install page instead. *Size: S.*

### Phase M3: Phone connection in the frontend

- **M8. Third connection mode in `api.ts`.** If it isn't Tauri and isn't the Vite dev env, the frontend asks `/api/v1/mobile/session`. Requests are same-origin with the cookie and the `X-ENS-Request` header, and there's no session token. A 401 shows the pairing screen and a network failure shows "Your PC isn't reachable". `openUrl` already falls back to `window.open`, which handles `mailto:` on phones. Tests mirror the existing desktop-mode tests. *Size: S.*
- **M9. Pairing and sign-out screens.** Reads the code from the URL fragment, the name field, and clear errors (expired, already used, too many tries). Settings on the phone gets "Sign out this phone". The UI hides ❌ features on the phone instead of letting them fail; `DESKTOP_ONLY` errors still show "Do this on your PC" as a safety net. *Size: S.*

### Phase M4: Phone layout

- **M10. Shell.** Adds the `PHONE_QUERY` (max-width 599 px) in `layout.ts`, the bottom tab bar with badges and the More sheet, the header, safe areas, the AI button above the tabs, and full-screen sheets in place of drawers (`Drawer` gets a phone variant). *Size: M.*
- **M11. Card lists.** A shared `ResponsiveList` renders rows as cards on phones (All leads, Campaigns, Templates, Catalogue) and gets "Load more" pagination. *Size: M.*
- **M12. Today and Shortlist.** *Size: S.*
- **M13. Pipeline and lead detail.** Stage chips, card list, "Move to…", the full-screen lead, tap-to-call and tap-to-email, and drag turned off on touch. *Size: M.*
- **M14. Email drafts.** List → single draft, pinned Approve/Reject, and the "Did you send it?" prompt on return (`visibilitychange`). *Size: M.*
- **M15. Assistant and search.** Full-screen assistant with a keyboard-safe input, camera-roll attachment, and the full-screen search palette. *Size: S.*
- **M15a. Answers survive a locked phone.** `POST /assistant/conversations/{id}/messages` holds the request open until the local model replies, which can take up to 120 s. A phone that locks its screen or switches apps in that time drops the request, but the PC keeps working. First check that the backend saves the question before calling the model and the answer after. Then the frontend shows "Still thinking on your PC…" and reloads the conversation when the page becomes visible again or the request fails with a network error. It does not resend, so you never get a duplicate question. Applies to the lead briefing too. *Size: S.*
- **M16. Installable app.** Manifest, icons (from `app-icon.svg`), theme colours for light and dark, and the iOS meta tags. No service worker. *Size: S.*

### Phase M5: Check and hand over

- **M17. Verification.** `agent-browser` screenshots every phone screen at 390×844 (iPhone) and 360×780 (Android), in light and dark, against a throwaway database. Then a real-phone run over Tailscale: pair, approve and send a draft through the mail app, confirm sent, revoke, and confirm the revoked phone is locked out. A keyboard and screen-reader pass covers the bottom bar and sheets. *Size: M.*
- **M18. Runbook.** `docs/operations/MOBILE_ACCESS.md`: install Tailscale on both, switch on, pair, keep the PC awake (Windows power settings), what to do if a phone is lost (Revoke, then optionally `tailscale logout` that device), and turning it all off. *Size: S.*

## 7. Risks

| Risk | Mitigation |
|---|---|
| Lost or stolen phone | The phone's own lock screen; Revoke from the PC; 30-day expiry; the phone can't touch secrets, exports or backups. |
| Gateway route added later without thinking about phones | The M3 route-walk test fails until the route is classified. |
| PC asleep, so the phone can't connect | A clear "PC isn't reachable" screen; power settings in the runbook. |
| AI answers slow on the phone | Same model and limits as the desktop; the existing "thinking" state; protection mode still yields to LightBurn/xTool. |
| Tailscale account compromise | Device cookie still required; optional login check (4.2); Tailscale's own 2FA recommended in the runbook. |
| Layout regressions on desktop | Phone styles live under the phone query only; desktop screenshots at 1366×768 and 720×600 are re-taken in M17. |

## 8. Order and size

Eighteen items over five phases. M0 to M9 make the phone *work*, on the existing narrow layout. M10 to M16 make it *pleasant*. If the plan is approved, the natural first stopping point is after M9: the phone can pair and do the daily work, before any layout effort.
