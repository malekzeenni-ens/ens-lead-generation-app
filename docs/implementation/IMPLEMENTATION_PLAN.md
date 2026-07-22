# Implementation plan

**Plan date:** 18 July 2026  
**Delivery approach:** Tested vertical slices with explicit stage gates.

## 1. Current-state summary

The project began from a documentation-only clean baseline. There is no legacy application or production data to preserve. All five repository documents have been read in full; the BRD/FSD filename discrepancy is recorded in the baseline assessment. The additional universal application design system is treated as the UI implementation standard.

## 2. Confirmed target architecture

- Tauri 2 desktop lifecycle host.
- React, TypeScript strict mode and Vite presentation layer.
- FastAPI/Pydantic application API bound to `127.0.0.1`.
- Application-owned ephemeral session token for local API calls.
- SQLAlchemy 2 and Alembic over SQLite with WAL, foreign keys and busy timeout.
- Modular-monolith domain boundaries and provider-neutral adapter ports.
- SQLite-backed durable jobs before scheduled/external work is enabled.
- Windows Credential Manager or DPAPI-backed secrets before credentials are accepted.
- Rotating, structured, redacted logs and correlation IDs.

The architecture is confirmed by ADR-001 through ADR-015.

## 3. Repository changes required

Create `apps/desktop`, `apps/frontend`, `apps/backend`, migrations, tests, documentation, scripts and CI. Add reproducible dependency locks, `.env.example`, lint/type/test/build commands, seed commands and backup/restore tooling.

## 4. Stage-by-stage backlog

| Stage | Coherent outcomes | Gate |
|---|---|---|
| 0 | Desktop/backend lifecycle spike; loopback/session control; migrations/WAL; backup/restore; mock provider contracts; SSRF design; AI schema spike; Windows vault spike; packaging check | Partially complete: local lifecycle/data/packaging, provider contract and bounded SSRF controls proven; AI and vault spikes pending |
| 1 | Campaign CRUD; manual lead capture; list/detail; pipeline; notes; follow-ups; suppression; audit; export; backup/restore; settings/diagnostics | Local workflow complete and verified; CSV import removed from this increment by user direction |
| 2 | Observations/evidence; field resolution; identity/merge; deterministic scoring; catalogue/matching; shortlist | Qualification plus button-triggered bulk campaign execution complete; richer field resolution/merge remain |
| 3 | Durable worker; budgets; approved Google adapter; assisted Meta capture; safe website enrichment | Operator-triggered durable run, Google adapter, bounded multi-page enrichment and assisted Meta capture complete; scheduling and budgets remain |
| 4 | AI gateway; evidence packets; drafts/versions/approval; manual-send confirmation; communications | Approval, suppression and AI validation gates pass |
| 5 | Analytics; performance/accessibility/security hardening; installer; runbooks; pilot support | Clean-profile pilot gate passes |

## 5. Requirement traceability

`REQUIREMENTS_TRACEABILITY.md` is the live source. Every increment updates requirement status, code, tests and evidence. The first increment addresses FR-001, FR-005, FR-010, FR-031/032, FR-113, FR-160, DR-001/002/003/009/012, SEC-001/003/005/009, NFR-001/004/005/009/010/011/012 and architecture additions NFR-A05/A07.

## 6. Data-model implementation plan

Begin with campaign, lead, lead-campaign, source-system, source-observation, stage-event, audit-event and backup-manifest tables. Add later conceptual entities only with their owning workflow. Canonical values and source observations remain separate; no provider response model enters domain tables.

## 7. Migration plan

Alembic is the only schema mutation path. Startup runs forward migrations before accepting API traffic. Each revision is tested from an empty database and, after the first revision, from the preceding schema. Destructive revisions require a verified backup and explicit recovery instructions.

## 8. Security plan

Enforce loopback-only CLI configuration, random per-desktop-session API token, strict validation, correlation-aware error responses, CORS allowlist, safe logs, no raw HTML rendering and no secrets in source/database/frontend. URL/SSRF controls now gate website fetching. Google credentials are accepted from the backend process environment and never persisted; Meta credentials and tokens use the implemented Windows DPAPI vault. Formula-safe lead export and bounded Shopify catalogue CSV import controls are implemented.

## 9. Compliance-control plan

Capture contact classification and source/date on manual entry. Suppression will override shortlist, preparation, approval and later send actions. Unknown classification remains visibly unresolved. Production outreach remains gated on professional UK legal/privacy review; the application provides controls, not legal conclusions.

## 10. Integration-adapter plan

Provider-neutral discovery batches feed one staged-candidate pipeline. Google uses field-mask/radius controls. Instagram uses direct campaign hashtag links for operator selection followed by professional-profile Business Discovery, plus bulk refresh of saved handles; Facebook retains assisted capture. Website enrichment remains same-domain and SSRF protected; Zoho is draft-first in Phase 2. Shopify API sync is deferred; the implemented Shopify boundary is an operator-selected local product-export CSV only.

## 11. AI plan

AI remains advisory. The gateway will accept minimised evidence packets, versioned prompts and schema-constrained output, reject unknown evidence IDs and prohibited claims, record model/prompt/input hashes and usage, cache stable inputs, and fail without blocking manual workflows.

## 12. Testing plan

- Pytest: domain, migration, API integration, persistence restart, backup/restore and security.
- Vitest/Testing Library: accessible forms, states and API mapping.
- Cargo checks: desktop lifecycle compilation.
- Playwright: packaged/development critical flow once desktop orchestration is stable.
- Later: adapter contracts, SSRF corpus, AI golden set, scale benchmarks and clean-machine packaging.

