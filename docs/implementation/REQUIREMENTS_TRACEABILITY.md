# Requirements traceability

Status values: `planned`, `in progress`, `implemented`, `verified`, `deferred`, `blocked`.

## First vertical slice

| Requirement | Status | Implementation evidence | Verification evidence |
|---|---|---|---|
| FR-001 Create campaign | Verified | Campaign schema/service/repository/API/UI | API flow and frontend submission tests |
| FR-005 Campaign validation | Verified | Strict Pydantic/domain/database constraints | Invalid-input integration tests |
| FR-010 Manual lead entry | Verified | Lead service/API/UI | Create/list/detail and reopen test |
| FR-031 Source evidence | Verified | `source_system` + separate `source_observation` | Observation values/source queried after create |
| FR-032 Information classification | Verified | Observation classification enum | Schema validation/integration assertion |
| FR-113 Activity timeline foundation | Verified | Initial stage and audit events | Transactional event assertions |
| FR-160 Source attribution | Verified | Required source and collection time | Lead creation integration test |
| DR-001 Lead | Verified | `lead` table/model | Migration/API tests |
| DR-002 Campaign | Verified | `campaign` table/model | Migration/API tests |
| DR-003 Source evidence | Verified | Source system/observation models | Migration/API tests |
| DR-009 Pipeline event | Verified | Initial `lead_stage_event` | Integration test |
| DR-012 Audit event | Verified | Append-only campaign/lead audit service | Integration test |
| SEC-001 / NFR-A05 Local access | Verified | Literal loopback binding, random per-run token, restricted CORS | Backend auth/host tests, Rust and packaged smoke |
| SEC-003 Secret management (local slice) | Verified | No provider secret fields/env-file loading; session token generated in memory | Source review and ignored env policy; OS vault remains a pre-integration gate |
| SEC-005 Input validation | Verified | Pydantic schemas and database/domain checks | Invalid-input tests |
| SEC-009 Audit logging | Verified | Correlated campaign/lead audit records | Integration test |
| NFR-001 Local-first | Verified | No external provider runtime dependency | Core integration and packaged smoke |
| NFR-004/005 Reliability | Verified | Short transactions, constraints, restart persistence | Reopen and rollback integration paths |
| NFR-009 Observability | Verified | Health, correlation IDs, safe rotating logs | API tests/manual log review |
| NFR-010 / NFR-A07 Backup | Verified | SQLite backup, manifest, integrity/checksum, isolated restore | Backup/tamper/restore tests |
| NFR-011 Port management | Verified | Tauri selects an ephemeral loopback port and waits/fails closed | Rust lifecycle and release-host smoke |
| NFR-012 Windows | Verified for increment | Windows scripts, PyInstaller sidecar, Tauri NSIS output | Sidecar smoke, Cargo gates, installer build |
| Universal design system | Verified for current workflow | Desktop shell, semantic tokens, reusable primitives, Lucide icons, operational records, shared accessible pagination and responsive states | 13 frontend tests, keyboard review and responsive browser checks; see `DESIGN_SYSTEM_REVIEW.md`, `STAGE1_LOCAL_WORKFLOW_REVIEW.md` and `STAGE2_QUALIFICATION_REVIEW.md` |

## Stage 1 local operations

