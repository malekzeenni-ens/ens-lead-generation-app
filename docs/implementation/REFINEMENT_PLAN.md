# Refinement plan

**Plan date:** 17 October 2026
**Source:** Whole-codebase architecture review of `main` at `8608a65`.
**Delivery approach:** Tested vertical slices, smallest coherent increment first, as set out in `CONTRIBUTING.md`. Each work item lands as its own commit (or short series), passes `npm.cmd run quality`, and updates `DELIVERY_LOG.md`, `REQUIREMENTS_TRACEABILITY.md` and `CHANGELOG.md` where behaviour changes.

## 1. Summary

The application is in good shape: loopback-only API with a per-session token, DPAPI secrets, approval gates before anything leaves the machine, and 193 backend plus 112 frontend tests passing. The review found:

- one broken quality gate on `main`;
- four data-integrity or compliance defects (suppression bypass, over-eager duplicate linking, stranded campaign drafts, weekly outreach owned by the UI);
- reliability gaps in the desktop host and startup path;
- three structural issues that will limit growth (long AI work inside HTTP requests, business state read from the audit log, an all-in-memory frontend data layer);
- a set of small hardening items.

The work is grouped into six phases. Phases 0–2 fix defects and should be done first. Phases 3–4 are structural and can be scheduled when convenient. Phase 5 can be done in any gap.

| Phase | Theme | Items | Size |
|---|---|---|---|
| 0 | Green gate and faster tests | R0.1, R0.2 | S + S |
| 1 | Data integrity and compliance | R1, R2, R3, R4 | M + M + S + M |
| 2 | Startup and runtime reliability | R5, R6 | M + S |
| 3 | Backend structure | R7, R8, R9 | L + M + M |
| 4 | Frontend data layer | R10, R11 | L + L |
| 5 | Hardening | H1–H8 | S each |

Sizes: **S** is up to half a day, **M** is one to two days, **L** is three to five days.

## 2. Decisions required before starting

These change documented behaviour or add dependencies. Each has a recommendation; work on the affected item waits for a decision.

| ID | Decision | Affects | Recommendation |
|---|---|---|---|
| D1 | FR-015 currently says "exact normalised names link automatically". Should a name match with a *different* location still auto-link, or go to operator review? | R2 | Send it to review. "The Crown" in Luton and "The Crown" in Leeds are different businesses; a wrong auto-link merges their evidence, notes and outreach history. |
| D2 | Should audit events stop storing personal data (recipient email, names, message content), and should existing audit rows be scrubbed? | R8 | Yes to both. FR-163 promises the personal lead graph is deleted; audit summaries currently survive deletion with the recipient email in them. |
| D3 | Suppression will also hash phone, email, website host and social handle. Plain SHA-256 of a phone number can be reversed by brute force; a keyed hash (HMAC with a DPAPI-held key) cannot, but breaks backup portability to another machine. | R1 | Plain SHA-256 with a per-kind prefix, matching the existing name/location hash. The database is local and already holds far more sensitive data in clear. |
| D4 | Add `@tanstack/react-query` as a frontend dependency. | R11 | Yes. The existing `RefreshDomain` lists map directly onto its invalidation keys, so the migration is mechanical. |
| D5 | Weekly outreach should be scheduled by the backend while the app is running. Should it also run when the app is closed (Windows Task Scheduler)? | R4 | Not now. Running while open removes the current defect; closed-app scheduling is a separate feature with its own consent questions. |

## 3. Phase 0 — Green gate and faster tests

### R0.1 Restore strict mypy on `main` (S)

**Problem.** `uv run mypy app` fails with `no-untyped-call` at `apps/backend/app/domains/assistant/catalogue_answers.py:196-199`. The lambdas inside the tuple literal are untyped, so CI fails on every push.

**Change.**
- Hoist the pairs into a typed local:
  `renderers: list[tuple[list[str], Callable[[str], str]]] = [...]`, importing `Callable` from `collections.abc`.
- No behaviour change.

**Tests.** Existing `test_catalogue_answers.py` passes unchanged.

**Acceptance.** `npm.cmd run quality` passes locally; the GitHub `Quality` workflow is green.

### R0.2 Migrate once per test session (S)

