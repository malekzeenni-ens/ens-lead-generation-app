# Delivery log

## 18 July 2026 — Kickoff and increment 1

### Inputs and baseline

- Read the BRD/FSD, solution-architect review prompt, approved architecture assessment, implementation kickoff, and universal application design system in full.
- Confirmed a documentation-only clean baseline, recorded the BRD/FSD filename mismatch, and initialised Git.
- Added the implementation plan, live traceability matrix, fifteen ADRs, architecture/security/data/job/integration documentation, operations runbooks, test strategy, pilot report, and compliance register.

### Delivered slice

- Created a Tauri 2 Windows lifecycle host, React/TypeScript/Vite interface, FastAPI/Python modular monolith, and SQLAlchemy/Alembic/SQLite persistence.
- Implemented loopback-only startup, ephemeral port, random per-session token, restricted CORS/CSP, safe correlated errors, rotating local logs, and local AppData paths.
- Implemented campaign create/list/detail and manual lead create/list/detail with contact classification, exact duplicate review, campaign membership, separate source observation, initial stage event, and append-only audit event.
- Implemented SQLite-native backup, integrity/checksum manifest, verification, and isolated restore with active-database protection.
- Aligned the UI with the central Etch ’N’ Shine navy/slate/off-white/champagne token, typography, spacing, control, focus, error, loading, warning, and reduced-motion rules.
- Added locked Python/npm dependencies, local consolidated quality script, Windows CI workflow, PyInstaller sidecar build/smoke, and Tauri NSIS build/release smoke.
- Routed generated Cargo and frontend coverage outputs to local AppData so repeated gates remain reliable from a Dropbox-synchronised repository.

### Verification

- Ruff check and format check: pass.
- Strict mypy: pass.
- Pytest: 7 passed; 90% Python statement coverage.
- ESLint and TypeScript: pass.
- Vitest: 3 passed; 69.95% aggregate frontend coverage.
- Frontend production build: pass.
- rustfmt, Cargo test, and Clippy with warnings denied: pass; lifecycle test passed.
- npm high-severity audit: 0 vulnerabilities.
- Standalone PyInstaller sidecar smoke: pass on `127.0.0.1`, database created and child cleaned up.
- Tauri NSIS build: pass.
- Exact release host `--smoke-test`: pass; bundled backend served authenticated health and stopped cleanly.
- Installer: `Etch N Shine Lead Generation_0.1.0_x64-setup.exe`, 21,671,018 bytes, SHA-256 `73A335705AD2CC4FE7E5EAD27AD4B679C376E7283AC3C9F4E9C6427E33091468`.

### Scope and residual risks

External Google/Meta/website/AI/Zoho adapters and all outbound communication remain absent. Stage 1 still needs CSV, fuller pipeline, notes, follow-ups, suppression, export, settings/diagnostics, and demo data. SSRF, AI validation, Windows credential vault, durable jobs, provider budgets, legal/privacy sign-off, code signing, automated visual-diff/extended zoom review, and clean-profile installer/upgrade/uninstall testing remain explicit gates.

Rollback for this greenfield increment is removal of the new source and disposable test artefacts. No pre-existing application code or user database was overwritten.

## 18 July 2026 — Universal design-system application

- Replaced the centred form presentation with the documented desktop management shell: application header, 240px sidebar, overview hierarchy, workflow strip, metrics, structured work panels, operational lead table and status bar.
- Added reusable React design-system primitives and Lucide as the single icon family; regenerated desktop icons in deep navy, off-white and champagne gold.
- Added explicit loading, success toast, actionable error, empty, disabled, warning and connection states while preserving campaign/lead API payloads and defaults.
- Added skip-link focus transfer, a single landmark sequence, visible focus, reduced-motion behaviour, non-colour status labels and compact table-card conversion.
- Browser-tested the real disposable local campaign-to-lead flow. Verified no horizontal overflow at 720×600, 1366×768, 1440×900, 1920×1080 or 2560×1440. Local development vitals: TTFB 13.2ms, FCP/LCP 328ms and CLS 0.
- Added visual-review evidence and raised frontend coverage to 69.95%. No production database or external provider was used.