| Requirement | Status | Implementation evidence | Verification evidence |
|---|---|---|---|
| FR-002 Edit campaign | Verified | Campaign PATCH service/API and inline editor retain memberships | Backend campaign operation test and browser edit workflow |
| FR-003 Pause/resume campaign | Verified | Audited active/paused status updates | Backend test and real-browser pause/resume workflow |
| FR-004 Duplicate campaign | Verified | Duplicate service copies configuration with a unique name | Backend test and UI workflow coverage |
| FR-090–095 Pipeline/opportunity | Verified | All 17 stages, stage events, values, recurrence and lost reasons | Backend operation tests; browser stage/value/status workflow |
| FR-100–104 Follow-ups | Verified | Typed dated follow-ups, dashboard buckets, completion and no sequence runner | Backend suppression/follow-up tests; frontend and browser workflows |
| FR-110–113 Communications | Verified | Manual communication records, sent confirmation, reply status and unified timeline | API invariant tests and real-browser manual-send confirmation |
| FR-120–123 Commercial tracking | Verified | Mock-up, sample and quote status fields/API/UI | Backend update test and browser workflow |
| FR-130 Analytics | In progress | Operational campaign/lead/follow-up/review counts and grouped pipeline summary | Dashboard API/frontend/browser tests; conversion and revenue analytics remain Stage 5 |
| FR-137 Analytics export | Planned | Lead/activity export exists, but dedicated analytics export does not | Stage 5 analytics gate |
| FR-140–143 Navigation/dashboard/search | In progress | Stage-appropriate primary navigation, operating queue, campaign/lead/catalogue/pipeline filters and accessible pagination for every unbounded register | 13 frontend tests and high-volume responsive browser review; scoring/source/follow-up filters await owning stages |
| FR-161–162 Suppression/objection | Verified | Active suppression forces Do Not Contact, cancels open follow-ups and blocks outreach actions | Backend invariants and browser cancellation/blocking workflow |
| FR-163 Privacy deletion | Verified | Personal lead graph is deleted while active minimised suppression hash survives | Backend privacy-deletion test |
| FR-164 Data export | Verified | Authenticated JSON/CSV lead and complete activity export with CSV formula protection | Backend export assertions and browser download workflow |
| FR-165 Retention review | Verified | Configurable default interval plus per-lead review date | Settings/update tests and browser settings workflow |
| FR-166 Data minimisation | Implemented | Local workflow stores only operational identity, evidence and activity fields | Schema/service review; legal review remains external |
| FR-167 Contact classification | Verified | Business/individual/unknown classification editable and visible | Creation/update tests and UI review |
| FR-168 Compliance warning | Verified | Unknown classification, review count and active suppression warnings | Frontend tests and browser review |
| Settings/diagnostics/backup controls | Verified | Authenticated settings, summary, diagnostics and backup create/verify APIs/UI | Backend tests and disposable real-browser acceptance flow |

## Stage 2 catalogue, qualification, and weekly shortlist

| Requirement | Status | Implementation evidence | Verification evidence |
|---|---|---|---|
| FR-040 Score calculation | Verified | Deterministic `ScoreRun` service/API produces a persisted 0–100 calculated and final score | Backend score workflow test and pipeline UI test |
| FR-041 Bakery scoring model | Verified | Seven bakery categories default to 25/20/20/15/10/5/5 and total 100 | Backend breakdown assertions and catalogue profile interface |
| FR-042 Score explanation | Verified | Every category records awarded points, evidence or explicit missing data, and an explicit null AI inference | API/domain tests and visible pipeline explanation panel |
| FR-043 Configurable weights | Verified for segment profiles | Catalogue scoring editor creates an immutable active profile version; campaign runs retain profile/version evidence | Backend version-history test and frontend type/lint/build gates |
| FR-044 Manual override | Verified | Score override requires a bounded score and non-empty reason while preserving the calculated score | Backend override test and pipeline interface test |
| FR-045 Disqualification | Verified | Existing `not_suitable` stage requires a reason through the pipeline service | Stage 1 pipeline tests; excluded from shortlist eligibility |
| FR-046 Segment-specific models | Implemented | Profiles are keyed and versioned by segment; `bakery` is the seeded operating profile | Repository/service review; additional segment defaults await their campaigns |
| FR-050 Product catalogue | Verified | Editable product model/API/UI covers required descriptive, segment, use-case, image, active, price, and sample fields | Shopify upsert/edit backend test and catalogue UI test |
| FR-051 Matching rules | Verified | Versioned deterministic segment/campaign product rules return reason and evidence | Backend score/shortlist tests |
| FR-052 AI-assisted product fit | Deferred | AI remains disabled; matches explicitly report `rule_based: true` | API response and UI label review |
| FR-053 Recommendation explanation | Verified | Product matches show why, source evidence, rule version, and rule-vs-AI status | Backend snapshots and pipeline/shortlist UI |
| FR-054 Recommendation override | Planned | Product records are editable, but per-lead add/remove/reorder/edit is not implemented | Stage 2 remainder |
| FR-055 Suggested offer | Deferred | No AI or offer generator is enabled | Optional later scope |
| FR-060 Weekly shortlist | Verified | Generator combines score, product fit, location/contact evidence, pipeline, freshness, history, suppression, campaign product categories, minimum score, and capacity | Backend qualification workflow test, frontend campaign mapping tests, and real-browser acceptance |
| FR-061 Shortlist size | Verified | Campaign create/edit interfaces configure shortlist size 1–50 and minimum score 0–100; generation applies the capacity clamp and threshold | Campaign validation, frontend create/edit tests, shortlist integration tests, and browser propagation review |
| FR-062 Recommendation reason | Verified | Every item persists and displays score/fit/local/contact/freshness reasons and product matches | API/frontend tests and browser acceptance |
| FR-063 Replace lead | Verified | Defer, dismiss, and replace actions are exposed and persisted | Backend action test and shortlist interface |
| FR-064 Capacity control | Verified | Approval beyond the effective campaign capacity is rejected with an operator-visible error | Backend capacity assertion and interface error path |
| FR-065 No duplicate recommendation | Verified | Recent recommendations are excluded for 28 days unless follow-up is due, deferred, or manually eligible | Backend repeat/suppression test |
| Shopify product CSV upload | Verified | Local file interface with readiness/progress feedback, 5 MB/10,000-row bounds, required header validation, variant collapsing and handle upsert; raw CSV is not retained | Backend/frontend tests plus supplied 589 KB export in Tauri: 840 rows, 123 products, zero skips, repeat-safe in under one second |

