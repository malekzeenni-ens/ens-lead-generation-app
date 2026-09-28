# Cloud draft polish implementation handover

**Handover date:** 28 September 2026

**Status:** Implemented and automated checks passed; operator-only acceptance remains.
**Specification:** [Cloud Draft Polish Specification](../specifications/Cloud_Draft_Polish_Specification.md)

## What shipped

The app can optionally polish the subject and body in one outreach draft using Anthropic. The feature defaults off, requires a key saved in the existing protected `SecretStore`, and runs only after an operator clicks **Polish with cloud AI**. The result replaces editor contents only. The regular draft edit/save/approval path still owns persistence and approval.

The backend sends the brand writing identity, the existing `_REFINE_TASK`, the current subject/body, optional instruction, and the selected lead's `_template_values` context. It does not build or send the workspace assistant snapshot. Prices are stripped before the request and from the response; an outgoing pound sign or a pound amount that survives response stripping is rejected. The Anthropic key is not part of settings, audit data, or API responses.

## Code map

| Area | Entry point |
|---|---|
| Authenticated key status/save/remove | `apps/backend/app/api/routes/system.py` (`/api/v1/system/cloud-polish`) |
| Secret vault adapter | `apps/backend/app/domains/system/cloud_polish.py` and `app.state.cloud_polish_configuration_service` in `main.py` |
| Enabled/model persistence and allowlist | `apps/backend/app/domains/system/schemas.py`; existing `AppSetting` workspace JSON |
| Single-draft API | `apps/backend/app/api/routes/outreach.py` (`POST /api/v1/outreach/drafts/{draft_id}/polish`) |
| Context boundary and non-mutating orchestration | `apps/backend/app/domains/outreach/service.py::polish_draft` |
| Shared prompt and version | `apps/backend/app/domains/outreach/cloud_prompt.py` |
| Anthropic SDK call, structured output, refusal and provider-error mapping | `apps/backend/app/domains/outreach/cloud_client.py` |
| Frontend endpoint and settings API methods | `apps/frontend/src/api.ts` |
| Conditional editor action | `apps/frontend/src/components/EmailDraftsWorkspace.tsx` |
| Key/model/enable controls | `apps/frontend/src/components/SettingsWorkspace.tsx` |
| App status refresh, mutation context, and shared actions | `apps/frontend/src/App.tsx`, `WorkspaceActionsContext.tsx`, `types.ts` |
| Backend automated coverage | `apps/backend/tests/test_cloud_polish.py` |
| Frontend automated coverage | `apps/frontend/src/App.test.tsx` |

## Safety properties to preserve

- Keep `cloud_polish_enabled` false by default and keep the UI button conditional on both `configured` and `enabled`.
- Keep the Anthropic API key exclusively in `SecretStore`. Do not add it to `Settings`, SQLite, audit summaries, app logs, frontend state persistence, or responses.
- Keep the cloud prompt context limited to the selected draft and its lead context. Do not call assistant snapshot/context builders or include campaign/follow-up/workspace data.
- Keep `_REFINE_TASK` as the shared brief and the identity block as the source of the brand writing rules. Bump `CLOUD_POLISH_PROMPT_VERSION` if prompt behavior changes.
- Keep price stripping/checks around outbound context and returned copy. Price handling is enforced in code as well as the model instructions.
- Keep the cloud path explicit and single-draft. It must not be a fallback for local AI, run on draft creation, or mutate/approve/send a draft.
- Mock the Anthropic client in automated tests. Never let CI or ordinary tests make a paid provider request.

## Verification recorded for this handover

- `cd apps/backend && python -m pytest -q`: 175 passed.
- `ruff check apps/backend`: passed.
- `mypy apps/backend/app`: passed.
- `cd apps/frontend && npm test`: 111 passed.
- `cd apps/frontend && npx eslint src --max-warnings=0`: passed.
- `cd apps/frontend && npx tsc -p tsconfig.app.json --noEmit`: passed.
- `cd apps/frontend && npm run build`: passed.
- `git diff --check`: passed.

The Python SDK dependency is declared in `apps/backend/pyproject.toml` and locked in the repository `uv.lock`.

## Operator follow-up before enabling for regular use

1. Check `GET /api/v1/system/summary` for `average_draft_edit_ratio` and `approved_drafts_measured`. The implementation session could not reach the local API, so the decision metric is unverified. The feature was implemented on the operator's explicit instruction, without evidence that the metric justified it.
2. Compare the 3B result with a larger local model on the same draft first. The available Ollama inventory during implementation contained only `llama3.2:3b`; no 8B model comparison was performed.
3. In Settings, save a real key directly into the protected vault, enable the feature, and polish one real draft. Check the wording, price removal, review-only editor behavior, and that Settings shows only whether a key is saved. Do not paste a real key into a chat, issue, test fixture, or log.
4. Choose the provider model deliberately in Settings. Sonnet 5 is the default/recommended writing model; Haiku 4.5 is the lower-cost option. Verify provider availability and the operator's own account access before use.

No real key was used and no live Anthropic call was made in the implementation or test runs. No installer was rebuilt.