**Problem.** The backend suite takes about 5 minutes for 193 tests. Every test builds a fresh database and runs all 16 Alembic migrations through `create_app`.

**Change.**
- In `apps/backend/tests/conftest.py`, add a session-scoped fixture `migrated_template` that runs `run_migrations()` once into `tmp_path_factory.mktemp("template") / "ens-leads.db"`.
- Change the `settings` fixture to copy that file (plus any `-wal`/`-shm`) into `tmp_path / "data"` before returning.
- `create_app` still calls `run_migrations`, which becomes a fast no-op at head, so production code is unchanged.
- Leave tests that deliberately start from an older schema (for example in `test_outreach_drafts.py`) on their own paths.

**Tests.** Full suite passes. Record before and after timings in the delivery log.

**Acceptance.** Suite runtime under 2 minutes on the development machine, with no test changed except fixtures.

## 4. Phase 1 — Data integrity and compliance

### R1 Suppression covers every identifier (M) — FR-161, FR-163

**Problem.**
- A suppression stores only `sha256(normalised name | location)` (`apps/backend/app/domains/leads/service.py:852`).
- Google candidates use the full formatted address as their location (`apps/backend/app/domains/automation/providers.py:211`), while a manually entered lead usually has a town name.
- So after a suppressed lead is privacy-deleted, a later Google run hashes differently and re-creates it.
- Phone, email, website and social handle are never checked against suppressions, in discovery or in manual create/update.

**Design.**
- New table `suppression_identifier`:
  - `id`;
  - `suppression_id` (FK to `suppression_record`, `ON DELETE CASCADE`);
  - `kind` (one of `name_location`, `name`, `website_host`, `phone`, `email`, `social`);
  - `value_hash` (64 characters);
  - index on `(kind, value_hash)`.
- Hash format: `sha256(f"{kind}|{normalised value}")`. Normalisation reuses the existing helpers:
  - `normalize_business_name`;
  - `phone_match_key`;
  - email lowercased;
  - website host lowercased without `www.` (move `_website_host` from `automation/service.py` into `leads/identity.py`);
  - social as `platform:handle`.
- New module `apps/backend/app/domains/leads/suppression.py`:
  - `identifier_hashes(name, location, website, phone, email, social_keys) -> set[tuple[str, str]]`;
  - `find_active_suppression(session, hashes, *, include_name_only: bool) -> SuppressionMatch | None`, which returns the record and the matched kind.
- Matching rules:
  - A strong identifier (`name_location`, `website_host`, `phone`, `email`, `social`) blocks creation outright.
  - A `name` match alone puts a discovery candidate into `review_required` with the reason "Name matches a suppressed business". It is not an automatic rejection, because names are not unique.
- Keep `suppression_record.identifier_hash` populated for compatibility; it holds the `name_location` value.

**Migration `0017_suppression_identifiers`.**
- Create the table.
- Backfill: for each suppression record, insert its existing `identifier_hash` as `name_location`. Where `lead_id` is still set, compute and insert the other kinds from the lead.
- Records whose lead is already deleted keep only `name_location`; this limitation is documented in `DATA_MODEL.md`.
- Take a verified backup before applying, per `CONTRIBUTING.md`.

**Call sites to change.**
1. `LeadService.suppress`: write all identifier rows.
2. `LeadService.lift_suppression`: identifiers follow the record's `active` flag. Query through the join and filter on `suppression_record.active`, so there is no duplicated flag.
3. `LeadService._assert_identifier_allowed`: check all strong identifiers on **create and update**. An update that adds a suppressed phone or email is refused.
4. `CampaignAutomationService._promote_candidate`: check before creating a lead (replacing the name/location-only check at `automation/service.py:569`), and apply the name-only review rule.

**Tests** (new `tests/test_suppression_identifiers.py`):
- Suppress "Crown Bakery, Leeds" with a phone number, delete it, then run mocked Google discovery returning the same phone with a formatted address. The candidate is rejected and the lead count is unchanged.
- The same scenario repeated for website host, public email and Instagram handle.
- A name-only match produces `review_required` with the stated reason.
- After lifting a suppression, the same candidate is promoted.
- A manual update adding a suppressed email returns `409 LEAD_IDENTIFIER_SUPPRESSED`.
- A migration test seeds a 0016 database with a suppression record, upgrades, and checks the backfilled rows.

