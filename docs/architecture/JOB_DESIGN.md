# Persistent job design

**Status:** Operator-triggered durable campaign-run subset implemented; scheduling, leases, retry queues and budgets remain planned

`campaign_run`, `discovery_candidate`, and `provider_attempt` now persist the requested work, phase, progress counters, candidate evidence, safe failures, cancellation request, and terminal outcome. A single-process worker executes one run at a time and resumes queued/running records after application restart. This supports explicit button-triggered work; it is not an unattended scheduler or the full leased job design below.

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

The current integration suite proves run persistence, all-active filtering, unchanged-score reuse, shortlist idempotency, provider normalisation/radius filtering, exact and fuzzy duplicate handling, candidate decisions, suppression-safe promotion, and SSRF blocking. Before unattended scheduling is enabled, contract tests must additionally prove multi-worker lease exclusivity, retry classification, budget reservation/release, kill-switch behavior, and suppression re-check immediately before each external side effect.
