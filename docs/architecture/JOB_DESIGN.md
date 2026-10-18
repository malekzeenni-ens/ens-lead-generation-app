# Persistent job design

**Status:** Operator-triggered and backend-scheduled weekly campaign runs implemented; general background jobs for long local AI work implemented (ADR-022); operating-system scheduling, leases, general retry queues and budgets remain planned

## Background jobs (ADR-022)

`background_job` holds long local AI work started from the UI: lead autofill and catalogue enrichment. One worker thread runs them; each reports progress (committed, so finished work survives a cancellation), checks for cancellation between steps, and waits its turn for the shared model lock while interactive requests keep failing fast. The API returns the job with `202`; `GET /jobs/{id}`, `GET /jobs?active=true` and `POST /jobs/{id}/cancel` follow it. At startup, queued jobs are requeued and running ones marked `interrupted`.

`campaign_run`, `discovery_candidate`, and `provider_attempt` now persist the requested work, phase, progress counters, candidate evidence, safe failures, cancellation request, and terminal outcome. A single-process worker executes one run at a time and resumes queued/running records after application restart. It supports explicit buttons plus an idempotent current-week check that a backend scheduler thread repeats every 15 minutes while the app runs (`ENS_WEEKLY_SCHEDULER_POLL_SECONDS`), serialised with the manual action. Weekly runs execute campaigns sequentially and expose campaign-level retry, but the app cannot run while closed and this is not the full leased job design below.

Each current run follows `queued → discovery → qualification → shortlist → completed`, with `completed_with_warnings`, `failed`, and `cancelled` terminal variants. Active duplicate runs for one campaign are rejected, all-active execution uses a shared batch ID, and cancellation is checked between bounded units of work. Score input fingerprints make unchanged lead/campaign/profile/catalogue combinations reusable.

## Planned general-purpose records

- `job`: type, schema-versioned payload reference, status, priority, idempotency key, campaign, budget class, created/available/lease times, cancellation and terminal reason.
- `job_attempt`: job, attempt number, start/end, worker instance, provider correlation ID, outcome class, safe error summary, retry time.
- `provider_budget`: provider/campaign/day counters, reserved and consumed units, limit and reset time.

Payloads will contain internal IDs and bounded parameters, not plaintext credentials or unbounded provider responses.

## State machine

```text
pending ──lease──► running ──success──► succeeded
   ▲                 │
   │                 ├──retryable──► retry_wait ──due──┘
   │                 ├──policy/budget──► blocked
   │                 ├──terminal──► failed
   │                 └──operator──► cancelled
   └──── stale lease recovery ────────
```

Transitions are transactional and audited. Workers acquire expiring leases; a crashed worker cannot leave permanent `running` work. Idempotency keys prevent duplicate provider effects. Retry schedules use bounded exponential backoff with jitter and a maximum-attempt policy. Policy, authentication, validation, and budget errors are not blindly retried.

## Operator controls and recovery

The UI must show pending/running/retrying/blocked/failed states, last safe error, next attempt, budget state, pause/resume, retry, and cancel. Startup reclaims only expired leases. Provider calls must use connect/read deadlines and cancellation where supported. A global external-work kill switch and per-provider/campaign budgets are mandatory before the first real adapter is enabled.

## Verification gate

The current integration suite proves run persistence, all-active filtering, unchanged-score reuse, shortlist idempotency, scheduled week idempotency, week-boundary rollover with the app open, scheduler/endpoint races and catch-up, campaign failure isolation/retry, cross-campaign lead deduplication, weekly draft caps, provider normalisation/radius filtering, exact and fuzzy duplicate handling, candidate decisions, suppression-safe promotion, and SSRF blocking. Before operating-system scheduling is enabled, contract tests must additionally prove multi-worker lease exclusivity, retry classification, budget reservation/release and kill-switch behavior. Suppression and approval are already rechecked immediately before the existing assisted email handoff.
