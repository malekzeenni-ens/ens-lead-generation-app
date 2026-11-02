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

## 29 September 2026 — Smarter catalogue answers

### Delivered

- Asked "what are the products", the assistant listed 12 products as if they were the range. It had been given the 12 ranked most relevant, and the 3B model ignored the product count beside them.
- `app/domains/assistant/catalogue_answers.py` answers whole-catalogue questions from the database: an overview by product group that asks what to show, then exact lists for "all", a group or a trade. These replies are stored as `app:catalogue`, shown as "From your catalogue", and make no model call. Anything needing judgement still goes to the model.
- The model snapshot leaves out Shopify add-on listings, replaces the Shopify category counts with `product_groups`, and adds `products_shown`; prompt `ens-assistant-v6` forbids presenting the sample as the full range.
- Eight product groups (`enrichment.PRODUCT_GROUPS`) with keyword derivation, and an optional `group` field in the knowledge pack. All 110 products in the operator's local pack were given a group; both local copies were updated, and neither is committed.

### Verification

- New `tests/test_catalogue_answers.py`: overview content and add-on exclusion, follow-up lists, model routing for questions needing judgement, no price in any catalogue answer, the model's sample fields and prompt rule, keyword grouping, and a pack `group` overriding the derived one.
- Tried against a copy of the operator's database: 103 products in 8 groups; café, gym and wedding trade lists; advice questions routed to the model.

### Delivered

