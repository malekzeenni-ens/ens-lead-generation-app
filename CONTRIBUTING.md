# Contributing

Work in the smallest coherent increment. Identify requirement IDs, migration impact, security/compliance/data-loss risks, tests and rollback before implementation. Use Alembic for every schema change and the SQLite backup service before destructive migrations.

Required checks for the current increment are documented in `docs/testing/TEST_STRATEGY.md`. Never weaken assertions or suppress a failing gate without a recorded defect and removal condition.