## 18 July 2026 — Stage 1 local operations

### Delivered

- Added campaign search, edit, pause/resume and duplication with audit history.
- Added lead search/filter/edit and the complete required pipeline with stage history, opportunity values, lost reasons, and mock-up/sample/quote statuses.
- Added local notes, dated typed follow-ups, completion, manual communication records, sent confirmation, reply outcomes and chronological activity timelines.
- Added suppression/lift controls. Active suppression now forces Do Not Contact, cancels open follow-ups, and blocks stage movement, new follow-ups and sent communication records.
- Added privacy deletion of the personal lead graph while retaining only minimised active suppression evidence.
- Added authenticated JSON/CSV export with full lead activity and spreadsheet-formula protection.
- Added settings, dashboard summary, diagnostics, and backup create/verify workspaces.
- Added schema revision `0002_local_crm` and updated architecture, traceability, setup and test documentation.

CSV import was intentionally skipped by user direction. External providers, AI, automated work, and outbound sending remain disabled.

### Verification

- Ruff and strict mypy: pass.
- Pytest: 11 passed; 93% Python statement coverage.
- ESLint and strict TypeScript: pass.
- Vitest/Testing Library: 7 passed; 68.23% aggregate coverage across the expanded UI.
- Frontend production build: pass.
- Real browser workflow: pass against a disposable database, including campaign/lead/pipeline/follow-up/manual communication/settings/export/backup/suppression paths.
- Responsive review: 1366×768 and 720×600, no horizontal overflow and no application console errors.

The browser review identified and corrected workspace scroll restoration. This increment changed source, migrations, tests and documentation only; no installer was rebuilt.

## 19 July 2026 — Stage 2 qualification slice

### Delivered

- Added schema revision `0003_qualification` with products, versioned scoring profiles/runs, weekly shortlists and shortlist decisions.
- Added an editable product catalogue and a browser file interface for Shopify listing CSV exports. Imports enforce 5 MB / 10,000-row limits, require Shopify Handle/Title headers, collapse variants, upsert by handle and do not retain the raw file.
- Added deterministic bakery scoring with seven configurable categories, immutable profile versions, visible awarded/evidence/missing explanations, explicit no-AI status and manual override reasons.
- Added deterministic product matching with visible rule/evidence explanations and score/shortlist snapshots.
- Added capacity-aware weekly shortlists with score, product, local/contact, freshness, pipeline, history and suppression controls plus approve/defer/dismiss/replace decisions.
- Added campaign create/edit controls for product categories and the minimum shortlist score, including category de-duplication and immediate propagation into weekly shortlist configuration.
- Corrected desktop development startup so Cargo uses the Local AppData build cache and debug mode starts the current source backend rather than an older bundled sidecar.
- Added catalogue file-readiness/import-progress feedback and verified the supplied 589 KB Shopify export through the actual Tauri WebView: 840 rows, 123 products, zero skips, under one second; repeat upload updated all 123 without duplication.
- Added shared accessible pagination to every unbounded operating register: catalogue/import issues, campaigns, leads, weekly recommendations, pipeline lead selection, open follow-ups and activity history. Catalogue pages are limited to eight cards and long descriptions use a four-line preview.
- Integrated active-product, scored-lead and shortlist state into the dashboard and lead pipeline. No shortlist action sends a message.
- Extended suppression so it immediately suppresses a recommended/approved shortlist item and removes it from the active operating queue.

### Verification