- The operator's Desktop and Start Menu shortcuts open the installed build in `%LOCALAPPDATA%\Etch N Shine Lead Generation`, which dated from 22 July. Its bundled backend exited at startup with `Can't locate revision identified by '0014_backup_manifest_assistant_files'`, because development runs had migrated the shared database past the migrations it knew. The desktop host closed without showing why. The launch fix below was not the cause for the installed app; the stale build was.
- Rebuilt the NSIS installer from `f11f683` with `npm run desktop:build`: `artifacts/Etch N Shine Lead Generation_0.1.0_x64-setup.exe` (gitignored).
- Placed a copy of the knowledge pack beside the database in `%LOCALAPPDATA%\EtchNShine\LeadGeneration`, where the installed backend looks for it; the repository-root copy is only visible to development runs.

### Verification

- The newly bundled backend, run against a copy of the operator's database with the pack beside it, listened after about 3 s, applied migrations 0015 and 0016, applied the pack (104 matched, 10 notes, 4 fits) and returned 200 on every startup endpoint. The bundle contains the Anthropic SDK, `pack_autoload` and `cloud_client`.
- The real database is untouched until the operator installs and launches the new build.

### Follow-up

- Any future migration makes an older installed build crash the same way against a database a newer build has migrated. Rebuild and reinstall after a migration lands, or make the desktop host show the backend's startup error instead of exiting silently.

## 28 September 2026 — Desktop launch fix

### Delivered

- The desktop app closed on launch because the backend no longer started listening inside the host's 10-second window. Profiling showed `import app.main` at about 7.3 s, of which the Anthropic SDK was about 3.9 s; migrations (0.44 s) and the knowledge pack (0.41 s) were minor. The operator's database was also still two migrations behind, so a first start does extra work.
- `cloud_client.py` now imports the SDK inside `polish_with_anthropic`, and a test asserts that `import app.main` never loads it. Startup import time is about 2.6 s.
- `wait_for_backend` in `apps/desktop/src-tauri/src/lib.rs` now allows 30 seconds, since a cold start from a synced folder with pending migrations can exceed ten.

### Verification

- Launched `npm run desktop:dev` against an unmigrated copy of the operator's database: migrations ran, the pack applied (104 matched, 10 notes, 4 fits) and the window stayed up. The real database was not touched.
- Backend: 186 pytest tests, Ruff and mypy passed. Rust: `cargo fmt --check` and `cargo check` passed.

## 28 September 2026 — Cloud polish review fixes and automatic knowledge pack

### Delivered

- Fixed the review findings in cloud draft polish: the Settings form no longer throws after saving, a failed polish reports beside its own button, price checks block only a `£` amount, and the Anthropic SDK floor matches the API in use. See the review revision in `CLOUD_DRAFT_POLISH_HANDOVER.md`.
- The product knowledge pack now loads from disk (`app/domains/catalogue/pack_autoload.py`), so it no longer has to be uploaded by hand. It is found through `ENS_KNOWLEDGE_PACK_PATH`, beside the database, or at the repository root; applied at startup and after each Shopify import when the file or catalogue changed; and never applied over hand-written or AI-run product wording. A broken pack is logged and skipped. ADR-021 carries a dated amendment recording the reversal of "nothing reads it from disk".
- The test fixture switches the automatic load off so the operator's real pack cannot reach the suite; the pack stays gitignored.

### Verification

- Backend: 185 pytest tests passed, including 5 new loader tests and 6 new cloud polish tests; Ruff and mypy passed.
- Frontend: 112 Vitest tests passed; ESLint, `tsc -p tsconfig.app.json` and the production build passed.
- The operator's local pack was validated read-only against the strict parser (110 products, 10 notes, 4 proven fits). It is applied on the next backend start. No installer was rebuilt.

## 28 September 2026 — Optional cloud draft polish

### Delivered

- Implemented the bounded Anthropic rewrite flow specified in `docs/specifications/Cloud_Draft_Polish_Specification.md`: a separate polish endpoint rewrites only the subject/body currently in the editor and never edits the stored draft.
- Added the Anthropic SDK client, shared outreach task/brand voice prompt, fixed model allowlist, structured response/refusal handling, provider error mapping, and token/request metadata logging.
- Added the system cloud-polish status/configure/remove endpoints and DPAPI-backed `SecretStore` credential handling. Workspace settings default to disabled and select Sonnet 5 unless the operator chooses Haiku 4.5.
- Added price stripping and boundary checks around the outbound draft/context message and returned copy; audit events contain draft ID, model, prompt version, token counts and request ID, without copy or credentials.
- Added Settings controls and a conditional **Polish with cloud AI** action. The result remains in the editor for review and must be saved/approved through the existing flow.
- Added mocked backend and frontend coverage, including model-gate behavior, no snapshot/other lead context, non-mutating output, price handling, secret non-disclosure, refusal handling, SDK error mappings, and editor/button behavior.

### Verification

- Backend: 175 pytest tests passed; Ruff and strict mypy passed.
- Frontend: 111 Vitest tests passed; ESLint, the app TypeScript project, and production build passed.
- `git diff --check` passed. No test makes a real Anthropic request.

### Handover and release follow-up

- The operator summary metric endpoint was not available in the implementation environment. The cloud feature was implemented on the operator's explicit instruction; there is no captured measurement showing the metric justified it. The installed Ollama inventory contained only `llama3.2:3b`, so the larger-local-model comparison was not performed.
- No real API key was supplied, so the one-draft manual Anthropic acceptance check was not performed. See `CLOUD_DRAFT_POLISH_HANDOVER.md` for ownership, entry points, invariants and the remaining checks.
- No installer was rebuilt or released.

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

## 26 August 2026 - Phase 2 assisted Zoho handoff

### Delivered

- Added **Open in Zoho to send** only for the current approved, unsent draft version. The backend repeats eligibility and approval-hash checks before returning recipient, subject and body.
- Recorded every open click on the lead activity timeline before the desktop composer is requested, including repeated clicks and explicit wording that sending is not confirmed.
- Opened the approved message through the OS default `mailto:` composer and copied the full body to the clipboard as a fallback. Composer failures are logged and do not mark the draft sent.
- Added explicit **Mark as sent** after a successful handoff. Confirmation creates one user-confirmed email communication, closes the draft for future drafting and leaves the pipeline stage unchanged.
- Kept Zoho OAuth/API sync, scheduling, background work and automatic sending out of scope.

### Verification

- Ruff, strict mypy, ESLint and strict TypeScript: pass.
- Pytest: 65 passed, including repeated handoff logging, failure recovery, sent-confirmation idempotency and communication evidence.
- Vitest/Testing Library: 86 passed, including route mapping, clipboard/composer payload, click-before-open ordering, sent confirmation and timeline visibility.
- Production frontend build and Rust Cargo check: pass.

## 26 August 2026 - Phase 1 local email drafts

### Delivered

- Added schema revision `0009_outreach_drafts` with structured lead holds, local draft batches, versioned draft content and version-bound approval evidence.
- Added the **Email drafts** navigation workspace and dashboard review count with a two-step **Prepare drafts** → **Review drafts** journey.
- Added server-side eligibility checks for suppression, pipeline stage, public email, contact classification, outreach hold and duplicate active drafts at generation and approval.
- Added recent-note and communication-warning context without interpreting free-form notes as automated instructions.
- Added subject/body personalisation, Save, Save and approve, individual/bulk approval, rejection reason and Reopen. Editing approved content clears approval; rejection never changes the lead.
- Kept the complete phase local: no AI, scheduling, Zoho transfer or email sending path was added.

### Verification

- Ruff, strict mypy, ESLint and strict TypeScript: pass.
- Pytest: 63 passed, including the 0008→0009 upgrade, draft lifecycle, hold and approval-invalidation invariants.
- Vitest/Testing Library: 85 passed, including API route mapping and the full prepare/edit/approve/reject/reopen journey.
- Production frontend build and desktop checks remain part of the final workspace quality run.

## 27 August 2026 - Reusable lead email context

### Delivered

- Added schema revision `0010_lead_email_context` and a focused **Context** tab for one primary contact plus reusable personalisation, relevance, offer and next-step inputs.
- Added named-contact and context template fields with a safe `greeting_name` fallback to the business name. Internal source/reference and avoid-mentioning fields are deliberately not inserted into templates.
- Made a valid direct contact email the preferred recipient, with the public business email retained as fallback across manual contact, draft creation, approval and Zoho handoff.
- Included the new fields in lead search, JSON/CSV export and deterministic contactability scoring. Any context/contact change invalidates approval for an unsent draft.

### Verification

- Pytest: 68 passed, including storage, validation, search, export, migration, scoring, context rendering, recipient priority, approval invalidation and Zoho handoff.
- Vitest/Testing Library: 91 passed, including Context-tab submission, template rendering, greeting fallback and email selection.
- Ruff, strict mypy, ESLint, strict TypeScript and the production frontend build pass.

## 28 August 2026 - First-open weekly automation and control-centre dashboard

### Delivered

- Added schema revision `0011_weekly_outreach_automation` with campaign opt-in/template/provider controls and durable campaign-week/outreach-batch links.
- Added first-open current-week catch-up, one-run-per-campaign/week idempotency, sequential multi-campaign execution, campaign-level failure isolation and same-run retry.
- Added strongest-campaign deduplication for shared leads, per-campaign shortlist capacity and a settings-controlled global maximum of automatic drafts per week.
- Reused the existing eligibility and template renderer so suppression, holds, contact classification, recent/replied communications, active drafts and referenced Context fields are checked before draft creation.
- Reworked Overview into a weekly control centre with due/caught-up status, campaign progress, retries, draft/action counts, attention groups and a discovery-to-send funnel.
- Kept the final workflow controlled: drafts require operator editing and approval; Zoho handoff and sent confirmation remain manual, and no email is sent automatically.

### Verification

- Focused weekly backend suite: 7 passed, covering first-open idempotency, Tuesday catch-up, missing Context, cross-campaign deduplication, global cap, retry and failure isolation.
- Focused dashboard interaction tests: pass, including automatic first-open check, weekly status and navigation to draft review.
- Full regression: 75 backend tests and 92 frontend tests passed. Ruff, strict mypy, ESLint, strict TypeScript, the production frontend build, Cargo desktop check and `git diff --check` all pass.

## 29 August 2026 - Local campaign assistant and confirmed playbook overrides

### Delivered

- Added a local-only campaign planner backed by Ollama and `llama3.2:3b`, with a loopback-only runtime boundary, structured output and no model tools.
- Added durable draft, revision and override-decision records. Material playbook departures wait for explicit confirmation; hard approval, provider and automation constraints cannot be overridden.
- Added a campaign chat and complete editable review form. Generation never creates a campaign; explicit approval creates exactly one paused campaign with weekly outreach disabled.
- Added exact LightBurn/xTool Creative Space process detection. Normal model limits remain active otherwise; only detected design-software sessions use reduced limits and unload-after-use behavior.
- Added workspace switches for the local assistant and design-software protection, plus Ollama setup and architecture documentation.

### Verification

- Full backend regression: 83 tests passed, plus the focused resource-policy test for standard, protected and protection-disabled modes.
- Frontend Vitest/Testing Library: 101 tests passed, including conversational draft creation, override confirmation and explicit paused-campaign approval.
- Ruff, backend application mypy, ESLint, strict TypeScript, frontend production build, lock verification and `git diff --check` pass.

## 29 August 2026 - General local AI conversations and attachments

### Delivered

- Expanded the same Ollama interface from campaign-only drafting to persistent general questions, templates, playbooks and planning conversations.
- Added authenticated local TXT/CSV/DOCX artifact generation and download, plus validated TXT/CSV/DOCX/JPEG/PNG uploads. The text-only 3B model clearly reports that it cannot inspect image content.
- Added a deliberate conversation/playbook-to-campaign handoff that reuses the existing override, paused-draft and separate-approval boundaries.
- Added schema revision `0013_general_assistant`, local attachment storage, a shared Ollama generation lock and the same exact LightBurn/xTool resource policy.

### Verification

- Real local Ollama run passed for a general answer, generated Word playbook, authenticated DOCX download and playbook-to-campaign handoff; no campaign existed before approval.
- Focused backend assistant/campaign suites: 12 passed. Frontend local-assistant interaction suite: 50 passed.
- Full regression: 91 backend tests and 102 frontend tests passed. Ruff, formatting, strict mypy, ESLint, strict TypeScript, production frontend build, Cargo tests/clippy, lock verification, dependency audit and `git diff --check` pass.

## 18 October 2026 - Architecture review refinements

Work follows `REFINEMENT_PLAN.md` on branch `refinement/architecture-review`, one commit per item. Decisions: D1 (name-only duplicates go to review) and D2 (audit records hold no personal data, with a historic scrub) approved by the operator; D3-D5 taken as recommended.

### R0.1 - Quality gate restored

- `main` failed the gate on strict mypy (an untyped lambda pair in `catalogue_answers.py` and five test typing errors) and on `ruff format` (nineteen files). All fixed; formatting changes are style only.

### R0.2 - Faster backend suite

- A session-scoped database at head is copied per test instead of running all migrations each time (1.6 s per test). Backend suite: 308 s to 124 s.
- Found while measuring: every test app's shutdown sends a real unload request to a local Ollama if one is running. Harmless, but it is recorded here for follow-up.

### R1 - Suppression covers every identifier (ADR-023)

- Added `suppression_identifier` and `discovery_candidate.review_reason` (migration `0017`, with a backfill from existing suppressions whose lead still exists).
- Lead create, edit and discovery promotion now check website host, phone, email and Instagram/Facebook handle as well as name/location. A name-only match holds a discovery candidate for review with its reason shown in the review queue.
- Structured log events record the suppression ID and matched identifier kind only.
- Verification: 6 new tests in `test_suppression_identifiers.py`; full backend suite 199 passed; Ruff, strict mypy, ESLint and TypeScript pass. Two schema-version assertions now read the head revision instead of naming it.

### R3 - No work left stuck in progress

- Any exception during campaign-draft generation, not only a `DomainError`, now rolls back and marks the draft `generation_failed`, so it stays editable. Unexpected errors are logged with their traceback and the draft ID.
- At startup, drafts still `generating` become `generation_failed`, and provider attempts still `running` become `interrupted` with `PROCESS_INTERRUPTED`. Both recoveries and run resumption are logged.
- Verification: 2 new tests in `test_interrupted_work.py`; full backend suite 201 passed with resource warnings as errors.

### R2 - Duplicate matching ranks identifiers and respects location (FR-015, D1)

- New pure module `leads/matching.py`. Ranks, strongest first: social handle, website host, phone, email, name with the same locality. The strongest match across all leads wins, so a phone match on one lead beats a name match on another.
- Locality compares UK postcode districts when both addresses have one, otherwise place words ("Leeds" matches "12 High Street, Leeds LS1 1AA").
- The same name in a different or unknown locality now goes to review with a stated reason instead of linking automatically. Phone keys under nine digits no longer match.
- Each link or review hold is logged with the candidate, lead and match rank.
- Verification: 22 new tests in `test_lead_matching.py`; existing discovery tests unchanged and passing; full backend suite 223 passed.

### R4 - Weekly outreach scheduled by the backend (FR-060, D5)

- New `WeeklyScheduler` thread, started in the lifespan and stopped first at shutdown. It runs the idempotent weekly check at start (on its own thread, so startup does not wait) and every 15 minutes (`ENS_WEEKLY_SCHEDULER_POLL_SECONDS`), and survives a failing check.
- `queue_weekly_due` is serialised with a lock and takes the week explicitly. The runs it creates are logged with the week and correlation ID.
- The frontend no longer triggers the check on load; the manual "Run due campaigns" action stays. Help text and the enable confirmation now describe the new behaviour.
- Correction to the plan: the database already allowed only one weekly run per campaign per week (migration 0011). No new migration was needed; the model now declares the constraint so the two match.
- Verification: 4 new tests in `test_weekly_scheduler.py` (week rollover with the app open, thread start and recovery, a four-way race, the constraint); two frontend tests updated; 227 backend and 112 frontend tests pass.

### Phase 1 gate and test tooling

- `npm.cmd run quality` failed at `npm audit` on advisories published since the lock was last updated (two critical in `tinypool`/`vitest`, all development tooling). Fixed with `npm audit fix` and vitest 3.2 to 5.0.5; no config change was needed and the frontend suite dropped from 103 s to 46 s. The full gate then passed.

### R5 - Startup errors recorded; desktop host supervises the backend

- Backend: logging is configured before migrations, and a migration failure is logged with its traceback. Alembic no longer replaces the app's log handlers when migrations run in process, so migration output reaches `application.jsonl`. `serve` writes `startup-error.log` on failure, and a new authenticated `POST /system/shutdown` stops the managed uvicorn server so lifespan shutdown runs.
- Fixed a latent logging defect found by the new tests: `configure_logging` opened a new file handler on every call and kept only the first directory configured in a process. It is now idempotent per directory and closes a replaced handler.
- Desktop host: the window opens immediately and the backend starts in the background. The frontend waits through `backend_connection`, which now returns the failure reason and log path instead of the app closing silently. Backend output goes to `backend-stderr.log` (rotated at 2 MB). A supervisor restarts a backend that exits unexpectedly, at most three times in five minutes, and emits `backend-status` events. On exit the host requests a clean shutdown and kills the process only after five seconds.
- Changed from the plan: no dialog plugin was added. Reporting failures in the app's own window needs no new dependency and gives a better message.
- Frontend: a persistent notice for "reconnecting" and "not running"; the host's failure message stays on screen; network failures become `BACKEND_UNREACHABLE`; non-JSON error bodies are described with their status and correlation ID; a failed host connection is retried on the next request; 204 responses resolve without parsing. Request timeouts (H5) wait for R7, because long AI requests are still synchronous.
- Verification: 5 new backend tests; 3 Rust tests (restart budget, status serialisation, and a real backend that serves health and exits on the shutdown request within the grace period); 6 new frontend tests. Backend 232, frontend 118, Rust 3 passed; Clippy, rustfmt, Ruff, mypy, ESLint and TypeScript pass.
- Manual desktop check (desktop:dev against a throwaway database and log folder): the backend process was killed and the host logged the exit and restarted it on the same port about three seconds later. Closing the window then sent the shutdown request; the backend logged "Shutdown requested by the desktop host" and "Application shutdown complete" and exited without being killed, leaving no process or dev server behind.

### R6 - A failed campaign run leaves nothing half-written

- `execute` now handles a `DomainError` like any other failure: it rolls back to the last commit (each provider batch and phase transition commits on its own), then records the failure. Before, a domain error part way through a batch committed whatever had been added, such as a lead without its evidence.
- A provider attempt rolled back to `running` is closed as failed with the run's error code. Domain failures are now logged with their code.
- Verification: `test_campaign_run_failures.py` (domain error and unexpected error) fails without the fix and passes with it; backend suite passes.

### H1-H4, H6 - Hardening

- H1: `CampaignAssistantManager.resource_profile()` no longer changes protection as a side effect. One read for an unprotected request used to stop the model being unloaded when LightBurn started; a regression test covers it.
- H2: DPAPI calls load crypt32/kernel32 with `use_last_error=True` and declared signatures, so a failure reports the real Windows error code (it was always 0). New Windows-only tests round-trip a secret and check a damaged vault's error code; the second fails on the old code.
- H3: one shared CSV escaper (`app/core/csv_safety.py`), now also covering tab and carriage-return prefixes, used by the lead export and by CSV files the assistant generates, which were not escaped before.
- H4: changed from the plan. The opener also handles `target="_blank"` links to lead websites, which can be any domain and sometimes plain http, so the http(s) wildcards stay. The redundant per-domain entries were removed and the capability description now states that only web pages and `mailto:` can be opened, never `file:` or custom protocols.
- H6: cloud polish defaults to `claude-sonnet-5-5`, offers `claude-haiku-5-5` as the lower-cost option, and keeps the older IDs valid. It sends `effort: "low"` only to models that accept it, raises `max_tokens` to 4000, and maps a retired model to `CLOUD_POLISH_MODEL_UNAVAILABLE`. The SDK is still imported only when a polish runs.
- Verification: backend suite, frontend 118 tests, Ruff, mypy, ESLint, TypeScript pass.

### R8 - The audit log holds no personal data (ADR-024, D2)

- New `outreach_activity` table and `outreach_draft.zoho_opened_at` (migration `0018`, backfilled from existing audit events with their IDs and times). Lead outreach history and the sent-confirmation check no longer read the audit log; `AuditRepository` was removed.
- `record_audit_event` refuses personal-data keys at any depth. `lead.updated` records changed field names plus before/after values for structured fields only; reasons become `reason_provided`; `lead.created` drops the business name. The migration rewrote historic audit summaries under the same rules.
- Safety copy before upgrades: `run_migrations` copies an existing database before applying pending revisions. This replaced a copy inside migration 0018 that hung, because SQLite's backup call spins while the same connection holds an open write transaction. The new migration test found it; a stack dump confirmed it.
- Found while tracing a stray warning: an R4 test opened the app's database without starting the app, so its engine was never disposed. Fixed.
- Verification: 4 new tests in `test_audit_minimisation.py` (runtime guard, call-site scan, history kept with and deleted with the lead, migration backfill, scrub and safety copy); full backend suite 258 passed with resource warnings as errors.

### R7 - Background jobs for long AI work (ADR-022), and H5 request timeouts

- New `app/jobs/` package and `background_job` table (migration `0019`): a single worker, progress committed per step, cancellation between steps, startup recovery, a one-at-a-time rule per kind, and a log line for every transition. Routes: `GET /jobs`, `GET /jobs/{id}`, `POST /jobs/{id}/cancel`.
- Lead autofill and catalogue enrichment now return a job (`202`). Preconditions are still checked up front. A job waits its turn for the shared model lock instead of failing as busy, so the operator's own requests still go first between steps. This resolves the trade-off that had kept enrichment in the foreground.
- Frontend: `api.ts` follows a job by polling, reports progress and cancels on abort, keeping the existing result types. Autofill shows "n of N" with "Stop after this lead"; enrichment shows progress with "Stop after this product" and no longer holds the app-wide busy state, so the rest of the workspace stays usable.
- H5 completed: requests time out after 60 s, or 200 s for interactive AI calls, with a message that the work may still finish. Single model interactions (chat, campaign drafting, refine, polish, briefings) stay synchronous by design.
- Verification: 9 backend job tests (real worker thread), an updated autofill test, 5 new frontend tests; backend and frontend suites pass.

### R9 - Largest services split without behaviour change

- `automation/service.py` (1,503 lines) is now a chain `base -> promotion -> discovery -> social -> service`, with helpers in `candidate_data.py`. `leads/service.py` (1,137 lines) is now `lead_base -> editing -> operations -> privacy -> service`, with helpers in `lead_read.py`. The largest module is 432 lines.
- Done by a script that copies each method's source verbatim, then checked by comparing every definition's syntax tree before and after: 36 and 26 definitions, none added, lost or changed. Class names and method names are unchanged, so no caller or test changed; 267 tests pass.
- `qualification/service.py` is left until it next needs feature work, as planned.

### R11 - Server state through a query cache (D4)

- Added `@tanstack/react-query` 5.104.1, pinned exactly; the newest release was a day old, so a version out for over two weeks was chosen. `App` owns its `QueryClient`, so existing tests render it unchanged. Retries are off under test and one retry is allowed in the app.
- The 21-endpoint all-or-nothing loader and the hand-written refreshers are replaced by one query per resource. A failing endpoint no longer blanks the rest of the workspace; its error appears once in the banner, and the host's "not running" state stays on screen. `refreshDomains` invalidates the matching queries and still throws if a re-fetch fails, so actions report it as before.
- Campaign-run and Meta-authorization polling became `refetchInterval`, with the same 1.5-second cadence and the same full resync when they settle. Direct state writes became `setQueryData`.
- Not done yet: workspaces still receive data from `App` as props rather than reading their own queries. That is now a mechanical follow-up (each workspace can call the same hooks), and it was deferred to keep this change reviewable.
- Verification: new test that leads still show when products fail to load; 123 frontend tests pass; TypeScript and ESLint (including exhaustive-deps) pass with no suppressions.

### R10 (phase 1) - Paged lead register

- Backend: `GET /leads/page` returns `{items, total, limit, offset}` of slim `LeadListItem` rows, newest first, filtered on the server by text, stage, suppression, campaign, source type (normalised as the register shows it; "unknown" means no named source) and review state. It loads only the lead rows plus three small queries for campaign IDs, source types and the next open follow-up. `GET /leads/source-types` feeds the source filter. The full `GET /leads` is unchanged.
- Measured: the first page of 5,000 leads takes 0.11 s locally (plan target 0.3 s), so no new index was needed; the test asserts under 1 s to leave room on slower machines.
- Frontend: the "All leads" register queries one page at a time, with search settled for 300 ms, filters and paging sent to the server, and the previous page kept on screen while the next loads. Changing a filter returns to page 1. The test suite's `leadPage` fake applies the same server rules to each test's mocked leads, so the existing register tests still check filtering and paging.
- Phase 2, not done: the pipeline board, dashboard, email drafts, campaign register and assistant pickers still use the full lead list, and `App` still loads it for them and for the counts. Each can move to paged or summary endpoints on its own, after which the full list can be retired. Until then, startup still loads every lead.
- Verification: 4 new backend tests (paging, item fields, every filter, 5,000-lead timing); 1 new frontend test for the requested parameters; backend 271 and frontend 124 tests pass.

### H7 - Source documents moved out of the repository root

- The eight specification, brief and audit documents moved unchanged to `docs/source/`, with an index. Changed from the plan's `docs/archive/`: the BRD/FSD and the design system are still authoritative, so "archive" would mislead. Only `BASELINE_ASSESSMENT.md` named them, and it now says where they are; no code or script referred to them.

### Upgrading the installed app

- The operator's database moves from revision 0016 to 0019 on the next start. Before migrating, the app writes `ens-leads.pre-upgrade-0016_seed_outreach_templates-<time>.sqlite3` beside the database (see `BACKUP_AND_RESTORE.md`). Migration 0018 removes personal data from historic audit events, so keep that copy until the upgraded app has been checked, then delete it.

## UX redesign (see `UX_REDESIGN_PLAN.md`)

Branch `ux/redesign`. Visual checks run against a scratch database seeded with fictional businesses only; screenshots stay outside the repository.

### A1 - Type scale, motion tokens and status pills

- Six type steps (`--ens-type-xs` to `--ens-type-2xl`) replace eleven. The old names map onto them, so no component changed size by accident; `--ens-text-xl` and `--ens-text-2xl` were used but never defined, and now are.
- Motion tokens (120, 200 and 300 ms, two easings) drop to zero when the operator's system asks for reduced motion.
- Status badges became pills with a coloured dot, and pipeline classification badges get a tone from `classificationTone`. The white focus outline that framed the whole content area on every click is gone; keyboard focus on controls is unchanged.

### A2 - Shared components

- `Collapsible`, `Drawer` (focus kept inside, Escape closes, focus returns to the opener), `Toolbar` with filter chips and "Clear all", `StatusPill`, `SkeletonRows`, and a rows-per-page choice in `Pagination`.
- `useRememberedState` keeps a screen's tab, page, filters and open sections for the session (sessionStorage, prefix `ens:view:`, in-memory fallback). Nothing personal is stored: only view settings.
- Verification: 5 new component tests.

### A3 - Motion

- Pages and tabs fade in, toasts slide in, alerts reveal, a changed row flashes once, and clickable metric cards lift on hover. All of it uses the A1 tokens, so it switches off with reduced motion.

### B1 - Header status, footer and sidebar card removed

- The "API connected" badge became a quiet green dot, with a visible label only while connecting ("Connecting to service") or offline ("Service offline"). The footer bar and the sidebar "Controlled mode" card are gone, which returns about 120 px of height to the content.
- What they told the operator now lives where it is looked for: Settings > Diagnostics opens with "How this app protects you" (local data, nothing sent automatically, suppression, discovery limits, local AI) and the version.
- Verification: two shell tests updated to the new wording; 129 frontend tests pass (one timed out once while the dev server and browser shared the machine, and passes on its own in 2.4 s); TypeScript and ESLint pass.

### B2 - Sidebar groups, action badges and icon mode

- Three groups: Find (Overview, AI assistant until B3, Campaigns, All leads), Work (Weekly shortlist, Pipeline, Email drafts) and Set up (Catalogue, Templates, Settings).
- Plain totals are gone. A gold badge appears only when something waits for the operator: leads needing review, follow-ups due today or overdue, drafts awaiting approval, and shortlist entries still awaiting a decision. Screen readers hear what the number means ("3 awaiting approval").
- "Collapse sidebar" turns the sidebar into an icon rail with tooltips and corner badges, and the choice is kept between sessions (`localStorage`, view setting only). Between 901 and 1180 px it collapses on its own; below 900 px the existing top bar is unchanged.
- Fixed while there: the compact layout still reserved a row for the removed footer.
- Verification: 1 new test (groups, badges, collapse and its persistence); 130 frontend tests pass; TypeScript and ESLint pass.

### B3 - Floating AI assistant (operator addition)

- A round gold button, bottom-right on every screen, widens to "Ask AI" on hover or focus. It opens a non-modal 440 x 640 px panel (a wide mode of 900 px shows the campaign brief and review side by side) without leaving the current page.
- The panel hosts the existing assistant unchanged in behaviour: App copilot and Campaign draft, conversations, attachments, context picker, overrides and approval. It is created on first open, so the model status is not checked at startup, and kept mounted afterwards, so a conversation survives closing it. Esc or the close button closes it and focus returns to the button; while open, the button is hidden so there is only one close control.
- Every "Ask AI" action opens the panel with that record as context; asking about the same record again resets the picker (a request key). "Plan with AI" in Create campaign opens it in Campaign draft mode. Approving a campaign draft closes the panel and shows Campaigns.
- The "AI assistant" screen and sidebar entry are removed (`AssistantWorkspace.tsx` deleted, `assistant` dropped from `WorkspaceSection`). The panel renders outside `<main>`, so page layout rules and the page's busy state do not apply to it.
- The warning dot on the button appears once the assistant has reported the local model is not ready; before the first open it cannot know, by design.
- Docs: `AI_INTEGRATION_ARCHITECTURE.md` and `LOCAL_SETUP.md` updated.
- Found while here: the per-item typecheck used `tsc -p .`, which checks nothing because the root config only holds references. The gate is `npm run typecheck` (`tsc -b`), which passes on A1-B3.
- Verification: 2 new tests (open, Esc, focus return, kept state; Plan with AI), 4 assistant tests moved to the panel; 131 frontend tests pass; TypeScript and ESLint pass.

Phase gate after B3: `npm run quality` passed (frontend 131, backend 271, Rust 3; lint, types and build).

### C1 + C2 - One level of cards, plain wording

- Eyebrow labels are gone from all 31 page and section headings; `PageHeader` and `SectionHeading` take an optional one-sentence description.
- Section headings that only repeated the tab or page name are removed (Campaigns list, Leads, Pipeline, Settings); their sections keep an accessible label. A section without its own heading now draws no frame, so the panels inside it are the only cards: one level instead of two.
- Wording, for example: "Lead intelligence dashboard" -> "Overview", "Catalogue and scoring" -> "Catalogue", "Settings and diagnostics" -> "Settings", "Message templates" -> "Templates", "Campaign register" -> "Your campaigns", "Discover, score and prepare" -> "Find new leads", "Action queue" -> "Needs you", "Upload Shopify listing CSV" -> "Import from Shopify", "Bakery scoring weights" -> "Scoring weights". Every description is now one sentence.
- Not done here, by design: wording inside each screen's rows and buttons, and the remaining in-page safety notices, change with that screen's Phase D redesign, so each screen is reworded once.
- Verification: three heading assertions updated; 131 frontend tests pass; TypeScript and ESLint pass.

### C3 - Remembered list state

- For the rest of the session, each screen keeps its open tab, search, filters, page and rows per page when the operator switches away and back: Campaigns (search, show archived, page), All leads (tab, search, all five filters, page), Pipeline (tab, search, page), Catalogue (tab, search, include-retired, page, rows), Templates (tab, search, page, rows) and Settings (tab). Keys are per screen under `ens:view:`; only view settings are stored.
- `useRememberedState` gained an optional starting value, so a link from Overview that opens All leads on "needs review" still wins over the remembered filter.
- Catalogue products and templates show 10 per page with a rows-per-page choice (10, 25, 50). Per-lead lists (follow-ups, timeline) are deliberately not remembered, because they belong to whichever lead is open.
- Verification: 1 new test (page, rows per page and search survive switching screens); the catalogue paging test now expects 10 per page; 132 frontend tests pass; TypeScript and ESLint pass.

### D1 - Overview becomes "Today"

- The first screen is now "Today" (sidebar and title), dated, and opens with what needs the operator, most urgent first: a campaign that stopped, campaigns due to run, drafts to approve, approved emails ready for Zoho, emails to mark as sent, follow-ups due or overdue, shortlisted leads to decide, leads needing review and possible duplicates. Each card says what to do and has one button straight to the right screen; "Run due campaigns" keeps its confirmation.
- When nothing needs the operator: "You're up to date", with the date of the next weekly check (or how to turn weekly outreach on).
- Below: "This week" (found, scored, shortlisted, drafted, sent, plus the pipeline by stage group), "Coming up" (next five follow-ups), the weekly runs as a collapsible section with the capacity and "how it works" help, and a slim totals row. The long weekly explanation became a help tip.
- Counts agree with the sidebar badges (the shortlist count covers every open shortlist). New `goToPipeline` action. Staggered card entry is switched off under reduced motion, which now also zeroes animation delays app-wide.
- Verification: 2 new tests (empty day; urgency order); the dashboard tests now go through the action cards and help tips; 134 frontend tests pass; TypeScript and ESLint pass.

### D2 - All leads: saved views, filter chips and a preview drawer

- Saved views above the register: All, Needs review, Ready to contact, Following up, Won and Do not contact. Each is a combination of the existing server filters (R10), so the backend is unchanged; the matching view is highlighted, and none is when the filters are custom.
- The filters sit in the shared toolbar with a chip per active filter (removable), "Clear all" and "Showing 1–10 of N". "Set filters with AI" and "Stalled leads" moved into a closed disclosure under the toolbar.
- Clicking a row, or the business name, opens a preview drawer: stage, score, contact, where it was found, next follow-up and campaigns, with "Ask AI" and "Open in pipeline". Row buttons still work without opening it. Loading shows skeleton rows instead of a spinner; dates show as dates.
- Not done: stage names are still title case from `humanize` ("Ready To Contact"); a sentence-case pass touches every screen and is left for the polish phase.
- Verification: 1 new test (saved view sets filters, chip removal, clear all, preview drawer to pipeline); 135 frontend tests pass; TypeScript and ESLint pass.

### D3 - Pipeline board and lead summary

- A List / Board switch on Pipeline, remembered for the session. The board has one column per stage group (Prospecting, Contact, Engaged, Closed) with a count; each card shows the business, location, stage, score, next follow-up and value (won, else quoted, else estimated).
- Moving a card, by dragging it onto a column or with its "Move to…" button (the keyboard route), opens a small dialog: the new stage (only that column's stages when dragged) and an optional reason, then the same `changeLeadStage` action and server rules as the lead's own form, recorded in its history. Suppressed leads cannot be dragged or moved and say why; "Do not contact" is never offered, because suppression belongs to the Privacy tab. Clicking a card opens that lead in the list view.
- The open lead now has a summary strip above its tabs: stage, score, next follow-up and value. The duplicate stage badge and the "Selected lead" eyebrow were removed from its header.
- Not done from the plan: making "Lead details" the default tab with privacy and audit collapsed. The current tabs already open on Overview, and folding Privacy into a collapsed section is left for the polish phase.
- Verification: 1 new test (board columns, Move to…, no "Do not contact" option, stage change called with the reason, card opens the list); the score test reads the summary strip; 136 frontend tests pass; TypeScript and ESLint pass.

### D4 - Email drafts review queue

- The review tab already had the queue beside the editor; it now shows progress ("2 of 12 reviewed" with a bar) and keyboard shortcuts while the queue has focus: J or Down for the next draft, K or Up for the previous, A to approve the draft on screen, E to jump to its subject, ? to show or hide the list. A "Shortcuts" button shows the same list.
- Shortcuts never fire while typing (text fields, text areas, selects) or with Ctrl, Alt or Cmd held. A uses the same approval call as "Approve selected" and asks first, with the same "Nothing will be sent automatically" wording; it does nothing for a draft that is not awaiting review.
- Verification: 1 new test (J/K move, ? shows help, E focuses the subject, typing "a" there does nothing, A confirms then approves); 137 frontend tests pass; TypeScript and ESLint pass.

### D5 (part 1) - Campaign groups, a "More" menu and editing in a drawer

- Campaigns are grouped into collapsible Active, Paused and Archived sections, each with its count and its own pages (remembered per group). Archived starts closed and replaces the "Show archived" toggle; search covers all three.
- Each card keeps its run buttons, Ask AI, Edit and Pause/Resume in view; Archive, Duplicate and Delete moved into a shared `MoreMenu`, which closes on Escape, on a click outside and after an action. Every confirmation is unchanged.
- Edit opens the full campaign form in a wide drawer instead of expanding inside the card, with the same validation, weekly-outreach confirmation and save.
- Not done here: "last run" and "this week's leads" on each card need per-campaign figures the screen does not load yet.
- Verification: 1 new component test (More menu); the edit, weekly-enable and archive tests now use the drawer and the Archived section; 138 frontend tests pass; TypeScript and ESLint pass.

### D5 (part 2) - New campaign as steps

- Create campaign is now five steps over the same fields and the same `createCampaign` call: Basics (name, segment, location, description), Audience (radius, weekly shortlist, minimum score, keywords, exclusions), Discovery (sources), Products (categories or a product family) and Review (a plain summary before "Create campaign"). "Plan with AI" stays beside the heading as the other way to start.
- Next checks only the fields on the current step, with the browser's own messages, and will not move past an invalid one; clicking a later step in the stepper checks every step on the way. Enter in a field moves to the next step; only the Review step can create the campaign.
- The plan's "Weekly outreach" step is not there because the create form has never had weekly-outreach fields; weekly outreach is still set when editing, with its confirmation.
- Fixed while checking: a rule that sized every child of the main area also stretched the success toast across the window; the toast is now excluded and sits top-right again.
- Verification: 1 new test (an empty required field keeps the step; Enter advances without creating); the three creation tests step through the form with a helper; 139 frontend tests pass; TypeScript and ESLint pass.

### D6 - Shortlist cards

- Each ranked card shows why it scored as short chips ("Public contact route", "Matched …"), without repeating the score already on the card, and a plain decision label ("Awaiting your decision", "Accepted", "Skipped", "Deferred", "Replaced", "Do not contact").
- Accept and Skip are the two buttons on each card (the existing "approved" and "dismissed" actions); Defer and Replace moved into its More menu. The builder form is a collapsible section, open only when there is no shortlist yet.
- Not done: an undo toast. The backend has no action that reopens a decided shortlist entry, so there is nothing to undo with; adding one is a backend change for later.
- Verification: the shortlist test now checks the reason chips, Accept, and Defer through the More menu; 139 frontend tests pass; TypeScript and ESLint pass.

### D7 - Catalogue and Settings

- Settings has a section list beside the content instead of tabs: General (campaign defaults and the Today window), Outreach (the weekly draft limit, with a reminder that emails are approved and sent by the operator), AI and models (local assistant, model, LightBurn/xTool protection, and cloud polish), Connections, Data and privacy (export and backup) and About (how the app protects you, version, diagnostics). The section is remembered for the session; General is the default.
- The old single defaults form is now three small forms. The settings endpoint already accepts partial updates, so each saves only its own fields.
- Connections opens with a status card per connection: Instagram via Meta, Google Places (now passed the automation capabilities) and Cloud draft polish, each "Connected", "Needs attention" (with the reason) or "Not set up".
- Catalogue: products missing sales knowledge, or whose listing changed since, carry a badge. A Cards / By category switch (remembered) adds a view grouped into collapsible sections by the last part of the Shopify category ("Keychains", "Card Cases"), each counting the products that need knowledge. Editing a product moved from an inline disclosure to a wide drawer in both views and closes on a successful save.
- Not done: grouping by the knowledge pack's own eight product groups, which the product list does not expose yet.
- Verification: 1 new test (badge, grouped view with its knowledge count, edit in the drawer); the settings and Meta tests use the section list; 140 frontend tests pass; TypeScript and ESLint pass.

Phase gate after D7: `npm run quality` passed (frontend 140, backend 271, Rust 3; lint, types and build).

### B4 - Global search (Ctrl+K)

- Ctrl+K (or Cmd+K), or the new Search box in the header, opens a search over what is already loaded: screens ("Go to"), quick actions (New campaign, Plan a campaign with AI, Ask AI, Leads needing review), leads, campaigns, products and templates, grouped by type with up to six results each. With nothing typed it shows screens and actions.
- Keyboard first: arrows move, Enter opens, Esc closes and focus returns to where it was. It is a combobox over a listbox, so screen readers announce the active result. Choosing a lead opens it in Pipeline; a campaign, product or template opens its screen.
- Nothing new is fetched and nothing is stored: it searches the data each screen already has.
- Verification: 1 new test (Ctrl+K, grouped results, Enter opens the lead, header button, Esc closes); 141 frontend tests pass; TypeScript and ESLint pass.

### E1 + E2 - Density and light theme

- Settings > General > Appearance: Theme (Match Windows, Light, Dark) and Density (Comfortable, Compact). Both apply at once, through `data-theme` and `data-density` on the page root, and are kept in this computer's browser storage (display preferences only, no workspace data). They are applied before the first paint, so a light-theme user never sees a dark flash.
- The light theme is the same brand on warm paper: navy text, gold actions, and a darker gold for accent text. Measured contrast: every text colour is at least 4.7:1 on every light surface (WCAG AA is 4.5:1), and dark text on the gold buttons is 9.3:1. Following Windows is the default; `color-scheme` is set so native controls and scrollbars match.
- Compact density lowers control heights (44/38/32 px to 36/32/28 px) and tightens the spacing scale; type sizes stay the same, for legibility.
- Verification: 1 new test (theme and density applied, stored, and "Match Windows" clearing the choice); the test setup now clears local storage and the appearance attributes between tests; 142 frontend tests pass; TypeScript and ESLint pass.

## 2 November 2026 — Mobile access (ADR-025)

Plan: `docs/implementation/MOBILE_ACCESS_PLAN.md`. Branch `mobile/access`, one commit per item. At the operator's request (2 November), full gates run at the end of each phase rather than after every item; items in between get lint, type checks and their own tests.

### M0 - Decision record

- ADR-025 records phone access through a second loopback listener reached over Tailscale, keeping ADR-015 intact. The security model gains six threat rows; the control register gains CMP-016.

### M1 - Second listener

- `ENS_MOBILE_GATEWAY_PORT` (default 8770, loopback, 1024-65535). The phone gateway is an ASGI wrapper around the same app that marks each request's scope as the phone channel; it runs in its own uvicorn server and thread, so there is still one scheduler, job manager and database writer.
- The on/off switch and the Tailscale name are kept in `app_setting` (`mobile_access`), off by default, and applied at startup and whenever they change. A port clash leaves the switch on and reports "Port 8770 is already in use on this PC." in the status instead of failing.
- On the phone channel the session token is never accepted; until pairing exists every authenticated route answers `401 PHONE_NOT_PAIRED`. A `DesktopOnly` dependency answers `403 DESKTOP_ONLY` there; the new `/mobile/status` and `/mobile/config` routes use it.
- Deviation from the plan: one wrapper over the shared app instead of a second FastAPI app with dependency overrides. Same effect, and the channel mark cannot come from request data.
- Logs: `mobile_gateway_started`, `mobile_gateway_stopped`, `mobile_gateway_start_failed` with the port only.
- Verification: 6 new tests (off by default; switching on serves on loopback and refuses the session token; switching off stops it and leaves the desktop API up; the switch survives a restart; a port clash is reported; the Tailscale name is validated). Full backend suite: 276 passed, 1 skipped; ruff and mypy pass.

### M2 - Paired devices

- Migration `0020_mobile_devices` adds `mobile_device` (name, label, secret hash, last seen, revoked) and `mobile_pairing_code` (hash, attempts, expiry, closed).
- Settings on the PC issue an 8-character code (no I, L, O, 0, 1), shown as `K7QM-4T9X`, valid 5 minutes; a new code closes any earlier one. The pair link carries it after `#`, so it never appears in a request line. Five wrong codes cancel it; twenty failures across codes in ten minutes refuse pairing (`429 PAIRING_LOCKED`).
- Pairing (`POST /mobile/pair`, gateway only) returns a 256-bit secret in an `HttpOnly; Secure; SameSite=Strict; Path=/api` cookie. Only its SHA-256 hash is stored. A device unused for 30 days must pair again; last-seen is written at most every five minutes.
- The gateway reads the cookie on every API request and marks the request with the device. `GET /mobile/session` says which phone this is; `POST /mobile/sign-out` revokes this phone. On the PC: list devices, revoke one, revoke all, each audited.
- Logs: `mobile_pairing_code_issued`, `mobile_pairing_succeeded`, `mobile_pairing_failed` (reason, attempt count), `mobile_device_revoked`. Codes, cookies and secrets are never logged.

