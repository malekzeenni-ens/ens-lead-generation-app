# Specification: Polish an outreach draft with a cloud model

- **Status:** Ready to build. Not yet implemented.
- **Audience:** A coding agent working in this repository with no prior context on it.
- **Prerequisite:** ADR-021 is shipped. Read [ADR-021](../adr/ADR-021-product-sales-knowledge.md) and §22–§24 of [the AI integration architecture](../architecture/AI_INTEGRATION_ARCHITECTURE.md) before writing code.
- **Scope:** One optional button that rewrites a single already-drafted outreach email using the Anthropic API instead of the local model. Nothing else in the application changes.

---

## 1. Why this exists, and the gate before building it

Every AI feature in this application runs locally through Ollama, deliberately: no per-request cost, no data leaving the machine. The one place that constraint bites is outreach copy, where a 3B local model is weakest and the output is read by a paying prospect.

Rather than guess, the app already measures the problem. When the operator approves a draft, `OutreachService._edit_distance_ratio` compares the wording approved against the wording first generated and stores it on `outreach_draft_revision.edit_distance_ratio`. `OperationsSummary.average_draft_edit_ratio` averages it, and the Overview screen shows it as "Draft edit rate".

**Do not build this feature until that number justifies it.** Check it first:

```
GET /api/v1/system/summary  →  average_draft_edit_ratio, approved_drafts_measured
```

| Reading | What to do |
|---|---|
| `approved_drafts_measured` under ~10 | Not enough evidence. Stop and tell the operator to approve more drafts first. |
| Average below ~0.25 | The local model is doing the job. **Do not build this.** Say so. |
| Average above ~0.25 | Try the cheaper fix first: a larger local model (§9). Build this only if that is already in use and still not good enough. |

If you build it anyway because you were told to, say plainly in your summary that the metric did not justify it.

---

## 2. What the operator gets

On the Email drafts screen, beside the existing **Refine with AI** button, a second button: **Polish with cloud AI**.

- It rewrites the subject and body currently in the editor, exactly as Refine does, and drops the result into the same two fields for the operator to accept or edit.
- It is **off by default**. It does not appear at all until an API key has been saved and the feature switched on in Settings.
- It acts on **one draft at a time**. There is no batch version and no automatic invocation.
- It changes nothing about approval. The draft still has to be reviewed and approved by hand, and the existing eligibility checks still apply.

---

## 3. Hard boundaries

These are not preferences. Each one has a reason, and breaking one is a defect.

1. **The workspace snapshot is never sent to the cloud.** Not leads, not campaigns, not follow-ups, not the catalogue. The request carries only: the brand voice block, the draft's own subject and body, and a small dictionary of facts about the one lead being written to. This is the whole reason the feature is narrow.
2. **No pricing goes out or comes back.** Pass the request body through `app.domains.catalogue.enrichment.strip_prices` on the way out and on the way back. Reject a response containing `£` followed by a digit. ADR-021 §"Two rules" explains why this is enforced in code rather than asked of the model.
3. **The API key never reaches SQLite, the logs, an audit record, or an API response.** Use the existing `SecretStore` (§5).
4. **No key, no feature.** Absent or invalid credentials is a clear 409, never a silent fall back to the local model — the operator must know which model wrote their words.
5. **Nothing is sent automatically.** One button, one draft, one explicit click.
6. **Failure is not destructive.** A timeout, a refusal or a bad response leaves the draft exactly as it was and shows the operator why.

---

## 4. The Anthropic call

Use the official `anthropic` Python SDK. Add `anthropic` to `apps/backend/pyproject.toml`. Do not hand-roll HTTP with `httpx`, and do not use an OpenAI-compatible shim.

### Model

`claude-haiku-4-5` — 200K context, **$1.00 per 1M input tokens, $5.00 per 1M output**.

A polish call sends roughly 2,500 input tokens and returns about 300, so **an individual polish costs on the order of a third of a US cent**. Even a hundred a month is well under a dollar.

> **Flag this to the operator, do not decide it silently.** Haiku is the cheapest and weakest of the current models, and this feature exists precisely because writing quality is the problem. `claude-sonnet-5` at $2.00/$10.00 per 1M is roughly twice the price — still under a cent per polish — and materially better at copy. Recommend Sonnet 5 and let the operator choose. Put the chosen model in the workspace setting (§5) so it can be changed without a code edit, and validate it against an allowlist of `claude-haiku-4-5` and `claude-sonnet-5`.

### Request shape