- Consolidated quality command: pass, including npm high-severity audit with 0 vulnerabilities.
- Ruff format/check and strict mypy: pass across 54 Python source files.
- Pytest: 14 passed; 92% Python statement coverage.
- ESLint, strict TypeScript and production build: pass.
- Vitest/Testing Library: 13 passed; 71.17% aggregate frontend statement coverage.
- Rust lifecycle test, rustfmt and Clippy with warnings denied: pass.
- Real-browser disposable workflow: Shopify upload created two products from three variant rows; all three leads received explained scores and rule-based product matches; a three-lead shortlist was generated; approve and defer decisions persisted; suppression removed the affected lead and blocked outreach actions.
- Real-browser campaign-control workflow: create persisted a 65/100 minimum with de-duplicated categories, edit persisted 70/100 with revised categories, and the shortlist screen reflected the new threshold immediately.
- Responsive review: 1366×768 and 720×600, no page-level horizontal overflow and no application console errors. Evidence is in `docs/testing/STAGE2_QUALIFICATION_REVIEW.md` and the `stage2-*` screenshots.

Lead CSV import, external discovery/providers, AI inference, Shopify API sync, outbound sending and installer generation remain outside this increment. No installer was built.

High-volume pagination review used disposable data only: 123 products, 12 campaigns, 15 leads/recommendations, seven follow-ups and 23 activity events stayed within their configured page sizes; filter reset, selected-lead page retention, keyboard transitions and responsive overflow checks passed.

## 19 July 2026 — Operator-triggered automation and controlled discovery

### Delivered

- Added schema revision `0004_campaign_automation` with durable campaign runs, staged discovery candidates, provider attempts, score-run lineage and input fingerprints.
- Added per-campaign **Refresh scoring** and **Run all active campaigns** controls. Each run executes discovery when configured, bulk deterministic scoring/product matching for every eligible campaign lead, and current-week shortlist preparation.
- Added unchanged-input score reuse and protected existing current-week shortlists from replacement.
- Added the optional official Google Places Text Search (New) and Geocoding v4 adapter with query/result caps, selected fields, exact Haversine radius filtering, safe provider attempts and fail-closed missing-key/provider-error behavior.
- Added public-homepage enrichment with public-address DNS validation, redirect revalidation, robots policy, content-type/size/time limits and no raw HTML retention.
- Added provider-ID/website/name duplicate resolution, suppression checks, staged fuzzy duplicate review, and audited link/promote/reject decisions.
- Added run history, phase/status, metrics, warnings, cancellation and paginated duplicate-review controls to the Campaigns workspace. AI and outbound messaging remain disabled.

### Verification

- Ruff, strict mypy, ESLint and strict TypeScript: pass.

- Pytest: 19 passed, including bulk scoring/idempotency, all-active filtering, provider radius, staged promotion/link/review, candidate decision and SSRF blocking paths.
- Vitest/Testing Library: 14 passed; production frontend build passed.
- Real-browser disposable workflow: campaign creation and button-triggered run completed with durable status, counters and warning; no console/page errors.
- Responsive review: 1366×768 and 720×600 had zero document-level horizontal overflow.

External discovery was not called during browser acceptance because no real provider credential was supplied. Provider behavior was verified with an HTTP contract transport. No user database, AI service, outbound message or installer was used.

## 19 July 2026 — Contact enrichment and assisted social discovery

### Delivered

- Added schema revision `0005_contact_social`: canonical phone/public-email fields plus unique per-platform social identities with source and collection evidence.
- Persisted Google Places phone numbers on promoted or previously linked leads, including international numbers when supplied by Places API (New).
- Expanded safe website research to home plus at most two same-domain contact/about pages and extracts public emails, public phones and Instagram/Facebook links without retaining HTML.
- Strengthened cross-run and cross-source duplicate resolution using final provider records, social handles, website hosts, phone numbers, public emails and exact normalised business names. Ambiguous fuzzy names still require operator review.
- Added campaign-generated Instagram/Facebook public searches and an operator-assisted capture form. Capture triggers duplicate resolution, deterministic scoring, catalogue product matching and shortlist eligibility immediately; no Meta login, scraping or automated messaging is used.
- Added phone/email/social fields to manual lead entry, the lead register, pipeline detail editing and exports.