### M3 - Route policy

- `dependencies=[DESKTOP_ONLY]` on 35 routes: backups, catalogue and template changes (read-only on the phone, as agreed), lead export and privacy deletion, scoring profile changes, Meta and cloud polish set-up, workspace settings changes, diagnostics, shutdown, the API schema, and phone access management itself.
- Privacy deletion of a lead was not in the plan's table; it is irreversible and type-to-confirm, so it stays on the PC. Reading settings stays allowed, because the phone needs the follow-up window and limits.
- A test walks every registered route and compares the desktop-only set with an explicit list, so a new route must be classified.

### M4 - Gateway hardening and the phone app files

- `Host` must be the Tailscale name or loopback on the gateway port (`421 HOST_NOT_ALLOWED`), which stops DNS rebinding. Every change needs a matching `Origin` and `X-ENS-Request: 1` (`403 ORIGIN_REJECTED`).
- Every response gets a strict content-security policy, `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`, `no-referrer`, HSTS and a permissions policy; API responses get `Cache-Control: no-store`.
- The gateway serves the built frontend: hashed assets are cached for a year, the page is `no-cache`, screen paths such as `/pair` fall back to the page, and paths outside the build folder are refused. Content types are fixed in code, because the Windows registry can serve `.js` as text. If the build is missing, phones see a page saying to run `npm run frontend:build`, and the status reports `phone_app_ready: false`.
- `ENS_MOBILE_FRONTEND_DIRECTORY` overrides the folder; the packaged backend now bundles `apps/frontend/dist` (the sidecar build builds the frontend first).