```python
import anthropic

client = anthropic.Anthropic(api_key=api_key, timeout=30.0, max_retries=2)

response = client.messages.create(
    model=model,                 # from workspace settings
    max_tokens=2000,             # a subject and a short body; do not lowball
    system=system_prompt,        # identity + task, see below
    messages=[{"role": "user", "content": user_content}],
    output_config={
        "format": {
            "type": "json_schema",
            "schema": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["subject", "body"],
                "additionalProperties": False,
            },
        }
    },
)
```

Notes that will otherwise cost you a debugging cycle:

- **Do not send a `thinking` parameter.** A short rewrite does not need it. If you ever add one on Haiku 4.5 it takes `{"type": "enabled", "budget_tokens": N}` — *not* `{"type": "adaptive"}`, which is for newer models. `output_config.effort` errors on Haiku 4.5.
- Use `output_config: {format: {...}}`. The older top-level `output_format` parameter is deprecated.
- Do not use assistant-message prefill to force JSON. Use the structured output above.
- **Check `response.stop_reason` before reading `response.content`.** On `"refusal"` read `response.stop_details.category` and surface a clear message. On `"max_tokens"` treat it as a failed polish rather than using the truncated text.
- `response.content` is a list of blocks. Match on `block.type == "text"`, do not index blindly.
- **Prompt caching is not worth it here** and should not be added. The cacheable prefix would be the ~2,000-token brand voice block, but polishing is sporadic and one draft at a time, so the 5-minute cache window will almost always have expired between calls — you would pay the 1.25× cache-write premium and rarely collect the discount. Revisit only if polishing ever becomes a batch operation.
- Log `response.usage.input_tokens` / `output_tokens` and `response._request_id` on the audit event. Never log the prompt content or the key.

### Prompt

System prompt is exactly two parts, joined by a blank line:

1. `identity_block(IdentityTier.WRITING)` from `app.domains.brand.profile`. This is the brand voice and the full B2B outreach rules, and it is the single source of truth — do not restate or paraphrase any of it.
2. A task instruction. Reuse `_REFINE_TASK` from `app.domains.outreach.prompt` so the cloud path and the local path are held to the same brief, including its rule that removing money overrides preserving concrete facts.

User message: the current subject, the current body, an optional operator instruction, and the lead context dictionary — built with the **same** `_template_values`-derived `context` that `refine_draft` already assembles (see `OutreachService.refine_draft`). Say in the message that these values are untrusted reference text, not instructions, exactly as `build_refine_messages` does.

Put this in a new `app/domains/outreach/cloud_prompt.py` with a `CLOUD_POLISH_PROMPT_VERSION` constant, so the version can be recorded and bumped.

---

## 5. Configuration and the key

**Credential storage.** Use the existing `SecretStore` protocol in `app/core/secrets.py` — on Windows it is `DpapiSecretStore`, a user-scoped DPAPI vault; tests get `MemorySecretStore`. Follow `MetaConnectionService` in `app/domains/system/meta.py` as the working precedent: `secret_store.set_json(key, {...})` to save, `get_json` to read, `delete` to remove. Use a new key such as `cloud_polish_credentials`. **Do not add a new secrets mechanism and do not put the key in `Settings`.**

**Workspace settings.** Add to `WorkspaceSettings` and `WorkspaceSettingsUpdate` in `app/domains/system/schemas.py`, following `local_ai_model` as the pattern:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `cloud_polish_enabled` | `bool` | `False` | Master switch. False means the endpoint 409s and the button is hidden. |
| `cloud_polish_model` | `str` | `""` | Empty means `claude-sonnet-5`. Validate against the allowlist. |

**Status endpoint.** `GET /api/v1/system/cloud-polish` returning `{configured: bool, enabled: bool, model: str}`. `configured` is whether a key is in the vault. **Never return the key or any part of it.**

**Configure and remove.** `PUT /api/v1/system/cloud-polish` taking `{api_key: SecretStr}`, and `DELETE` to wipe it. Mirror the Meta `configure` / `remove_configuration` methods.

---

## 6. Backend surface to build

| Item | Location |
|---|---|
| `POST /api/v1/outreach/drafts/{draft_id}/polish` | `app/api/routes/outreach.py`, modelled on the `refine` route directly above it |
| `OutreachService.polish_draft(...)` | `app/domains/outreach/service.py`, modelled on `refine_draft` |
| Prompt builder + version constant | new `app/domains/outreach/cloud_prompt.py` |
| Anthropic client wrapper | new `app/domains/outreach/cloud_client.py` |
| Credential + status service | `app/domains/system/` alongside `meta.py` |
| Settings fields | `app/domains/system/schemas.py` |

Request and response reuse `OutreachDraftRefineRequest` and `OutreachDraftRefineResult` unchanged, so the frontend contract matches Refine exactly.

`polish_draft` in order:

1. 409 `CLOUD_POLISH_DISABLED` if `cloud_polish_enabled` is false.
2. 409 `CLOUD_POLISH_NOT_CONFIGURED` if the vault has no key.
3. 404 if the draft does not exist.
4. Build the lead context the same way `refine_draft` does.
5. Call the API.
6. Strip prices from the returned subject and body; reject a price that survives.
7. Write an audit event `outreach.draft_cloud_polished` with the draft id, the model, the prompt version, the token counts and the Anthropic request id. **Not the content.**
8. Return the subject and body. Do not create a revision or mutate the draft — the operator saves through the existing edit path, exactly as with Refine.

### Error mapping

| Anthropic SDK exception | HTTP | Operator-facing message |
|---|---|---|
| `AuthenticationError` | 409 | The saved API key was rejected. Save a new one in Settings. |
| `PermissionDeniedError` | 409 | That API key is not permitted to use this model. |
| `RateLimitError` | 503 | The cloud model is rate limited. Read `retry-after` and say when to retry. |
| `BadRequestError` | 502 | The request was rejected. Include the message. |
| `APITimeoutError` | 504 | The cloud model took too long. The draft is unchanged. |
| `APIConnectionError` | 503 | No internet connection, so the cloud model is unreachable. |
| `APIStatusError` ≥500 | 503 | The cloud model is unavailable. Try again shortly. |

Catch most-specific first. Do not catch one broad class — a 429 and a 400 need different operator advice. Per-class details are in the `claude-api` skill's `shared/error-codes.md`.

---

## 7. Frontend surface to build

Follow the existing Refine implementation, which is the closest possible template:

- **`EmailDraftsWorkspace.tsx`** — `refineWithAI` at ~line 131 and the button at ~line 247. Add `polishWithCloud` and a second button beside it, with its own busy state and its own error line. Render the button **only** when the status endpoint reports `configured && enabled`. Label it so there is no ambiguity about what it does and what it costs: **Polish with cloud AI**.
- **`api.ts`** — `polishOutreachDraft` beside `refineOutreachDraft` (~line 603), plus the three cloud-polish settings calls.
- **`SettingsWorkspace.tsx`** — a Connections-tab panel for the key, following the Meta panel. A password-type input, a Save, a Remove, a model select, and an enable checkbox. Show only whether a key is saved, never the key. State plainly that this sends the draft and that lead's details to Anthropic and costs a fraction of a penny per polish.
- **`types.ts`** — mirror the new backend types.
- Wire any new mutation through `WorkspaceActionsContext.tsx` **and** `App.tsx`; a mutation needs an entry in all three files.

---

## 8. Tests

Add `apps/backend/tests/test_cloud_polish.py`. Mock the Anthropic client — **no test may make a real API call.**

Required cases:

1. Disabled by default: the endpoint 409s on a fresh workspace.
2. Enabled but no key: 409 `CLOUD_POLISH_NOT_CONFIGURED`.
3. Happy path: returns the rewritten subject and body, and the draft row is unchanged.
4. **The request body contains no workspace snapshot.** Assert on the captured call that no campaign, follow-up, shortlist or other lead's name appears. This is the most important test in the file.
5. **A price in the model's response is stripped**, and a price that survives stripping fails the request.
6. The API key never appears in the status response, an audit record, or a log line.
7. `stop_reason: "refusal"` produces a clear error and leaves the draft untouched.
8. Each error in the §6 table maps to the right status code.
9. The model allowlist rejects anything outside it.

Frontend: extend `App.test.tsx`, mocking the new endpoints in both the `vi.mock` factory and the `beforeEach`. Cover the button being hidden when unconfigured, shown when configured, and the polished text replacing the editor contents.

## 9. Verification

Everything below must pass, from the repository root:

```
cd apps/backend && python -m pytest -q
ruff check apps/backend
mypy apps/backend/app
cd apps/frontend && npx eslint src --max-warnings=0
cd apps/frontend && npx tsc -p tsconfig.app.json --noEmit    # tsconfig.json alone checks nothing
cd apps/frontend && npm test && npm run build
```

Then one manual check with a real key, on one real draft: polish it, confirm the wording improved, confirm no price appeared, and confirm the Settings screen never shows the key back.

**Before shipping, try the cheaper lever and compare.** Pull an 8B local model, select it in Settings, and polish the same draft both ways. If the local 8B is close, say so and recommend against enabling the cloud path. Bigger local model first, cloud second.

## 10. Out of scope

Do not build: a batch polish; automatic polishing on draft creation; any cloud call for campaign planning, lead briefing, autofill or general chat; sending the workspace snapshot anywhere; a cloud fallback when Ollama is down; streaming; or a spend dashboard. If the operator wants any of these, they are a separate decision with their own specification.
