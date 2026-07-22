# ADR-009: Assisted Instagram/Facebook workflow

- **Status:** Accepted and retained as the fallback to official Instagram discovery
- **Context:** Official Meta interfaces are not a comprehensive local-prospect index and authenticated automation creates policy risk.
- **Decision:** Campaign-generated public searches, external profile opening, verified manual capture, canonical Instagram/Facebook identities, cross-source duplicate checks and immediate deterministic qualification remain available where Meta's official API cannot expose a profile. Copy and manual sent confirmation remain the only outreach path.
- **Alternatives considered:** Browser automation; scraping; official API dependency.
- **Consequences:** More user effort but predictable, policy-aware operation.
- **Security/compliance impact:** No automated login, extraction, scrolling or DM; social DMs remain subject to outreach controls.
- **Rollback/migration:** Feature can be removed without loss of canonical lead data; future official APIs require a new ADR/spike.