### M5 - Attribution

- A context variable carries the actor for the request: `phone:<device id>` on the gateway, `local_user` otherwise. Audit events, stage events and notes take it by default, and the five places that wrote `"local_user"` explicitly now use it, so a note added from a phone is recorded as that phone's.
- Fixed in the same commit: M4's commit had mangled the frontend path in `build-backend-sidecar.ps1`.

### M7 (backend) - Tailscale helper

- `GET /mobile/tailscale` reports installed, signed in, this PC's name and whether the phone address is set up. `POST /mobile/tailscale/serve` runs `tailscale serve --bg --https=443 http://127.0.0.1:<port>` and saves the name as the phone address; `DELETE` runs `tailscale serve --https=443 off`. The command lines are fixed in code. If Tailscale asks for HTTPS to be enabled for the account, its admin link is returned for the button.

### M15a (check) - Assistant answers and a dropped phone request

- Confirmed: `AssistantService.send` commits the question before calling the model and the answer after it. A phone that loses the request can reload the conversation and find the answer, with no resend. The frontend side is part of M15.

### Backend phase gate

- 33 new tests in `test_mobile_access.py` (pairing, single use, replacement, expiry, five-attempt cancel, lockout, gateway-only pairing, revoke one and all, 30-day expiry, sign-out, forged cookie, the route walk, desktop-only refusals, phone reads, foreign host, four origin and header cases, no-store and policy headers, file serving, path traversal, missing build, attribution, three Tailscale cases) plus the 6 in `test_mobile_gateway.py`.
- Full backend suite: 309 passed, 1 skipped; ruff, ruff format and mypy pass.

