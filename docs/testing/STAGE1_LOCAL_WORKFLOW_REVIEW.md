# Stage 1 local workflow review

**Review date:** 18 July 2026  
**Scope:** Source development workflow only; CSV import, external providers, AI, outbound sending, and installer generation excluded.

## Result

Pass. The frontend and authenticated FastAPI service completed the local operating workflow against a disposable SQLite database. No production data or external service was used.

## Exercised workflow

1. Created a Luton bakery campaign, then paused and resumed it.
2. Added an evidence-backed manual lead.
3. Moved the lead from New to Qualified with a recorded reason.
4. Recorded estimate and quote values, recurrence, and mock-up/sample/quote statuses.
5. Added a note and dated email follow-up.
6. Recorded a manually sent email only after explicit user confirmation, then completed the follow-up.
7. Updated the retention setting, exported CSV, created a SQLite backup, and verified its checksum/schema/integrity evidence.
8. Created another follow-up and recorded an unsubscribe. The system moved the lead to Do Not Contact, cancelled the open follow-up, and disabled stage changes and new follow-ups.

## Interface checks

- Responsive views checked at 1366×768 and 720×600.
- No horizontal document overflow at either width.
- Workspace changes reset the active scroll container to the top.
- Compact navigation, labelled controls, disabled states, status text, activity timeline and suppression warning remained accessible in the browser snapshot.
- Browser console contained Vite connection and React development notices only; no application errors were reported.

## Evidence

- `screenshots/stage1-dashboard-1366x768.png`
- `screenshots/stage1-dashboard-720x600.png`
- `screenshots/stage1-pipeline-1366x768.png`
- `screenshots/stage1-pipeline-720x600.png`
- Backend: 11 tests passed, 93% statement coverage.
- Frontend: 7 tests passed, 68.23% aggregate coverage.

The browser review prompted one implementation correction: switching workspaces now resets both the desktop main scroll container and the compact document scroll position.
