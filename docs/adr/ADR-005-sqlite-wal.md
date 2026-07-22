# ADR-005: SQLite WAL persistence

- **Status:** Accepted
- **Context:** The MVP is single-user with up to 10,000 leads and 100,000 activities.
- **Decision:** Use SQLite WAL, foreign keys, busy timeout, short transactions, explicit indexes and Alembic migrations.
- **Alternatives considered:** PostgreSQL; embedded document database; plain JSON files.
- **Consequences:** Simple local ownership and backup; write concurrency remains intentionally bounded.
- **Security/compliance impact:** Production data belongs in user-local AppData with Windows ACLs, not the synced source tree; SQLite is not treated as encrypted storage.
- **Rollback/migration:** Repository boundaries and migrations support later PostgreSQL migration.