### M8 + M9 - Phone connection and pairing

- `connection.ts` decides the mode: inside Tauri or with Vite's API env it is the desktop; a production build without them (what the gateway serves) is the phone. On a phone `api.ts` calls `/api/v1` on the same origin with `X-ENS-Request: 1` and no session token, says "Your PC isn't reachable" when the request can't get through or Tailscale answers 502/504, and tells the app when the PC answers `PHONE_NOT_PAIRED`.
- `PhoneGate` shows the workspace only once `/mobile/session` answers; otherwise the pairing form (code read from the `/pair#…` fragment, the phone named from its browser) or the "Your PC isn't reachable" screen with **Try again**. A revoked phone returns to pairing mid-session.
- Phone Settings: Appearance for this phone, "Signed in as …", **Sign out this phone** (revokes it), and a list of what stays on the PC. Catalogue and Templates take `readOnly` and show only the list with a "View only on a phone" note. The phone never asks for diagnostics.

### M6 + M7 (frontend) - Settings > Phone access on the PC

- A new Settings section: status pill (Off, On with phones paired, or Needs attention with the reason), the on/off switch, the phone address step (install Tailscale, sign in, **Set up phone address**, or the address itself), **Pair a phone** with a QR code, the code and a countdown (it closes itself when the phone pairs), and the paired phones with **Remove** and **Remove all phones**.
- QR codes come from `qrcode-generator@2.0.4` (exact version, no dependencies), drawn as SVG squares rather than injected markup. Outside links go through a shared `openExternalUrl`, which on a phone follows `mailto:` links in place because phones block windows opened after waiting on the PC.

