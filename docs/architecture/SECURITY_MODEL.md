# Security model

**Status:** Local-core and encrypted Meta credential controls implemented; outbound-feature controls pending  
**Updated:** 19 July 2026

## Assets and trust boundaries

Protected assets are prospect research, source evidence, classifications, future contact details, credentials, drafts, audit history, backups, and provider budgets. Boundaries exist between the webview and native host, local API and other local processes, application and filesystem, application and future providers, and backup data and its destination.

## Implemented controls

| Threat | Control | Evidence |
|---|---|---|
| Network exposure | Settings reject any host except literal `127.0.0.1`; desktop selects an ephemeral port | Settings and API tests; Rust lifecycle test |
| Other local process calls API | Random per-run token required with constant-time comparison | Authentication tests and packaged smoke test |
| Cross-origin web access | Explicit CORS origin allowlist, no credentials, restricted methods/headers | App configuration/test |
| Injection/invalid state | Strict typed request models, forbidden extra fields, domain/database constraints | Invalid-input tests |
| Information leakage | Stable safe errors, generated correlation IDs, disabled Swagger/ReDoc, no server header | API tests/manual review |
| Unsafe webview content | Tauri content-security policy; React renders text, not raw HTML | Tauri config/frontend review |
| Corrupt/inconsistent backup | SQLite backup API, `integrity_check`, SHA-256 manifest, atomic rename | Backup/restore tests |
| Data loss during restore | Live database restore blocked; isolated restore requires explicit replacement | Backup service tests |
| Secret disclosure | Meta App secret and OAuth tokens use a current-user DPAPI vault; no secret response fields, browser storage or SQLite values; generated session secret is not logged | DPAPI/API tests and manual secret scan |
| OAuth interception/forgery | Fixed HTTP callback binds only to `127.0.0.1`; exact redirect URI, random one-time state and ten-minute expiry; no token in browser URL after exchange | Meta connection service tests |

Runtime data is stored in local AppData, not the synchronised source tree. Logs contain operational messages and correlation IDs; session tokens and request payloads are not logged. Audit summaries deliberately avoid raw evidence payloads.

## Controls required before enabling later features

- Provider revocation confirmation and token-expiry/reauthorisation operational review beyond the implemented DPAPI disconnect/remove controls.
- URL canonicalisation, DNS/IP validation before and after redirects, private/link-local/loopback denial, scheme/port allowlists, size/time limits, safe MIME handling, and same-domain crawl bounds.
- CSV formula neutralisation, row/size/encoding limits, mapping preview, and per-row error reports.
- Provider scope minimisation, timeouts, retry limits, circuit breakers, daily/weekly budgets, consented terms, and kill switches.
- AI minimisation, schema validation, evidence-ID validation, prompt-injection resistance, prohibited-claim checks, and model/prompt/input audit metadata.
- Suppression as a hard server-side invariant at every selection, drafting, approval, and send boundary.
- Signed release artefacts and a clean-profile Windows installation test.

Official, operator-triggered Instagram profile lookup is authorised only for the professional-account path in ADR-016. The Meta OAuth request is limited to Page listing, Page read access and basic Instagram access. Instagram messaging, publishing, comments, insights, advertising, business administration, automated browser activity, AI, Zoho and autonomous sending remain disabled.

## Incident handling

Stop the application, preserve logs and relevant backup manifests, rotate any affected external credential through its provider, and record correlation IDs and times. Do not place personal data, credentials, or exploit details in a public issue. Recovery must use a verified backup and the runbook in `BACKUP_AND_RESTORE.md`.