**Acceptance.** No path creates or edits a lead to carry an identifier belonging to an active suppression. Traceability rows FR-161 and FR-163 are updated with the new evidence.

### R2 Duplicate matching ranks identifiers and respects location (M) — FR-015, needs D1

**Problem.**
- `_promote_candidate` (`apps/backend/app/domains/automation/service.py:535-550`) treats an equal normalised name as an exact duplicate whatever the location.
- It also stops at the first lead that matches anything, so a name match on lead A can win over a phone match on lead B further down the list.

**Design.**
- New pure module `apps/backend/app/domains/leads/matching.py`, with no database access:
  - `MatchKeys` dataclass: normalised name, locality, website host, phone key, email, social keys.
  - `match(candidate: MatchKeys, leads: Iterable[tuple[str, MatchKeys]]) -> MatchResult`, where `MatchResult` has `kind` (`exact`, `review`, `none`), `lead_id`, `reason` and `confidence`.
- Ranking, strongest first (provider record ID is already handled before matching):
  1. social handle;
  2. website host;
  3. phone key;
  4. public email;
  5. name **and** same locality;
  6. name with different or unknown locality → `review`;
  7. fuzzy name ratio ≥ 0.94 → `review`.
- The best rank across *all* leads wins; ties go to the most recently created lead.
- `locality(location)`:
  - If a UK postcode is present, use its outward code (regex on the formatted address).
  - Otherwise use the town token set, after stripping country names and street numbers.
  - Two localities match when the outward codes are equal, or when the shorter location's tokens all appear in the longer one.
- `_promote_candidate` builds `MatchKeys` for the candidate and leads, calls `match`, and acts on the result. The `force=True` path (operator chose "promote") is unchanged.

**Optional follow-up R2b (M, when lead count passes about 2,000).** Add indexed `lead.website_host` and `lead.phone_key` columns with a backfill migration. Matching then runs indexed lookups for the strong keys and only fuzzy-scans leads in the same segment, instead of loading every lead with its social identities (`AutomationRepository.candidate_leads`).

**Tests.**
- Table-driven unit tests for `match` and `locality`, covering each rank, tie-breaking, postcode versus town forms, and empty fields.
- Integration: two leads named "The Crown" in different towns. The second discovery candidate becomes `review_required`, not linked.
- Integration: a candidate whose name matches lead A and phone matches lead B links to B.
- Existing repeat-discovery tests (one canonical lead across re-runs) still pass.

**Acceptance.** FR-015's traceability row is reworded to the new rule and lists the new tests.

### R3 No campaign draft is left in "generating" (S)

**Problem.**
- `CampaignAssistantService.generate`, `message` and `decide_override` set a draft to `generating`, commit, and call the model. Only a `DomainError` marks the draft failed (`apps/backend/app/domains/campaign_assistant/service.py:174`).
- An unexpected exception, or the desktop host killing the backend mid-generation (`apps/desktop/src-tauri/src/lib.rs:32`), leaves the draft in `generating`.
- `generating` is not in `ACTIVE_DRAFT_STATUSES`, so the draft can never be edited again.
- `provider_attempt` rows have the same problem with `running`.

**Change.**
1. In all three methods, also catch `Exception`. Call `session.rollback()`, re-load the draft, then `_mark_failed`, then re-raise. Add the rollback to `_mark_failed` itself so a failed flush cannot block the status write.
2. Add `CampaignAssistantService.recover_interrupted(session) -> int`, which moves every `generating` draft to `generation_failed`. Call it from the FastAPI lifespan before `campaign_assistant_manager.start()`; nothing can be in flight at that point.
3. In the same lifespan step, mark `provider_attempt` rows still `running` whose run is not queued or running as `interrupted`.

**Tests.**
- Inject a manager whose `generate` raises `RuntimeError`. The draft ends `generation_failed` and the API returns 500 with the standard error shape.
- Seed a `generating` draft, start the app, and check it is now `generation_failed` and editable.

**Acceptance.** No reachable state leaves a draft uneditable.

### R4 Weekly outreach is scheduled by the backend (M) — FR-060, needs D5

