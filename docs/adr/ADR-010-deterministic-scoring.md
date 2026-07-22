# ADR-010: Deterministic versioned scoring

- **Status:** Accepted
- **Context:** Numeric scores must be explainable, reproducible and not depend on AI invention.
- **Decision:** Versioned rules calculate every point from evidence IDs or explicit missing state; AI may narrate but not set the authoritative score.
- **Alternatives considered:** AI-assigned score; opaque statistical model; manual-only rating.
- **Consequences:** Rule calibration and golden tests are required; manual overrides preserve original score and reason.
- **Security/compliance impact:** Reduces discriminatory/unsupported automated decisions and makes prospecting rationale auditable.
- **Rollback/migration:** Retain historical executions by version; introduce new versions without rewriting results.

