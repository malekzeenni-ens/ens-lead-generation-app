# ADR-011: Separate canonical and observed data

- **Status:** Accepted
- **Context:** Providers and users can supply conflicting, time-varying facts with different retention rules.
- **Decision:** Store observations/evidence independently and resolve canonical fields through precedence, freshness, confidence or explicit user decisions.
- **Alternatives considered:** Last-write-wins canonical fields; raw provider blobs only.
- **Consequences:** More tables and resolution workflows, but complete provenance and safe provider-data deletion.
- **Security/compliance impact:** Classifications prevent suggestions/inferences being displayed as verified facts and support data minimisation.
- **Rollback/migration:** Canonical records remain usable if an observation source is disabled or removed.