**Problem.**
- Weekly runs are queued only when the frontend loads and calls `POST /campaign-runs/weekly/ensure` (`apps/frontend/src/App.tsx:366-375`).
- The backend lifespan only resumes runs that already exist.
- If the app stays open across the week boundary, or the UI fails to load, nothing is queued.

**Design.**
- New `apps/backend/app/domains/automation/scheduler.py` with a `WeeklyScheduler` that follows the `ProtectedApplicationMonitor` thread pattern:
  - On start, it calls `CampaignRunManager.queue_weekly_due()` once.
  - It then wakes every 15 minutes (`threading.Event.wait`) and calls it again when `current_week_start()` differs from the last week it handled.
  - It takes an injectable clock for tests.
- `CampaignRunManager.queue_weekly_due` gets a `threading.Lock`, so the scheduler and the endpoint cannot interleave.
- Database guarantee:
  - Migration `0018_weekly_run_unique` adds `UniqueConstraint("campaign_id", "week_start")` on `campaign_run`. SQLite allows many `NULL`s, so manual runs are unaffected.
  - The migration first checks for existing duplicates and aborts with a clear message rather than deleting anything.
- New setting `ENS_WEEKLY_SCHEDULER_ENABLED` (default `true`; `false` in `conftest.py`).
- Lifecycle: start the scheduler in the lifespan after `resume_incomplete()`, and stop it first on shutdown.
- Frontend: remove the startup `ensureWeeklyOutreach()` effect (`App.tsx:366-375`). Keep the endpoint, which is idempotent, for the existing manual action (`App.tsx:575`) and for tests.

**Tests.**
- Scheduler with a fake clock: no run before the boundary, exactly one per eligible campaign after it, and none repeated on later ticks.
- The endpoint and scheduler called concurrently produce one run per campaign per week.
- Migration test for the constraint, including the duplicate-abort path.

**Acceptance.** With the app left open from Sunday to Monday, Monday's runs appear without any UI action.

## 5. Phase 2 — Startup and runtime reliability

### R5 Startup errors are always recorded; the desktop host supervises the backend (M)

**Problem.**
- `create_app` runs migrations before logging is configured (`apps/backend/app/main.py:70-71`).
- The desktop host sends backend stdout and stderr to null (`lib.rs:111-113`, `160-162`), so a startup failure leaves no trace. The recent "app closes on launch" defect (`f11f683`) was this kind of failure.
- If the backend dies mid-session, nothing restarts it and the UI only shows "unavailable".
- Closing the app hard-kills the backend, so the lifespan shutdown never runs.

**Backend changes.**
1. In `create_app`, call `configure_logging` before `run_migrations`, and log a migration failure with its traceback before re-raising.
2. Stop Alembic's `fileConfig` replacing the application's handlers when migrations run in-process: set `config.attributes["configure_logger"] = False` in `run_migrations`, and have `migrations/env.py` skip `fileConfig` when that attribute is false.
3. In `cli.py serve`:
   - wrap startup in a handler that writes the exception to `<log_directory>/startup-error.log`;
   - build `uvicorn.Server(config)` explicitly and store it on `app.state.server`.
4. Add authenticated `POST /api/v1/system/shutdown`, which sets `app.state.server.should_exit = True` and returns 202.

**Desktop host changes (`lib.rs`).**
1. Redirect backend stderr to `%LOCALAPPDATA%\EtchNShine\LeadGeneration\logs\backend-stderr.log` (append mode) instead of `Stdio::null()`.
2. When setup fails, show a native message naming that log file before exiting. Use `tauri-plugin-dialog`, which is a new dependency; pin its version and add it to the capability file with only the message permission.
3. Supervisor thread:
   - poll `child.try_wait()` every 2 seconds;
   - on an unexpected exit, restart on the same port with the same token, at most 3 times in 5 minutes;
   - after that, emit a `backend-failed` event to the window.
4. On exit:
   - call `POST /system/shutdown`;
   - wait up to 5 seconds on `try_wait`;
   - only then kill.
   Interrupted campaign runs already resume at the next start; R3 covers drafts.