## 13. Windows packaging plan

Use Tauri's Windows bundling architecture. During development the host starts Python from the repository; Stage 0 must choose and prove a bundled Python sidecar (for example a PyInstaller executable), version compatibility, signing-capable MSI/NSIS output, controlled shutdown and clean-profile installation. A plain local web launcher is the documented fallback if sidecar packaging proves disproportionate.

## 14. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Python sidecar packaging | Thin Tauri lifecycle spike; bundle executable before packaging gate; retain local-web fallback. |
| Active SQLite backup corruption | Use SQLite backup API and integrity/checksum manifest. |
| Local API exposure | Fixed loopback binding plus ephemeral token and restricted origins. |
| Scope expansion | Stage gates and explicit deferred register. |
| Provider/legal uncertainty | Disabled flags, mocks/manual fallbacks and review gates. |
| Dropbox-synchronised workspace locking | Keep SQLite transactions short; production data path must be local AppData, not the source tree or sync folder. |

## 15. Dependencies and credentials required

The local core needs Python 3.13, `uv`, Node/npm, Rust/Cargo, WebView2 and Windows build tools. No credentials are required for Stages 0–2 using mocks. Later provider credentials, Google billing limits, AI data-processing selection, Zoho developer app details, sender identity, privacy wording and an approved backup location are business dependencies.

## 16. Explicit deferred scope

Meta/Facebook discovery beyond the bounded official Instagram professional-account path, all Meta messaging, direct Zoho sending, unattended sequences, Shopify sync, multi-user/RBAC, UK-wide optimisation, local AI, learning scoring, mobile, quote builder, full revenue attribution, referrals and autonomous commercial promises are deferred.

## 17. First coding increment outcome

Verified: desktop lifecycle starts and stops the backend; authenticated local health works; migration runs; campaigns and manual leads with source attribution are stored and displayed; audit and initial stage events exist; reopen preserves data; SQLite-consistent backup can be verified and restored to an isolated location; the packaged host starts its bundled Python backend. Rollback remains removal of the new greenfield source and disposable test data only; no pre-existing user data was changed.

## 18. Stage 1 local operations outcome

Verified in source development mode: campaign edit/pause/resume/duplicate/search; evidence-backed manual lead entry and filtering; all required pipeline stages and history; opportunity values and lost reasons; mock-up/sample/quote statuses; notes; dated typed follow-ups and completion; manually recorded communications with sent confirmation and reply status; chronological timelines; suppression enforcement and lifting; privacy deletion with minimal suppression evidence; JSON/CSV export; configurable operating defaults; diagnostics; dashboard queues; and backup creation/verification.

The acceptance flow used a disposable database and no external services. CSV import was intentionally skipped. Provider discovery, AI, unattended automation, outbound sending, and installer generation remain outside this increment.

## 19. Stage 2 qualification outcome

Implemented the first bakery-segment qualification slice: an editable catalogue, bounded Shopify product-export CSV upload, versioned deterministic score profiles and runs, seven visible evidence/missing-data explanations, rule-based product recommendations, manual score overrides with reasons, and weekly campaign shortlists. Shortlists respect campaign capacity, active suppression, pipeline eligibility, score threshold, recency, prior recommendations, and explicit defer/dismiss/replace decisions.

The Shopify CSV is used only to seed or refresh local catalogue records by product handle; variants are collapsed and the raw upload is not retained. This does not enable Shopify API synchronisation. Lead CSV import is still intentionally absent. The acceptance gate is backend/frontend automation plus a real-browser local workflow against disposable data, with no external requests, AI inference, sending, or installer work.

## 20. Campaign execution and controlled discovery outcome

Implemented the recommended sequences in campaign order. A per-campaign or all-active button creates durable campaign runs, processes every eligible campaign lead, calculates only changed score inputs, snapshots deterministic product matches, and prepares the current-week shortlist without replacing an existing operator list. Run status, phases, warnings, counters, cancellation and history are visible in the Campaigns workspace.

Implemented optional Google Places Text Search (New) discovery with Geocoding v4 campaign centring, exact radius post-filtering, bounded queries/results and selected response fields. Provider results are staged as candidates, exclusion and suppression controls run before promotion, exact duplicates link automatically, and high-confidence fuzzy matches wait for operator review. Public-homepage enrichment applies public-IP DNS, redirect, robots, MIME, byte and timeout controls and stores only normalised evidence. Missing credentials or provider failures fail closed while existing-lead scoring continues.

The assisted Meta sequence is now implemented: campaign-generated Instagram/Facebook searches lead to an operator-verified capture form, canonical social/contact storage, provider/social/website/phone/email/name deduplication and immediate scoring, product matching and shortlist eligibility. Website enrichment now checks home plus at most two safe same-domain contact/about pages.

The official Instagram sequence is implemented for app-role testing: DPAPI-protected Meta OAuth, Page/professional-account selection, profile URL preview/import, bulk saved-handle refresh, Business Discovery, website/contact enrichment, cross-run deduplication and the same deterministic qualification pipeline. Campaign-derived hashtag links assist the operator in selecting profiles because Meta does not expose a dependable author identity from hashtag media. It does not scrape, access consumer profiles, verify an exact social radius or send messages.

The Stage 3 remainder is unattended scheduling, general-purpose leased jobs/retries, provider budgets/kill switch and richer merge tooling. AI evidence packets, message recommendations and draft approval remain Stage 4; no AI inference or outbound message is enabled by these sequences.