## Campaign execution and controlled discovery

| Requirement | Status | Implementation evidence | Verification evidence |
|---|---|---|---|
| FR-012 Area/sector discovery | Implemented for Google Places; assisted for Instagram | Google uses campaign keywords/location/radius with exact post-filtering. Instagram opens campaign location/sector hashtags for operator selection because Meta does not expose a dependable author identity from hashtag media | Mock-transport Google radius, direct Instagram hashtag-link UI test and live Meta contract diagnostics |
| FR-013 Discovery source control | Verified | Campaign create/edit exposes Google/Instagram selection only when the backend reports configured/connected capability; absent credentials fail closed | Frontend type/interaction checks and disabled-capability states |
| FR-014 Discovery evidence | Verified | Provider result is staged in `discovery_candidate`; selected provider fields and normalised observations are retained without raw payload/HTML | Promotion/link integration test and schema review |
| FR-015 Duplicate handling | Verified for exact/fuzzy gate | Provider ID, social handle, website host, phone, public email and exact normalised names link automatically; at least 94% fuzzy name candidates require operator link/promote/reject | Repeat Google and social capture tests prove one canonical lead; fuzzy review/rejection remains covered |
| FR-016 Safe website research | Implemented | Home plus at most two same-domain contact/about pages with public-IP DNS checks, redirect revalidation, robots, MIME/size/time limits and normalised contact/social evidence | Contact-page extraction plus private/reserved and malformed URL tests; adversarial corpus remains Stage 3 hardening |
| FR-018 Assisted social discovery | Verified | Campaign-generated direct Instagram hashtag links and Facebook public searches; Instagram requires only profile selection while Facebook retains verified manual capture; no authenticated scraping | Frontend browser-opening and separated-action tests |
| FR-019 Official Instagram enrichment | Implemented for app-role testing | DPAPI-protected Meta OAuth, Page/account selection, professional-profile preview/import, bulk saved-handle refresh, website enrichment and canonical provider/social deduplication; no scraping or messaging | OAuth/provider mock contracts, secret non-disclosure, preview/import/bulk integration and repeat-run one-lead assertion |
| FR-017 Campaign execution | Verified | Durable `campaign_run` state, one-at-a-time manager, startup resume, cancellation request, per-campaign and all-active APIs/UI | Bulk-run tests, browser execution and terminal status/history review |
| FR-040/051 automated refresh | Verified | Each run scores every eligible campaign lead, fingerprints inputs, reuses unchanged results and snapshots rule-based product matches | Three-run idempotency test proves score reuse and one current-week shortlist |
| FR-060 automated shortlist preparation | Verified | Run creates the current-week capacity/threshold-controlled shortlist and preserves an existing shortlist | Campaign-run integration test |

## Delivery backlog mapping

| Requirements | Stage | Status |
|---|---:|---|
| FR-002–004 campaign update/pause/duplicate/search | 1 | Verified |
| FR-011 CSV import | 1 | Deferred by user direction; intentionally skipped |
| FR-090–113 pipeline, notes, follow-ups and communications | 1 | Verified |
| FR-120–123 commercial statuses | 1 | Verified |
| FR-161–168 compliance operations | 1–4 | Local controls verified; professional legal review remains a release dependency |
| FR-020–035 remainder | 2 | Planned |
| FR-040–065 | 2 | Qualification slice verified; FR-052/054/055 remain deferred/planned as listed above |
| FR-012–019 controlled discovery | 3 | Google, official Instagram and assisted social paths implemented and tested; scheduling, budgets and real credential pilots remain |
| FR-070–080, FR-150–157 | 4 | Planned |
| FR-130–143 | 5 | In progress; local operational subset implemented |
| INT-001–007 Zoho | Phase 2 | Deferred |
| Meta messaging/broader Facebook discovery, Shopify API sync, multi-user, local AI and other explicit exclusions | Later/none | Deferred; bounded official Instagram discovery and local Shopify product-export CSV import are verified in source |

No requirement is implied complete by the earlier installer proof. The Stage 1, Stage 2 qualification, and operator-triggered automation increments were developed and verified without rebuilding an installer.