**Frontend changes.**
- In `api.ts`, a network `TypeError` becomes an `ApiError` with code `BACKEND_UNREACHABLE` (see H5).
- The app shows a "Reconnecting to the local service…" banner and retries health with backoff.
- On `backend-failed`, show a persistent error naming the log folder.

**Tests.**
- Rust: unit test for restart budget accounting. Extend the existing lifecycle test to call `/system/shutdown` and assert a clean exit within 5 seconds.
- Python: `create_app` with a deliberately broken migration writes the traceback to the log. The shutdown endpoint requires the session token.
- Manual: kill `python.exe` from Task Manager while the app is open; the app recovers within about 5 seconds.

**Acceptance.** Every startup failure leaves a readable log, and a backend crash does not require restarting the app.

### R6 Campaign-run failures leave no half-written work (S)

**Problem.** In `CampaignAutomationService.execute`, the `DomainError` branch commits without rolling back (`apps/backend/app/domains/automation/service.py:1372`). The generic `Exception` branch rolls back first (`:1379`). So a domain error during promotion can commit a lead without its campaign link, stage event or evidence.

**Change.**
1. Make the commit points explicit and documented: commit after each provider batch is staged, so evidence is retained, and after each phase transition.
2. Both failure branches roll back uncommitted work, re-load the run, and record the failure, sharing one helper `_fail_run(session, run_id, code, message)`.

**Tests.** Force a `DomainError` inside `_promote_candidate` after `session.add(lead)`. Afterwards the run is `failed`, no orphan lead exists, and earlier committed batches are intact.

## 6. Phase 3 — Backend structure

### R7 General background jobs for long AI work (L)

**Problem.**
- Several AI operations run inside one HTTP request. Lead autofill handles up to 20 leads, each with a website fetch and up to 120 seconds of model time (`apps/backend/app/domains/lead_assistant/service.py:142`), which can be well over half an hour.
- The frontend has no timeout or cancel (`apps/frontend/src/api.ts:82`).
- `CampaignRunManager` already shows the right pattern, but it is specific to campaign runs.

**Design.**
- New infrastructure package `apps/backend/app/jobs/`:
  - `models.py`: table `background_job` with `id`, `kind`, `status` (`queued`, `running`, `succeeded`, `failed`, `cancelled`, `interrupted`), `progress_current`, `progress_total`, `payload` (JSON), `result` (JSON), `error_code`, `error_message`, `cancellation_requested`, `created_at`, `started_at`, `completed_at`, and an index on `(status, created_at)`. Migration `0019_background_jobs`.
  - `manager.py`: `JobManager` with a single-worker executor, because AI work already serialises on the generation lock.
    - `register(kind, handler, *, resumable=False)`, where a handler is `(session, job, report_progress, should_cancel) -> dict`.
    - `submit(kind, payload) -> job_id`.
    - `cancel(job_id)`.
    - `recover()` at startup: `queued` jobs are re-submitted; `running` jobs become `interrupted` unless the handler is resumable.
  - Routes `apps/backend/app/api/routes/jobs.py`:
    - `GET /jobs/{id}`;
    - `GET /jobs?status=active`;
    - `POST /jobs/{id}/cancel`.
