# ADR-008: Policy-aware Google/provider data handling

- **Status:** Accepted
- **Context:** Business-directory results have field, billing, attribution, caching and storage constraints.
- **Decision:** Use a provider-neutral adapter, minimal search field masks, detail calls only after selection, pre-run estimates, durable provider IDs and separate observations/canonical facts.
- **Alternatives considered:** Scraping maps/search; mirroring full provider records; manual-only discovery.
- **Consequences:** Provider policy metadata and manual fallback are first-class. No live adapter is part of the first increments.
- **Security/compliance impact:** Prevents unauthorised scraping and uncontrolled replication/cost.
- **Rollback/migration:** Disable the feature flag and retain independently verified canonical business records.