### M10-M12 - Phone layout and the waiting indicator

- Below 600 px: a compact header (logo, screen title, search, connection dot), bottom tabs (Today, Shortlist, Pipeline, Drafts with the same gold badges, More), a More sheet (Campaigns, All leads, Catalogue and Templates marked view only, Settings) that closes on Esc or the backdrop, the AI button above the tabs, full-screen drawers, assistant and search, 44 px targets, 16 px fields, and safe-area padding. Today, Shortlist and All leads use their existing stacked and card layouts.
- The operator asked that a phone always shows when it is waiting on the PC. `pendingWork.ts` tracks every change, every AI request and every followed background job made from a phone; `PendingWorkIndicator` shows one message after 400 ms ("Saving on your PC…", "Thinking on your PC…", "Working on your PC… 3 of 10"), puts AI and jobs ahead of saves, counts the rest, and after 10 seconds adds that the PC carries on (or, for a save, to keep the screen open). A message rather than a full-screen loader, so the phone stays usable.
- Returning to the phone after 15 seconds away refreshes the workspace.

### M13 - Pipeline

- On a phone the board opens first as stage chips over one column (the chosen group is remembered), with dragging switched off; "Move to…" is unchanged. Opening a lead shows it on its own with **All stages** to go back. History entries for stage changes and notes made from a phone end "· from your phone".