### Verification

- Ruff and strict mypy: pass.
- Pytest: 21 passed, including Google phone persistence, repeat-run deduplication, repeat social-profile deduplication, automatic social qualification and bounded contact-page enrichment.
- ESLint, strict TypeScript and production frontend build: pass.
- Vitest/Testing Library: 15 passed, including assisted Instagram capture payload and workflow.
- Real-browser disposable workflow: campaign creation, social capture, canonical phone/email display, immediate scoring/shortlisting and repeat capture linking were exercised; the lead count remained one.

No user database, real Google/Meta request, AI inference, outbound message or installer was used for this acceptance run.

## 19 July 2026 — Official Instagram discovery foundation

### Delivered

- Added current-user Windows DPAPI storage for Meta App credentials and OAuth tokens; secret values are not returned to the frontend or stored in SQLite.
- Added Facebook OAuth with a one-time state, ten-minute authorization window and fixed loopback-only callback at `http://127.0.0.1:8766/meta/oauth/callback` while retaining the desktop backend's collision-resistant ephemeral API port.
- Added Page/Instagram professional-account resolution, multiple-account selection, connection/disconnect/remove controls and automatic UI status polling.
- Added bounded location-and-sector Instagram hashtag discovery plus Business Discovery for accessible professional accounts using the official Meta Graph API and `appsecret_proof`.
- Added public bio contact extraction, safe website enrichment, stable Meta ID/social-handle deduplication and the existing deterministic scoring, product-matching and shortlist pipeline.
- Added per-campaign Instagram source controls, provider status/run attempts and assisted social fallback. Browser scraping and Instagram messaging remain disabled.

### Verification

- Ruff and strict mypy: pass.
- Pytest: 25 passed, including DPAPI non-disclosure, OAuth token/account exchange, official Instagram provider mapping/contact extraction and repeat-run deduplication.
- ESLint and strict TypeScript: pass.
- Vitest/Testing Library: 17 passed without coverage cleanup; production frontend build and Rust checks remain part of the final workspace quality run.
- No real Meta token, user database, outbound message or installer was used by the automated tests.

## 20 July 2026 — Resilient desktop relaunch

### Delivered

- Added a guarded port-1420 preflight to the desktop development launcher.
- Double-clicking while the desktop app is running now selects the existing window instead of starting a conflicting Vite process.
- A verified orphaned Etch N Shine Vite process is removed automatically; an unrelated port owner is preserved and reported by name and process ID.
- Updated launcher and troubleshooting messages to describe the relaunch behaviour clearly.

### Verification

- Verified free-port startup, active-startup preservation, orphan cleanup and unrelated-process protection.
- Launched the complete Tauri/Vite/local-backend path and confirmed a responsive desktop process, Vite on `127.0.0.1:1420` and the loopback backend sidecar.
- Re-ran the launcher while the app was active; it selected the existing window and returned successfully.
- PowerShell parser and `git diff --check`: pass.

## 20 July 2026 — Lead workflow refinements

### Delivered

- Pipeline Overview now opens Lead details and retention by default.
- All leads now filters by campaign in addition to search, stage and contact status.
- Changing campaigns resets lead pagination to the first page.

### Verification

- Vitest/Testing Library: 20 passed, including default-open lead details and campaign filtering from page two.
- ESLint, strict TypeScript, production frontend build and `git diff --check`: pass.

## 20 July 2026 - Provider-specific campaign runs

### Delivered

- Split campaign automation into explicit **Run Google Places**, **Run Instagram**, and **Refresh scoring only** actions at both per-campaign and all-active levels.
- A new run calls exactly the selected discovery provider, then applies the shared deterministic scoring, product matching and shortlist phases. It never calls Google and Instagram together.
- All-active provider runs include only active campaigns that selected that provider. Scoring-only includes every active campaign and makes no external discovery request.
- Added provider labels to run history and guarded provider actions when credentials are unavailable or the campaign has not selected that source.
- Retained backward-compatible execution of historical queued combined runs. Facebook discovery remains an assisted Social Leads workflow until a dedicated official provider is implemented.

