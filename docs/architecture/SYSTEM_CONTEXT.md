# System context

**Status:** Implemented local core, operator-triggered Google and official Instagram boundaries, plus assisted social capture; AI and messaging disabled  
**Updated:** 19 July 2026

## Purpose and boundary

Etch ’N’ Shine Lead Generation is a single-operator, local-first Windows workbench for evidence-backed prospecting. It stores campaign and lead research, preserves source observations, and keeps the operator in control. It is not a scraper, bulk-mailer, autonomous sales agent, CRM replacement, or legal decision engine.

```text
Local operator
    │ keyboard/mouse
    ▼
Tauri desktop host ── IPC bootstrap ──► React workbench
    │ starts/stops                         │ authenticated HTTP
    ▼                                     ▼
Packaged FastAPI service on 127.0.0.1:<ephemeral port>
    │
    ├── SQLite/Alembic database in local AppData
    ├── rotating redacted local logs
    ├── operator-selected backup directory
    ├── user-scoped DPAPI provider vault
    └── optional Google Places/Geocoding and Meta Graph HTTPS calls

Optional controlled boundaries:
Google Places/Text Search → staged candidates → bounded public-site enrichment
Instagram hashtag link → operator selects profile URL → Business Discovery → staged candidate
Saved Instagram handles → bulk Business Discovery refresh → existing canonical leads
Public Facebook search → operator verification → assisted capture

Future, disabled boundaries:
AI provider │ Zoho draft sync │ approved email/social hand-off
```

The Tauri host owns the backend process, chooses an available loopback port, generates a random per-session token, passes connection details to the webview over a narrow IPC command, and terminates the child on exit. The webview cannot choose a backend command or bind address.

## Current external dependencies

The existing-lead/scoring and assisted-social capture workflows require no provider credentials. Assisted social search opens normal public Google searches and only stores information the operator verifies and submits. Google discovery uses an environment-provided backend key. Instagram discovery uses an explicit Meta OAuth connection protected by Windows DPAPI, a loopback callback and per-campaign selection. Both official providers are bounded, operator-triggered and fail closed without blocking existing-lead scoring. WebView2 is a Windows runtime dependency; build tools retrieve locked packages.

## Data locations

- Production default: `%LOCALAPPDATA%\EtchNShine\LeadGeneration\ens-leads.db`
- Logs: `%LOCALAPPDATA%\EtchNShine\LeadGeneration\logs`
- Build cache: `%LOCALAPPDATA%\EtchNShine\Build\cargo-target`
- Backups: an operator-selected directory; never the active database path

The source repository may be in Dropbox, but runtime data deliberately is not.

## Trust and release status

The local operating slice is verified. The generated NSIS installer is unsigned and intended for development/pilot evaluation only. No production outreach is authorised until the compliance and security gates in `CONTROL_REGISTER.md` are closed.