### M14 - Email drafts

- On a phone the queue comes first and a draft opens on its own with "All drafts · 3 of 12". The send button reads **Open in mail to send**. When the approved draft has been opened in the mail app, the draft shows **Did you send it?** with **Not yet** and **Yes, sent**; "sent" is still recorded only by the operator's answer.

### M15 + M15a - Assistant

- If a phone loses an assistant request (locked screen, app switch, timeout), it looks for the saved answer every 3 seconds for up to 4 minutes, showing "Still thinking on your PC…", and does not resend. If the question never reached the PC it says so after two checks. The lead briefing is not saved by the backend, so a lost briefing shows the error and can be asked again.

### M16 - Add to home screen

- `manifest.webmanifest`, icons from the desktop icon set (192, 512, Apple touch 180), theme colours for both themes, `viewport-fit=cover`. No service worker, so nothing about leads is cached on the phone.

### M17 - Verification

- 22 new frontend tests (`phone.test.ts`, `PhoneComponents.test.tsx`): connection mode, same-origin requests without a token, PC unreachable and 502, the unpaired signal, waiting-work tracking for changes and AI but not reads, pairing helpers, the gate (paired, pairing from a QR link, wrong code, unreachable and retry, revoked mid-session), the indicator's delay, order, progress and reassurance, tabs and More sheet, and the Phone access panel (switch on, Tailscale missing, QR code and noticing the new phone, removing a phone). Full frontend: 164 passed; ESLint and TypeScript pass; production build passes.
- Real run on a throwaway database (scratchpad only): backend with the gateway on port 8771, a headless browser at 390×844 opened the pairing link, paired, and went through Today, Pipeline stage chips, a lead, the More sheet and Settings. A note added through the phone session was stored with actor `phone:209f871b…`; lead export from the phone answered 403. Fixed during the run: the phone Settings choices and sign-out button sat against the panel edge.
- Not checked here, for the operator: a real phone over Tailscale (Tailscale is not installed on this PC), the mail app handoff, and Add to Home Screen.
- `npm.cmd run quality` stops at its first step, `npm audit --audit-level=high`, on a high advisory in Vite's dev server that is also on `main` (13 advisories, 1 high, same as before this work). The remaining gate steps were run directly; results below.

### M18 - Runbook

- `docs/operations/MOBILE_ACCESS.md`: set-up, daily use, what stays on the PC, troubleshooting, a lost phone, switching off. `Start Etch N Shine.cmd` now rebuilds the phone app files when the frontend source is newer than the build, and refuses to while a local `.env` file exists (Vite would copy its values into the files phones load).

### Phase gate (all of mobile access)

- `npm audit --audit-level=high` fails on Vite's dev-server advisory that `main` already has (see M17); not introduced here and left for a separate Vite upgrade.
- Every other `quality.ps1` step passes: `uv lock --check`; ESLint, TypeScript, Vitest (164 passed) and the production build; ruff, ruff format and mypy (172 files); pytest (309 passed, 1 skipped); `cargo fmt --check`, `cargo test` (3 passed) and Clippy with warnings denied.
