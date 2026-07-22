# ADR-002: Modular monolith

- **Status:** Accepted
- **Context:** The single-user MVP has broad domains but no need for distributed deployment.
- **Decision:** Deploy one modular application service and database with explicit domain/service/repository/adapter boundaries.
- **Alternatives considered:** Microservices; unstructured single module.
- **Consequences:** Low operations overhead; internal dependencies require discipline and architecture tests/review.
- **Security/compliance impact:** Fewer network boundaries and one audit/control surface reduce exposure.
- **Rollback/migration:** Stable module ports permit later extraction if scale or multi-user requirements justify it.