- Feature endpoints that move onto jobs return `202 {job_id}`, in this order:
  1. lead autofill (`LeadAssistantService.autofill_leads` becomes a handler that reports progress per lead and checks `should_cancel` between leads);
  2. catalogue enrichment runs;
  3. campaign draft generation (R3's failure handling moves into the handler).
- `CampaignRunManager` stays as it is; folding it into `JobManager` is a later, optional step.
- Frontend:
  - add a `useJob(jobId)` hook that polls every 1.5 seconds while the job is active, matching the existing campaign-run cadence;
  - add a shared progress-and-cancel component;
  - `api.ts` functions for moved endpoints return `{ job_id }`.
- Record the design as `docs/adr/ADR-022-background-jobs.md` and update `docs/architecture/JOB_DESIGN.md`.

**Tests.**
- Job lifecycle (success, failure, cancel between steps).
- Startup recovery marks running jobs interrupted.
- Autofill job with a stub manager reports progress `n/N`.
- The frontend hook test renders progress and cancel.

**Acceptance.** No request handler runs a model call longer than one interaction (assistant chat and single-draft refine stay synchronous), and every long operation shows progress and can be cancelled.

### R8 Business state lives in domain tables; the audit log holds no personal data (M) — FR-163, needs D2

**Problem.**
- Lead activity is rebuilt from audit-event JSON (`apps/backend/app/domains/audit/repository.py:43`, consumed at `leads/service.py:89`).
- `confirm_sent` refuses to proceed unless a specific audit event exists (`apps/backend/app/domains/outreach/service.py:856`).
- Audit summaries store `recipient_email`, and lead deletion leaves them behind.

**Design.**
- New table `outreach_activity`: `id`, `lead_id` (FK, `ON DELETE CASCADE`), `draft_id` (FK, `ON DELETE SET NULL`), `action`, `version`, `recipient_email`, `reason`, `created_at`, and an index on `(lead_id, created_at)`. It is written in the same transaction as the existing audit call in every outreach action listed in `OUTREACH_ACTIVITY_ACTIONS`.
- Add `outreach_draft.zoho_opened_at`. `confirm_sent` checks it instead of `audit_repository.has_event`.
- Lead activity reads `outreach_activity` (indexed, and cascades on delete). `AuditRepository.outreach_activity_events` is removed.
- Audit summaries become personal-data free:
  - they record IDs, versions, counts, enums and hashes only;
  - `record_audit_event` rejects summary keys on a denylist (`email`, `recipient_email`, `phone`, `first_name`, `last_name`, `subject`, `body`, `content`) with a `ValueError`, so a regression fails tests rather than leaking.
- Migration `0020_outreach_activity`:
  - create the table and column;
  - backfill both from existing audit events;
  - then scrub the denylisted keys from historical `audit_event.summary` rows.
  Take a verified backup first; the scrub is not reversible.

**Tests.**
- The activity timeline is identical before and after the migration on a seeded database.
- Deleting a lead removes its activity rows.
- `confirm_sent` works without any audit row present.
- `record_audit_event` raises on a denylisted key.
- A grep-style test asserts that no call site passes a denylisted key.

**Acceptance.** Deleting a lead leaves no personal data about it anywhere in the database except the minimised suppression hashes. The FR-163 evidence is updated.

### R9 Split the largest services without changing behaviour (M)

**Problem.** `automation/service.py` is 1,452 lines covering discovery, duplicate matching, enrichment evidence, Instagram import and candidate decisions. `leads/service.py` (1,090 lines) and `qualification/service.py` (1,147 lines) are similar.

**Change.** Pure moves, with `CampaignAutomationService` kept as the facade so routes and tests do not change:
- `automation/discovery.py`: provider orchestration (`_run_discovery_provider`, `_store_discovery_batch`, `_discover`, `_excluded`).
- `automation/promotion.py`: `_promote_candidate`, `_link_existing`, `_attach_evidence`, `_add_observation`, built on R2's `leads/matching.py`.
- `automation/social.py`: Instagram preview, import, bulk refresh and assisted capture.
- `automation/candidates.py`: `decide_candidate`.
- `leads/export.py` and the existing `leads/suppression.py` (from R1) take the export and suppression code out of `leads/service.py`.
- Qualification is left until it next needs feature work.

**Sequencing.** After R1 and R2, so their changes are not tangled with the move. Each module moves in its own commit with no logic edits.

**Acceptance.** The test suite passes unchanged at every commit, and no module exceeds about 500 lines.

## 7. Phase 4 — Frontend data layer

### R11 Server state through a query cache (L) — needs D4

Do this before R10, because pagination is much simpler once each view owns its own query.

**Problem.**
- `App.tsx` holds 32 pieces of state, loads 21 endpoints at startup, and reloads lists after every action through `perform(..., domains)`.
- One failed call in the startup `Promise.all` marks the whole app "unavailable" (`apps/frontend/src/App.tsx:315`).

**Design.**
- Add `@tanstack/react-query`, pinned to an exact version, and wrap the app in `QueryClientProvider` in `main.tsx`.
- New `apps/frontend/src/queries.ts`:
  - one hook per current `RefreshDomain` (`useCampaigns`, `useLeads`, `useProducts`, …);
  - query keys are named after the domains;
  - `perform` keeps its signature but calls `queryClient.invalidateQueries` for the listed domains instead of hand-written refreshers.
- Workspaces read their own data through hooks instead of props from `App`. Migrate one workspace per commit, starting with Settings (smallest), then Campaigns, Leads, Pipeline, Catalogue, Email drafts and Dashboard.
- Health becomes its own query. Per-query errors show inside the affected panel, and only a failed health check shows the global "unavailable" state.
- The active campaign-run poll becomes `refetchInterval` on `useCampaignRuns` while any run is queued or running.
- Tests: `App.test.tsx` and the component tests create a fresh `QueryClient` per test with `retry: false`. The existing API mocks keep working.

**Acceptance.** `App.tsx` holds only navigation and notification state. A failing products endpoint no longer hides leads.

### R10 Paged lead list with a slim response (L)

**Problem.** `GET /leads` returns every lead with nine eager-loaded relationships (`apps/backend/app/domains/leads/repository.py:19-29`), plus outreach events for all of them. That's fine for hundreds of leads, slow for thousands.

**Design.**
- Backend: `GET /leads?limit=50&offset=0&query=&stage=&campaign_id=&suppressed=&sort=` returns `{ items: LeadListItem[], total }`.
  - `LeadListItem` carries the fields list views use: id, business name, segment, location, stage, suppressed, contact classification, latest score and campaign, campaign names, next follow-up date, and updated time.
  - Only the relationships those fields need are loaded, and outreach activity is loaded for the page's IDs only.
  - `GET /leads/{id}` keeps the full `LeadRead`.
- Inventory first: before changing the response, list which `Lead` fields each consumer reads (Leads, Pipeline, Shortlist, Dashboard, Email drafts, Campaign register, assistant context) and confirm `LeadListItem` covers them. Anything that needs the full record fetches the detail.
- Pipeline board: per-stage counts from `GET /leads/summary-by-stage`, and each column loads its first 50 cards with "load more".
- Transitional compatibility: keep `GET /leads?view=full` for one release while consumers migrate, then remove it.
- Indexes: add `(pipeline_stage, created_at)` and `(created_at)` on `lead` if query plans show scans.

**Tests.**
- Backend: paging, totals, filters, and every filter combined with paging.
- A performance smoke test seeds 5,000 leads and asserts the first page returns in under 300 ms locally.
- Frontend: page controls and pipeline "load more".

**Acceptance.** Lead views stay responsive with 5,000 leads; the startup payload no longer grows with the lead count.

## 8. Phase 5 — Hardening

| ID | Item | Change | Test |
|---|---|---|---|
| H1 | Getter with a side effect | `CampaignAssistantManager.resource_profile()` writes `_protect_resources` (`campaign_assistant/manager.py:63`). Split it into a pure `profile_for(protect: bool)`; only `set_protection_enabled` mutates. Update callers in campaign assistant, lead assistant and outreach. | Existing manager tests, plus one asserting that reading the profile does not change protection. |
| H2 | DPAPI error codes | `secrets.py` uses `ctypes.windll`, so `get_last_error()` is always 0. Use `ctypes.WinDLL("crypt32", use_last_error=True)` and `WinDLL("kernel32", use_last_error=True)`, and declare `argtypes`/`restype` for `CryptProtectData`, `CryptUnprotectData` and `LocalFree`. | Windows-only test that unprotecting corrupted bytes raises `OSError` with a non-zero code. |
| H3 | Formula injection in generated CSV | Move the lead-export cell escaper (`leads/service.py:1088`) to `app/core/csv_safety.py`. In `AssistantFileStore.generated`, parse CSV output with the `csv` module and re-write it with escaped cells. | A generated CSV containing `=HYPERLINK(...)` comes back prefixed with `'`. |
| H4 | Opener permission too broad | `capabilities/default.json` allows `https://*` and `http://*`, which makes the specific entries pointless. Remove the redundant specific entries and `http://*`; the frontend upgrades `http://` lead websites to `https://` before opening, and shows the URL when the upgrade fails. | `cargo test`; manual check that lead websites, `mailto:`, `wa.me` and Instagram links still open. |
| H5 | Fragile error handling in `api.ts` | `rawRequest` assumes every error body is JSON and caches a rejected connection promise. Parse JSON defensively, falling back to `ApiError` with code `HTTP_<status>`; turn `fetch` `TypeError` into `BACKEND_UNREACHABLE`; reset `connectionPromise` on failure; treat `204` as no body; add an `AbortController` timeout (30 s default; jobs from R7 replace the long ones). | `api.test.ts` cases for HTML error bodies, network failure, 204 and timeout. |
| H6 | Cloud polish model settings | The default `claude-sonnet-5` (in `outreach/service.py` and `system/cloud_polish.py`) is previous-generation; `claude-sonnet-5-5` is the current Sonnet at the same price. Add it to `ALLOWED_CLOUD_POLISH_MODELS` (`system/schemas.py:7`), keeping `claude-sonnet-5` so saved settings stay valid, and change the default in one shared constant; the operator can still choose in Settings. These models think by default, so `max_tokens=2000` can truncate: add `"effort": "low"` to `output_config` beside `format` and raise `max_tokens` to 4000. Add an `anthropic.NotFoundError` branch returning `CLOUD_POLISH_MODEL_UNAVAILABLE` with a "choose another model in Settings" message. | Update `test_cloud_polish.py` for the default, the effort parameter and the not-found mapping. |
| H7 | Root folder clutter | `git mv` the eight prompt and requirements documents at the repository root into `docs/archive/` (keeping names), and update links in `README.md` and the docs. | Link check by grep. |
| H8 | Anthropic SDK major version | `pyproject.toml` pins `anthropic<1`; 1.x is published and moves to `httpx2`. Leave as is for now; schedule a separate upgrade increment when the pin blocks a needed feature. | None in this plan. |

## 9. Sequencing and dependencies

```
R0.1 ─┬─ R0.2
      │
      ├─ R1 ──┬─ R2 (after D1) ── R9
      │       │
      ├─ R3   │
      ├─ R4 (after D5)
      │
      ├─ R5 ── R6
      │
      ├─ R8 (after D2)
      ├─ R7 (uses R3's failure handling for drafts)
      │
      └─ R11 (after D4) ── R10

H1–H8: any time after R0.1; H5 before R5's frontend banner.
```

Suggested order: R0.1, R0.2, R1, R3, R2, R4, R5, R6, H1–H6, R8, R7, R9, R11, R10, H7.

Migration numbering follows that order: `0017` (R1), `0018` (R4), `0019` (R7), `0020` (R8). If the order changes, renumber before merging; never rewrite an applied revision.

## 10. Definition of done (every item)

- `npm.cmd run quality` passes, including strict mypy, Ruff, ESLint, TypeScript, Vitest, pytest, rustfmt, Clippy and the dependency audits.
- New behaviour has tests that fail before the change.
- Schema changes are made only through Alembic, are tested from the previous revision, and destructive steps (R8's scrub) are preceded by a verified backup and documented recovery steps.
- `REQUIREMENTS_TRACEABILITY.md` is updated for FR-015 (R2), FR-060 (R4), FR-161/FR-163 (R1, R8) and NFR-010 (R5).
- New ADRs: ADR-022 background jobs (R7); ADR-023 suppression identifiers and audit data minimisation (R1, R8).
- `DELIVERY_LOG.md` entry with verification results, and a `CHANGELOG.md` line for user-visible changes.
- For desktop-host changes (R5, H4): `desktop:dev` launched and the recovery scenario checked manually, with the result recorded.

## 11. Risks

| Risk | Mitigation |
|---|---|
| R1's backfill can't recover phone, email or website for leads already deleted. | Documented limitation; their name/location hash still applies, and R2's name-only review catches most re-discoveries. |
| R2's locality rule sends genuine duplicates to review when addresses are formatted very differently. | Review is the safe failure mode; track the review count in run metrics and tune `locality` with real examples. |
| R8's scrub is irreversible. | Verified backup before migration; backfill and comparison test before the scrub step in the same migration. |
| R11 and R10 touch most of the frontend. | One workspace per commit; transitional `?view=full`; the large existing `App.test.tsx` suite guards behaviour. |
| R5's same-port restart can fail if another process takes the port. | After a failed bind, fall back to the `backend-failed` event and its message rather than retrying indefinitely. |
