# Stage 3 operator-triggered automation review

**Date:** 19 July 2026  
**Scope:** Campaign execution, deterministic bulk qualification, controlled Google discovery boundary and duplicate review  
**Data:** Disposable SQLite database only

## Outcome

The Campaigns workspace can start one campaign or all active campaigns. A run persists its batch, trigger, phase, provider state, counters, safe warnings/errors, candidates, attempts, cancellation request and timestamps. Eligible leads are scored against their campaign, rule-based product matches are snapshotted, unchanged inputs are reused, and the current-week shortlist is prepared once.

Google discovery is disabled unless the backend has a key and the campaign explicitly selects the source. The contract test verifies official request shape, selected fields and exact radius post-filtering without using a paid credential. Provider results are staged before promotion, exact duplicates link, ambiguous fuzzy names require review, active suppression blocks promotion, and raw provider responses/homepage HTML are not retained.

## Automated evidence

- Backend: 19 tests passed.
- Frontend: 14 interaction tests passed without coverage instrumentation; strict TypeScript and ESLint passed.
- Production frontend build passed.
- Provider contract: geocoding centre plus text search, inside-radius result retained and outside-radius result rejected.
- Website boundary: private/reserved and malformed URL cases rejected.
- Idempotency: third unchanged campaign run created zero new score runs; repeat execution retained one current-week shortlist.

## Browser evidence

Using the `agent-browser` workflow against Vite plus an authenticated backend and disposable database:

- Campaign form exposed keywords, exclusions and a disabled Google option with a configuration explanation.
- Campaign creation persisted through the real API.
- **Refresh scoring** returned an accepted durable run and the UI showed `completed with warnings`, `phase completed`, zero-result counters and the existing-leads-only warning.
- The browser reported no page errors or application console errors.
- Document width matched viewport width at 1366×768 and 720×600.

The screenshots were kept in the disposable local test directory rather than committed to the repository.

## Residual gates

- Exercise the Google adapter with the operator's restricted key, billing cap and agreed pilot query budget.
- Add general-purpose leases, retries, provider budgets and kill switch before unattended scheduling or multi-worker execution.
- Expand adversarial SSRF/rebinding and provider failure test corpora before production pilot use.
- AI inference, generated messages and all outbound sending remain disabled and require their own Stage 4 approval/evidence gates.
