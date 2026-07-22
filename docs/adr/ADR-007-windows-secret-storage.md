# ADR-007: Windows-native secret storage

- **Status:** Accepted and implemented with user-scoped Windows DPAPI
- **Context:** Later integrations require API keys/OAuth tokens that must not enter source, frontend storage, logs or SQLite plaintext.
- **Decision:** Use Windows Credential Manager or a DPAPI-protected vault behind an application-owned secret-store interface; store references only in SQLite.
- **Alternatives considered:** `.env` files; database encryption field; cloud vault.
- **Consequences:** Windows-specific adapter and tests are required before credential features are enabled.
- **Security/compliance impact:** Secrets inherit OS user protection and must be redacted from diagnostics.
- **Rollback/migration:** Delete vault entries and references; replace the adapter without domain schema changes.
