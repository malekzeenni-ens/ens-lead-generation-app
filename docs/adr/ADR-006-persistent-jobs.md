# ADR-006: SQLite-backed persistent jobs

- **Status:** Accepted
- **Context:** Discovery, enrichment and AI work must survive application shutdown and avoid duplicate external calls.
- **Decision:** Store jobs, leases, attempts, checkpoints, idempotency keys and retry classifications in SQLite; Task Scheduler may only wake the runner.
- **Alternatives considered:** In-memory timers; Windows Task Scheduler as state; Redis/Celery.
- **Consequences:** A local polling worker is required before scheduled external work is enabled.
- **Security/compliance impact:** Uncertain non-idempotent actions require reconciliation; suppression/policy failures are never automatically retried.
- **Rollback/migration:** Disable schedules and process jobs manually; job records remain auditable.

