# ADR-012: Advisory, schema-validated AI

- **Status:** Accepted
- **Context:** AI can reduce research/drafting effort but may hallucinate facts and commercial promises.
- **Decision:** Use minimised evidence packets, stable evidence IDs, versioned prompts, structured schema validation, prohibited-claim checks, usage records and human review.
- **Alternatives considered:** Free-form completion; provider-specific logic; no AI.
- **Consequences:** Validation failures are visible and manual workflows must remain complete.
- **Security/compliance impact:** No AI output mutates canonical, score, approval or communication truth without explicit validated workflows.
- **Rollback/migration:** Disable the AI feature flag and keep deterministic/manual operations.