### Verification

- Backend application suite: 27 passed, including explicit provider isolation, provider-selection validation and all-active provider filtering.
- Frontend Vitest/Testing Library: 22 passed, including separate Google Places and Instagram action payloads.
- Ruff, strict mypy, ESLint and strict TypeScript: pass.

## 20 July 2026 - Lead provenance and assisted-search repair

### Delivered

- Added a **Lead source** column and source filter to All leads. Provenance badges distinguish Google Places, Instagram, Facebook and Manual capture; a lead can show multiple origins after cross-provider deduplication.
- Routed assisted Instagram/Facebook searches through the Tauri desktop URL opener and added the minimum Google Search URL permission required by those actions.
- Clarified that the fallback opens public searches for operator review and requires the selected profile to be entered through **Capture verified social lead**; it does not scrape or import browser results.
- Added explicit Instagram warnings for zero accessible profiles and for hashtag-based location matches that cannot be exact-radius verified.

### Verification

- Backend Instagram/campaign automation tests: 14 passed, including empty-result and radius-evidence messaging.
- Frontend Vitest/Testing Library: 24 passed, including lead-source filtering and desktop fallback browser opening.
- Ruff, strict mypy, ESLint, strict TypeScript, frontend production build and Rust Cargo check: pass.

## 20 July 2026 - Instagram professional-profile import and enrichment

### Delivered

- Replaced the misleading new-lead expectation around Meta hashtag media with the supported semi-automated workflow: direct campaign hashtag links, one pasted professional-profile URL, official Business Discovery preview, and explicit import.
- Added backend re-fetch on import, safe public bio contact extraction, bounded website enrichment, source evidence, stable Meta ID/social-handle deduplication, deterministic scoring, product matching and shortlist evaluation.
- Added campaign-level bulk enrichment for every Instagram profile already attached to a lead. Each unavailable consumer/private/misspelled profile remains visible as a named warning; successful profiles update or link the existing lead without duplication.
- Changed campaign **Refresh Instagram profiles** runs to enrich saved handles rather than claiming that hashtag results can automatically reveal new account owners.
- Split Social leads into focused **Instagram import**, **Find profiles**, and **Facebook capture** tabs, removing the large manual Instagram form while retaining separate Facebook capture.
- Updated Instagram operational and architecture documentation to state the verified Meta boundary accurately.

### Verification

- Backend application suite: 30 passed, including direct profile lookup, import, bulk enrichment, source evidence and repeat-safe saved-profile refresh.
- Frontend Vitest/Testing Library: 25 passed, including Meta preview/import, bulk enrichment and direct hashtag opening.
- Ruff, strict mypy, ESLint and strict TypeScript: pass.
- Read-only live Meta check: the configured connection resolved the known professional profile `@donmillersuk` through the new lookup method without exposing credentials.

## 20 July 2026 - Meta integration cleanup

### Delivered

- Removed the unused Meta hashtag-search and recent-media transport. Instagram discovery now has one supported path: operator-selected professional profiles followed by official Business Discovery lookup and repeat-safe import or refresh.
- Reduced future Meta authorization requests to `pages_show_list`, `pages_read_engagement` and `instagram_basic`.
- Removed the unused permissions-sync request and stored permission list from the connection status contract.
- Reduced Business Discovery profile fields to the data the lead workflow actually stores and displays.
- Preserved OAuth connection, token exchange, secure local token storage, account resolution, disconnect, profile preview/import and campaign profile refresh.

### Compatibility

- Existing Meta connections remain usable. The narrower authorization scopes apply the next time Meta is connected or reconnected.
