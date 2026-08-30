# Lead & outreach AI features — implementation plan

- **Status:** Implemented
- **Updated:** 29 August 2026
- **Depends on:** [AI_INTEGRATION_ARCHITECTURE.md](AI_INTEGRATION_ARCHITECTURE.md) — read that document first. Every invariant, error-handling pattern, and safety boundary described there applies unchanged to everything in this document; this plan only adds new call sites onto the existing shared runtime, it does not change the runtime's guarantees.

This document is a standalone implementation spec for five new local-AI features, written so a
coding agent with no other context can execute it end to end. It assumes access to this repository
and to `AI_INTEGRATION_ARCHITECTURE.md` for background, but does not assume the agent has read any
other part of this conversation.

## 0. What this plan does not do

- No new database tables or migrations for any of the 5 features.
- No scheduling/cron for the stalled-lead digest (feature 5) — on-demand only.
- No semantic/full-text search over note or email content anywhere in feature 2 — only translation
  into the existing structured filter dimensions.
- No change to `OllamaClient.chat()` (the general assistant's call path) — it stays on its own
  contract and is not touched by anything below.

## 1. Context

The app already runs a local-Ollama integration (`app/domains/campaign_assistant/`,
`app/domains/assistant/`) with load-bearing invariants: one shared `CampaignAssistantManager`
singleton (`app.state.campaign_assistant_manager`) behind a single non-reentrant lock; model output
is always schema-constrained and re-validated deterministically before it can affect data; nothing
the model says is ever auto-persisted.

Five new features extend this:

1. **Outreach draft AI refine** — rewrite a drafted email using the lead's personalization
   context, for review before saving.
2. **Plain-English lead filter** — translate a natural-language query into the existing lead-list
   filter dropdowns.
3. **Lead briefing** — one-click "before you contact this lead" summary.
4. **Bulk lead-context autofill** — fills the `Lead` fields that today hard-block outreach batch
   creation, across a whole selected batch at once.
5. **Stalled-lead triage digest** — deterministically-selected stalled leads, one AI-suggested next
   action each.

Verified against the actual code (not assumed): `OllamaClient.generate()` /
`CampaignAssistantManager.generate()` hardcode the campaign schema today. Every new feature needs a
generic schema-in/model-out path, built once, first, without changing existing behavior for the
campaign or general-assistant callers.

**Hard schema constraint** (confirmed from `app/domains/campaign_assistant/ollama.py:34-38` and
the existing test `test_ollama_schema_keeps_each_outcome_unambiguous_and_grammar_compatible` in
`test_campaign_assistant.py`): any JSON schema sent to Ollama's `format` field must avoid `$defs`
(fully inline, no nested `$ref`s) and must avoid `maxLength` (Ollama's grammar converter does not
reliably support it). `minLength` and `enum` on string properties ARE supported and already used
in the existing campaign schema. **Length caps for every new schema below must be enforced by the
Pydantic model after generation, never by `maxLength` in the Ollama-side schema.**

## 2. Foundational refactor (must land first, before any feature; full regression gate)

### `app/domains/campaign_assistant/ollama.py`

- Extract the current `generate()` body's httpx try/except (today at lines ~321-351) into a
  private `_post_chat(self, payload: dict[str, Any], *, error_prefix: str) -> dict[str, Any]`
  returning the parsed response body (or raising `DomainError`), so the mapping below is written
  exactly once and reused:
  - `httpx.TimeoutException` → `DomainError(f"{error_prefix}_TIMEOUT", ..., status_code=504)`
  - `httpx.ConnectError` → `DomainError("OLLAMA_UNAVAILABLE", ..., status_code=503)`
  - `httpx.HTTPStatusError` → `DomainError("OLLAMA_REQUEST_FAILED", ..., status_code=503)`
    (special-case 404 → "model not installed" message, unchanged)
  - content missing/oversized (>100,000 UTF-8 bytes) → raise `ValueError` before returning
- Add:
  ```python
  ModelT = TypeVar("ModelT", bound=BaseModel)

  @dataclass(frozen=True)
  class OllamaStructuredResult(Generic[ModelT]):
      value: ModelT
      metrics: OllamaGenerationMetrics

  def generate_structured(
      self,
      messages: list[dict[str, str]],
      profile: ResourceProfile,
      *,
      schema: dict[str, Any],
      model_cls: type[ModelT],
      error_prefix: str,
  ) -> OllamaStructuredResult[ModelT]:
      ...
  ```
  Body: build `options`/`payload` exactly as `generate()` does today (same `num_ctx`/`num_predict`/
  `temperature`/`keep_alive` logic keyed off `profile`), except `payload["format"] = schema` as
  given (no campaign-specific mutation), call `self._post_chat(payload, error_prefix=error_prefix)`,
  then `model_cls.model_validate_json(content)` wrapped in the same
  `except (ValueError, json.JSONDecodeError, ValidationError)` →
  `DomainError(f"{error_prefix}_INVALID_RESPONSE", ...)` mapping `generate()` uses today. Return
  `OllamaStructuredResult(value=..., metrics=OllamaGenerationMetrics(...))` (same metrics
  construction as today, unchanged).
- Rewrite `generate()` as a thin wrapper:
  ```python
  def generate(self, messages: list[dict[str, str]], profile: ResourceProfile) -> OllamaResult:
      schema = deepcopy(OLLAMA_CAMPAIGN_PROPOSAL_SCHEMA)
      schema["oneOf"][0]["properties"]["campaign"]["properties"]["keywords"]["maxItems"] = (
          self.settings.discovery_max_queries
      )
      result = self.generate_structured(
          messages, profile, schema=schema, model_cls=CampaignDraftProposal,
          error_prefix="CAMPAIGN_ASSISTANT",
      )
      return OllamaResult(proposal=result.value, metrics=result.metrics)
  ```
  This must be **behavior-preserving**: identical error codes, identical payload, identical schema
  mutation. `chat()` (general assistant) is untouched — different response contract, do not force
  it onto this path.

### `app/domains/campaign_assistant/manager.py`

- Extract the current `generate()`/`chat()`'s shared lock-acquire → resource-profile → try/finally
  unload structure into a private helper:
  ```python
  def _run_locked(
      self, run: Callable[[ResourceProfile], T], *, protect_resources: bool, busy_message: str,
  ) -> tuple[T, ResourceProfile]:
      if not self._generation_lock.acquire(blocking=False):
          raise DomainError("CAMPAIGN_ASSISTANT_BUSY", busy_message, status_code=409)
      profile = self.resource_profile(protect_resources)
      try:
          result = run(profile)
      finally:
          should_unload = profile == ResourceProfile.DESIGN_SOFTWARE or self._unload_after_current.is_set()
          self._generation_lock.release()
          if should_unload:
              self._unload_after_current.clear()
              self.ollama.unload()
      return result, profile
  ```
  Reword the busy message to be feature-agnostic ("The local assistant is already processing
  another request.") since it is now shared by 6+ callers — confirm via `test_campaign_assistant.py`
  that assertions check `response.json()["code"]`, not message text, before making this change (if
  any test asserts message text, update that assertion in the same commit).
- `generate()`/`chat()` become one-line calls into `_run_locked` — **must remain byte-identical in
  observable behavior** (same lock, same 409 code, same unload timing).
- Add:
  ```python
  def generate_structured(
      self,
      messages: list[dict[str, str]],
      *,
      schema: dict[str, Any],
      model_cls: type[ModelT],
      error_prefix: str,
      protect_resources: bool,
  ) -> tuple[OllamaStructuredResult[ModelT], ResourceProfile]:
      return self._run_locked(
          lambda profile: self.ollama.generate_structured(
              messages, profile, schema=schema, model_cls=model_cls, error_prefix=error_prefix,
          ),
          protect_resources=protect_resources,
          busy_message="The local assistant is already processing another request.",
      )
  ```

**Regression gate**: after this step, run (from `apps/backend`) `python -m pytest`,
`python -m ruff check`, `python -m mypy app` — all must pass with the EXISTING test files
unmodified (aside from any busy-message text assertion found above). Do not proceed to any feature
below until this passes.

### New shared gate: `app/domains/campaign_assistant/gate.py`

```python
def require_local_ai_enabled(runtime_settings: Settings, workspace_settings: WorkspaceSettings) -> None:
    if not runtime_settings.campaign_assistant_enabled:
        raise DomainError("CAMPAIGN_ASSISTANT_DISABLED", "...", status_code=503)
    if not workspace_settings.local_campaign_assistant_enabled:
        raise DomainError("CAMPAIGN_ASSISTANT_DISABLED", "...", status_code=409)
```
Extracted from `CampaignAssistantService._require_enabled` (keep that method as a thin call to this
for backward compat, or replace its body with a call to this — either is fine, no test should need
to change). All 5 new features call this at the top of their service method instead of duplicating
the check.

### New domain: `app/domains/lead_assistant/`

```
app/domains/lead_assistant/
  __init__.py
  schemas.py     # all of features 2/3/4/5's request/response Pydantic models
  prompt.py      # one build_*_messages() + one _OLLAMA_*_SCHEMA dict per feature
  service.py     # LeadAssistantService with one public method per feature
app/api/routes/lead_assistant.py   # prefix "/lead-assistant"
```
Feature 1 (outreach refine) stays inside `app/domains/outreach/` (needs
`OutreachService._template_values`/`_template_products`, which are outreach-private).

### Frontend convention (verified against `App.tsx:410` `perform()` and `CampaignAssistantTab.tsx`)

A generation call that does **not** persist bypasses `WorkspaceActionsContext`/`perform()` entirely
— local component state (`working`/`error`), direct `api.*` call, exactly like the existing
campaign assistant tab. Only a call that actually writes data (feature 4's "Save all") goes through
`perform()`. Getting this backwards (routing a non-persisting generation call through `perform()`)
would wrongly gate it behind the shared `busy` flag and wrongly invalidate cache when nothing was
saved.

## 3. Feature: Outreach draft AI refine

**Goal**: a "Refine with AI" button on the draft editor that improves the current subject/body
using the lead's personalization context. Never auto-saves.

**Backend**
- `app/domains/outreach/prompt.py` (new):
  ```python
  OUTREACH_REFINE_PROMPT_VERSION = "outreach-refine-v1"
  SYSTEM_PROMPT = """You are rewriting one already-drafted outreach email for a human to review
  before sending. Preserve every concrete fact already present unless it is wrong. Never invent
  claims about the business that are not in the supplied context. Never claim the email has been
  sent or approved. Return only the subject and body fields."""

  def build_refine_messages(
      *, current_subject: str, current_body: str, lead_context: dict[str, Any],
      instruction: str | None,
  ) -> list[dict[str, str]]: ...

  _OLLAMA_REFINE_SCHEMA: dict[str, Any] = {
      "type": "object",
      "properties": {
          "subject": {"type": "string", "minLength": 1},
          "body": {"type": "string", "minLength": 1},
      },
      "required": ["subject", "body"],
  }
  ```
- `app/domains/outreach/schemas.py`:
  ```python
  class OutreachDraftRefineRequest(BaseModel):
      model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
      subject: str = Field(min_length=1, max_length=300)
      body: str = Field(min_length=1, max_length=50_000)
      instruction: str | None = Field(default=None, max_length=500)

  class OutreachDraftRefineResult(BaseModel):
      subject: str = Field(min_length=1, max_length=300)
      body: str = Field(min_length=1, max_length=50_000)
  ```
  (Caps match `OutreachDraftEdit` exactly, `schemas.py:38`.)
- `app/domains/outreach/service.py`, new method:
  ```python
  def refine_draft(
      self, session: Session, draft_id: str, data: OutreachDraftRefineRequest, *,
      manager: CampaignAssistantManager, runtime_settings: Settings,
      workspace_settings: WorkspaceSettings,
  ) -> OutreachDraftRefineResult:
      require_local_ai_enabled(runtime_settings, workspace_settings)
      draft = self.repository.get_draft(session, draft_id)
      if draft is None:
          raise DomainError("OUTREACH_DRAFT_NOT_FOUND", "...", status_code=404)
      lead = draft.lead
      template = self.template_repository.get(session, draft.template_id) if draft.template_id else None
      products = self._template_products(session, template) if template else []
      context = {k: v for k, v in self._template_values(lead, products).items() if v}
      messages = build_refine_messages(
          current_subject=data.subject, current_body=data.body,
          lead_context=context, instruction=data.instruction,
      )
      result, _profile = manager.generate_structured(
          messages, schema=_OLLAMA_REFINE_SCHEMA, model_cls=OutreachDraftRefineResult,
          error_prefix="OUTREACH_REFINE",
          protect_resources=workspace_settings.protect_design_software_resources,
      )
      return result.value  # never persisted — no revision row, no current_version bump
  ```
- `app/api/routes/outreach.py`:
  ```python
  @router.post("/drafts/{draft_id}/refine", response_model=OutreachDraftRefineResult)
  def refine_draft(draft_id: str, data: OutreachDraftRefineRequest, request: Request, _: Authenticated, session: DatabaseSession) -> OutreachDraftRefineResult:
      manager = cast(CampaignAssistantManager, request.app.state.campaign_assistant_manager)
      workspace_settings = SystemService().get_settings(session)
      settings = cast(Settings, request.app.state.settings)
      return service.refine_draft(session, draft_id, data, manager=manager, runtime_settings=settings, workspace_settings=workspace_settings)
  ```

**Frontend**
- `apps/frontend/src/types.ts`: `OutreachDraftRefineInput { subject: string; body: string; instruction?: string }`, `OutreachDraftRefineResult { subject: string; body: string }`.
- `apps/frontend/src/api.ts`: `refineOutreachDraft: (draftId: string, data: OutreachDraftRefineInput) => request<OutreachDraftRefineResult>(\`/outreach/drafts/${draftId}/refine\`, jsonBody("POST", data))`.
- `apps/frontend/src/components/EmailDraftsWorkspace.tsx`, inside `DraftEditor` (~line 79): add
  local state `refining`/`refineError`, an async `refineWithAI()` that calls the API and does
  `setSubject(result.subject); setBody(result.body)` — **must not call `save()`**. Add a "Refine
  with AI" button next to Save/Save & approve, disabled while `refining` or while the editor is
  otherwise busy.

**Do-not**: refine must not require any particular `sync_status`/lock state on the draft (it never
writes); the existing save-time lock still gates persistence.

**Acceptance criteria / tests** (extend `apps/backend/tests/test_outreach.py`):
- Refine returns a suggestion and creates **no** new `OutreachDraftRevision` row.
- Subject/body length caps enforced (422 on oversized `instruction`).
- A fake manager returning `CAMPAIGN_ASSISTANT_BUSY` propagates as 409.
- Refine succeeds even when the draft's `sync_status` is `opened_in_zoho`/`user_confirmed_sent`
  (documents that refine ≠ save authorization).

## 4. Feature: Plain-English lead filter (build second — smallest, proves the new domain scaffold)

**Goal**: a text box that sets the *existing* lead-list filters from a natural-language request. It
does **not** search inside notes or emails — say so in the UI copy.

**Backend**
- `app/domains/lead_assistant/prompt.py`:
  ```python
  LEAD_FILTER_PROMPT_VERSION = "lead-filter-v1"

  def build_filter_messages(
      *, query: str, available_stages: list[str], available_source_types: list[str],
      campaigns: list[dict[str, str]],
  ) -> list[dict[str, str]]: ...

  def build_filter_schema(available_stages: list[str], available_source_types: list[str]) -> dict[str, Any]:
      return {
          "type": "object",
          "properties": {
              "stage": {"anyOf": [{"type": "string", "enum": available_stages}, {"type": "null"}]},
              "suppressed": {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
              "campaign_id": {"anyOf": [{"type": "string"}, {"type": "null"}]},
              "source_type": {"anyOf": [{"type": "string", "enum": available_source_types}, {"type": "null"}]},
              "keyword": {"anyOf": [{"type": "string"}, {"type": "null"}]},
          },
          "required": ["stage", "suppressed", "campaign_id", "source_type", "keyword"],
      }
  ```
  Build the `stage`/`source_type` enum arrays dynamically per-request from live data, since valid
  values are runtime data, not a module constant.
  System prompt: "You translate the request into the given dropdown filters only. You do not search
  email or note text. If nothing structured matches, set every field null except `keyword`, which
  should hold the residual wording."
- `app/domains/lead_assistant/schemas.py`:
  ```python
  class LeadFilterTranslateRequest(BaseModel):
      model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
      query: str = Field(min_length=1, max_length=300)

  class LeadFilterTranslateResult(BaseModel):
      stage: str | None = None
      suppressed: bool | None = None
      campaign_id: str | None = None
      source_type: str | None = None
      keyword: str | None = Field(default=None, max_length=300)
  ```
- `app/domains/lead_assistant/service.py`:
  ```python
  def translate_filter(
      self, session: Session, data: LeadFilterTranslateRequest, *,
      manager: CampaignAssistantManager, runtime_settings: Settings, workspace_settings: WorkspaceSettings,
  ) -> LeadFilterTranslateResult:
      require_local_ai_enabled(runtime_settings, workspace_settings)
      stages = [s.value for s in PipelineStage]
      source_types = self.lead_repository.distinct_source_types(session)  # new small repo method
      campaigns = [{"id": c.id, "name": c.name} for c in self.campaign_repository.list(session)]
      messages = build_filter_messages(query=data.query, available_stages=stages, available_source_types=source_types, campaigns=campaigns)
      schema = build_filter_schema(stages, source_types)
      result, _ = manager.generate_structured(
          messages, schema=schema, model_cls=LeadFilterTranslateResult,
          error_prefix="LEAD_FILTER", protect_resources=workspace_settings.protect_design_software_resources,
      )
      value = result.value
      # Deterministic re-validation — never trust the model's values directly, even though the
      # schema already constrains stage/source_type via enum:
      if value.campaign_id is not None and self.campaign_repository.get(session, value.campaign_id) is None:
          value = value.model_copy(update={"campaign_id": None})
      return value
  ```
  New repository method needed: `LeadRepository.distinct_source_types(session) -> list[str]` —
  `SELECT DISTINCT source_type FROM source_observation` (or the equivalent existing table storing
  per-lead source type; confirm the exact table/column name in `app/domains/leads/repository.py`
  and `app/db/models.py` before writing this query).
- `app/api/routes/lead_assistant.py`: `POST /lead-assistant/search-filter`.

**Frontend**
- `apps/frontend/src/components/LeadWorkspace.tsx`: add a text input + "Ask AI" button near the
  existing filter controls (~lines 68-85). Local state only (`translating`/`translateError`),
  direct `api.translateLeadFilter(query)` call. On success, set the **existing** filter state
  setters (`setStage`, `setCampaignId`, `setSourceType`, `setSuppression`, `setQuery`) — read the
  exact `<select>` option string values already used in this file before wiring `suppression` (do
  not guess the literal strings — read the JSX, not just the `useMemo`). **Do not** touch the
  `filteredLeads` `useMemo` at all. Add one line of UI copy: "Sets the filters below from your
  request — it does not search inside notes or emails."
- `apps/frontend/src/types.ts`: `LeadFilterTranslateResult`. `apps/frontend/src/api.ts`:
  `translateLeadFilter: (query: string) => request<LeadFilterTranslateResult>("/lead-assistant/search-filter", jsonBody("POST", { query }))`.

**Acceptance criteria / tests** (new `apps/backend/tests/test_lead_assistant.py`):
- Valid stage/campaign pass through untouched.
- A hallucinated `campaign_id` (one that doesn't resolve to a real campaign) is nulled by backend
  validation, never passed to the caller.
- Empty/non-matching query returns all-null except `keyword`.

## 5. Feature: Lead briefing

**Goal**: a "Brief me" button on the lead detail view producing a short read-only summary before
contact. Nothing persisted unless the user explicitly saves it as a note.

**Backend**
- `app/domains/lead_assistant/prompt.py`:
  ```python
  LEAD_BRIEFING_PROMPT_VERSION = "lead-briefing-v1"
  def build_briefing_messages(*, context: dict[str, Any]) -> list[dict[str, str]]: ...
  _OLLAMA_BRIEFING_SCHEMA = {
      "type": "object",
      "properties": {
          "summary": {"type": "string", "minLength": 1},
          "talking_points": {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1, "maxItems": 3},
          "watch_out_for": {"anyOf": [{"type": "string"}, {"type": "null"}]},
      },
      "required": ["summary", "talking_points", "watch_out_for"],
  }
  ```
  Context assembled server-side: `business_name`, `segment`, `location`, existing personalization
  fields (`personalisation_observation` etc. — these are EXISTING human/AI-written values, input
  to this prompt, not output), latest 3 `LeadNote.content` (newest first), `current_score` +
  latest `ScoreRun.breakdown` (if `lead.score_runs` is non-empty — already eager-loaded per
  `LeadRepository._LEAD_OPTIONS`), campaign names via `lead.campaigns`.
- `app/domains/lead_assistant/schemas.py`:
  ```python
  class LeadBriefingResponse(BaseModel):
      model_config = ConfigDict(extra="forbid")
      summary: str = Field(min_length=1, max_length=1_000)
      talking_points: list[str] = Field(min_length=1, max_length=3)
      watch_out_for: str | None = Field(default=None, max_length=500)
  ```
- `app/domains/lead_assistant/service.py`: `brief(session, lead_id, *, manager, runtime_settings, workspace_settings) -> LeadBriefingResponse` — 404 if lead missing; tolerate no notes / no score runs (omit those context keys rather than erroring).
- `app/api/routes/lead_assistant.py`: `POST /lead-assistant/leads/{lead_id}/briefing` (POST, not
  GET — this is an expensive generation call each time, not a cacheable read; matches every other
  AI-generation endpoint in the app).

**Frontend**
- `apps/frontend/src/components/PipelineWorkspace.tsx`, "overview" tab: "Brief me" button + local
  state, renders `summary`, bulleted `talking_points`, `watch_out_for` if present. Optional "Save
  as note" button reuses the **existing** note-creation action (already wired through
  `WorkspaceActionsContext`) with the briefing text as content — do not build a new persistence
  path for this.
- `apps/frontend/src/api.ts`: `briefLead: (leadId: string) => request<LeadBriefing>(\`/lead-assistant/leads/${leadId}/briefing\`, jsonBody("POST", {}))`. `apps/frontend/src/types.ts`: `LeadBriefing`.

**Acceptance criteria / tests** (add to `test_lead_assistant.py`):
- Lead with no score runs / no notes doesn't crash.
- 404 for unknown lead.
- `talking_points` length (1-3) enforced by Pydantic even if the model returns more/fewer.

## 6. Feature: Bulk lead-context autofill (build after 4 and 5 — most complex, touches a shared file)

**Goal**: unblock `OutreachService.template_blockers` for a whole selected batch of leads in one
action by filling `personalisation_observation`, `relevance_opportunity`, `offer_angle`,
`desired_next_step` from a live website re-scrape + existing notes. Nothing writes to `Lead` until
an explicit "Save all".

**Backend**
- `app/domains/automation/enrichment.py`: add `visible_text: str` to the `WebsiteEvidence`
  dataclass. In `_EvidenceParser`, collect non-title/description text-node content from
  `handle_data()` (still respecting the existing `_ignored_depth` guard that already excludes
  `<script>`/`<style>`) into `self._visible_text_parts: list[str]`, capping total accumulated
  length during parsing (mirror the existing title/description capping style). In `enrich()`, join
  parts across the home page + up to 2 contact pages already fetched, collapse whitespace, and
  hard-truncate to ~3,000 characters before returning. **This is additive only** — confirm via
  `grep -rn "WebsiteEvidence(" apps/backend/app` that `enrich()` is the sole construction site
  before editing, so no other caller needs updating. `visible_text` must never be written to `Lead`
  or `SourceObservation` — it is used only in-memory to build one prompt, then discarded.
- `app/domains/lead_assistant/prompt.py`:
  ```python
  LEAD_AUTOFILL_PROMPT_VERSION = "lead-autofill-v1"
  def build_autofill_messages(*, business_name: str, segment: str, location: str, website_evidence: dict[str, Any] | None, existing_notes: str) -> list[dict[str, str]]: ...
  _OLLAMA_AUTOFILL_SCHEMA = {
      "type": "object",
      "properties": {
          "personalisation_observation": {"anyOf": [{"type": "string"}, {"type": "null"}]},
          "relevance_opportunity": {"anyOf": [{"type": "string"}, {"type": "null"}]},
          "offer_angle": {"anyOf": [{"type": "string"}, {"type": "null"}]},
          "desired_next_step": {"anyOf": [{"type": "string"}, {"type": "null"}]},
      },
      "required": ["personalisation_observation", "relevance_opportunity", "offer_angle", "desired_next_step"],
  }
  ```
  System prompt: use only the supplied evidence/notes; never invent specifics not present; if
  evidence is thin, return a generic-but-honest value anchored on segment/location, or null rather
  than fabricate.
- `app/domains/lead_assistant/schemas.py`:
  ```python
  class LeadAutofillRequest(BaseModel):
      model_config = ConfigDict(extra="forbid")
      lead_ids: list[str] = Field(min_length=1, max_length=20)

      @model_validator(mode="after")
      def require_unique(self) -> LeadAutofillRequest:
          if len(set(self.lead_ids)) != len(self.lead_ids):
              raise ValueError("Each selected lead may appear only once")
          return self

  class LeadAutofillSuggestion(BaseModel):
      personalisation_observation: str | None = Field(default=None, max_length=4_000)
      relevance_opportunity: str | None = Field(default=None, max_length=4_000)
      offer_angle: str | None = Field(default=None, max_length=4_000)
      desired_next_step: str | None = Field(default=None, max_length=2_000)

  class LeadAutofillResultItem(BaseModel):
      lead_id: str
      business_name: str
      suggestion: LeadAutofillSuggestion | None
      skipped_reason: str | None = None

  class LeadAutofillResponse(BaseModel):
      items: list[LeadAutofillResultItem]
  ```
  (Caps mirror `LeadUpdate`, `leads/schemas.py:337`, exactly.)
- `app/domains/lead_assistant/service.py`:
  ```python
  def autofill_leads(
      self, session: Session, data: LeadAutofillRequest, *,
      manager: CampaignAssistantManager, runtime_settings: Settings,
      workspace_settings: WorkspaceSettings, enricher: SafeWebsiteEnricher,
  ) -> LeadAutofillResponse:
      require_local_ai_enabled(runtime_settings, workspace_settings)
      items: list[LeadAutofillResultItem] = []
      for lead_id in data.lead_ids:
          lead = self.lead_repository.get(session, lead_id)
          if lead is None:
              items.append(LeadAutofillResultItem(lead_id=lead_id, business_name="", suggestion=None, skipped_reason="Lead not found."))
              continue
          evidence = None
          if lead.website:
              try:
                  evidence = enricher.enrich(lead.website)
              except EnrichmentFailure:
                  evidence = None  # degrade, don't abort this lead
          notes = " | ".join(n.content[:300] for n in sorted(lead.notes, key=lambda n: n.created_at, reverse=True)[:3])
          messages = build_autofill_messages(business_name=lead.business_name, segment=lead.segment, location=lead.location, website_evidence=asdict(evidence) if evidence else None, existing_notes=notes)
          try:
              result, _ = manager.generate_structured(messages, schema=_OLLAMA_AUTOFILL_SCHEMA, model_cls=LeadAutofillSuggestion, error_prefix="LEAD_AUTOFILL", protect_resources=workspace_settings.protect_design_software_resources)
              items.append(LeadAutofillResultItem(lead_id=lead.id, business_name=lead.business_name, suggestion=result.value))
          except DomainError as exc:
              if exc.code == "CAMPAIGN_ASSISTANT_BUSY":
                  raise  # whole batch aborts — retrying per-lead won't help while the lock is held
              items.append(LeadAutofillResultItem(lead_id=lead.id, business_name=lead.business_name, suggestion=None, skipped_reason=exc.message))
      return LeadAutofillResponse(items=items)
  ```
  No `session.commit()` anywhere in this method — it is read + inference only.
- **New bulk-update endpoint (does not exist today)**:
  ```python
  # app/domains/leads/schemas.py
  class LeadBulkUpdateItem(BaseModel):
      model_config = ConfigDict(extra="forbid")
      lead_id: str
      changes: LeadUpdate

  class LeadBulkUpdateRequest(BaseModel):
      model_config = ConfigDict(extra="forbid")
      items: list[LeadBulkUpdateItem] = Field(min_length=1, max_length=20)
  ```
  `app/domains/leads/service.py`: `bulk_update(session, data: LeadBulkUpdateRequest, correlation_id) -> list[LeadRead]` — loops the **existing** `update()` per item. **All-or-nothing**: validate every item's `changes` before calling `update()` on any of them (or wrap in a single transaction and roll back on the first failure) — unlike autofill's per-lead leniency, a real write must not partially, silently fail. Route: `PATCH /leads/bulk` in `app/api/routes/leads.py`.
- `app/api/routes/lead_assistant.py`: `POST /lead-assistant/autofill`.

**Frontend**
- In `EmailDraftsWorkspace.tsx`'s prepare step, next to the existing `template_blockers` display:
  "Fill missing context with AI" button → `api.autofillLeads(blockedLeadIds)` (local state, direct
  call, not `perform()` since nothing is saved yet) → renders an editable review table (business
  name read-only, 4 suggested fields editable per row) → "Save all" button calls
  `api.bulkUpdateLeads(items)` **through `WorkspaceActionsContext.perform()`** (this one *does*
  persist), invalidating `["leads", "outreachLeadOptions"]` → re-check `template_blockers` for the
  batch afterward.
- `apps/frontend/src/api.ts`: `autofillLeads`, `bulkUpdateLeads`. `apps/frontend/src/types.ts`:
  matching types. New `WorkspaceActionsContext` method `bulkUpdateLeads` implemented via `perform()`
  in `App.tsx` (this is the one exception to the "local state" rule in this feature set, because it
  genuinely writes).

**Acceptance criteria / tests**:
- Successful autofill across N leads (fake enricher + fake manager).
- A lead with no website still gets a suggestion from segment/location alone.
- One lead's enrichment failure does not block the others.
- Unknown `lead_id` → `skipped_reason`, not a failed request.
- `CAMPAIGN_ASSISTANT_BUSY` aborts the whole batch.
- `test_leads.py`: `bulk_update` rejects the whole request if any one item's `changes` fails
  validation (all-or-nothing — this is intentionally the opposite of autofill's leniency, do not
  "fix" it to match later).

## 7. Feature: Stalled-lead triage digest (build last — small refactor + new settings)

**Goal**: an on-demand, deterministically-selected list of stalled leads with one AI-suggested next
action each. No scheduling — this app has no cron/APScheduler; everything is on-demand or a
single-worker `ThreadPoolExecutor` gated by `settings.campaign_run_inline`. Follow the on-demand
pattern, not a new background job.

**Backend**
- Extract the existing "most recent activity across notes/stage-events/follow-ups/communications"
  union already implemented inline in `LeadService`'s CSV/activity-export path into a shared
  function `app/domains/leads/activity.py::latest_activity_at(lead: Lead) -> datetime | None`
  (pure extract-method — read the existing export code first and copy its exact union logic, do not
  re-derive it from scratch). Both the export path and the new query below call this one function.
- New deterministic query, `app/domains/lead_assistant/staleness.py`:
  ```python
  def find_stalled_leads(session: Session, *, stale_after_days: int, limit: int) -> list[tuple[Lead, int]]:
      today = date.today()
      active_stages = {...}  # confirm the exact "active" subset of PipelineStage in leads/schemas.py before hardcoding
      candidates = session.scalars(
          select(Lead).where(Lead.suppressed.is_(False), Lead.pipeline_stage.in_(active_stages)).options(*_LEAD_OPTIONS)
      )
      results: list[tuple[Lead, int]] = []
      for lead in candidates:
          last_activity = latest_activity_at(lead)
          days_stale = (datetime.now(UTC).date() - last_activity.date()).days if last_activity else stale_after_days
          hold_triggered = lead.outreach_hold_until is not None and lead.outreach_hold_until <= today
          retention_triggered = lead.retention_review_date is not None and lead.retention_review_date <= today
          if hold_triggered or retention_triggered or days_stale >= stale_after_days:
              results.append((lead, days_stale))
      results.sort(key=lambda pair: (-(pair[0].current_score or 0), -pair[1]))
      return results[:limit]
  ```
  **This selection is 100% deterministic — the model never decides which leads are stalled.**
- New setting in `app/core/config.py` (follow the existing `ENS_`-prefixed, one-field-per-line
  convention): `lead_stale_after_days: int = Field(default=21, ge=1, le=365)`.
- `app/domains/lead_assistant/prompt.py`:
  ```python
  LEAD_DIGEST_PROMPT_VERSION = "lead-digest-v1"
  def build_digest_messages(*, candidates: list[dict[str, Any]]) -> list[dict[str, str]]: ...
  def build_digest_schema(candidate_ids: list[str]) -> dict[str, Any]:
      return {
          "type": "object",
          "properties": {
              "items": {
                  "type": "array",
                  "items": {
                      "type": "object",
                      "properties": {
                          "lead_id": {"type": "string", "enum": candidate_ids},
                          "suggested_action": {"type": "string", "minLength": 1},
                      },
                      "required": ["lead_id", "suggested_action"],
                  },
                  "maxItems": len(candidate_ids),
              },
          },
          "required": ["items"],
      }
  ```
  Constraining `lead_id` to an `enum` of the known candidate IDs prevents most hallucination up
  front; the backend still re-validates every returned `lead_id` against the candidate set
  afterward and drops anything that doesn't match (defense in depth).
- `app/domains/lead_assistant/schemas.py`:
  ```python
  class StalledLeadDigestRequest(BaseModel):
      model_config = ConfigDict(extra="forbid")
      limit: int | None = Field(default=None, ge=1, le=25)

  class StalledLeadSuggestion(BaseModel):
      lead_id: str
      business_name: str
      days_stale: int
      suggested_action: str = Field(min_length=1, max_length=300)

  class StalledLeadDigestResponse(BaseModel):
      generated_at: datetime
      items: list[StalledLeadSuggestion]
  ```
- `app/domains/lead_assistant/service.py`:
  ```python
  def stalled_digest(
      self, session: Session, data: StalledLeadDigestRequest, *,
      manager: CampaignAssistantManager, runtime_settings: Settings, workspace_settings: WorkspaceSettings,
  ) -> StalledLeadDigestResponse:
      require_local_ai_enabled(runtime_settings, workspace_settings)
      limit = data.limit or 15
      candidates = find_stalled_leads(session, stale_after_days=runtime_settings.lead_stale_after_days, limit=limit)
      if not candidates:
          return StalledLeadDigestResponse(generated_at=datetime.now(UTC), items=[])  # never calls Ollama for an empty list
      candidate_ids = [lead.id for lead, _ in candidates]
      messages = build_digest_messages(candidates=[...])
      result, _ = manager.generate_structured(
          messages, schema=build_digest_schema(candidate_ids), model_cls=_DigestModel,
          error_prefix="LEAD_DIGEST", protect_resources=workspace_settings.protect_design_software_resources,
      )
      by_id = {lead.id: (lead, days) for lead, days in candidates}
      items = [
          StalledLeadSuggestion(lead_id=item.lead_id, business_name=by_id[item.lead_id][0].business_name, days_stale=by_id[item.lead_id][1], suggested_action=item.suggested_action)
          for item in result.value.items if item.lead_id in by_id  # drop anything not in the candidate set
      ]
      return StalledLeadDigestResponse(generated_at=datetime.now(UTC), items=items)
  ```
- `app/api/routes/lead_assistant.py`: `POST /lead-assistant/stalled-digest`.

**Frontend**
- `apps/frontend/src/components/LeadWorkspace.tsx` toolbar: "Stalled leads" button → modal/panel
  (local state, direct `api.stalledLeadDigest()` call). Rows: business name (links to that lead's
  detail view via the existing lead-selection mechanism), `days_stale`, `suggested_action`. No save
  action anywhere in this feature — purely informational; the operator acts through existing flows
  (add a note, change stage, start an outreach batch).
- `apps/frontend/src/api.ts`: `stalledLeadDigest(limit?: number)`. `apps/frontend/src/types.ts`:
  matching types.

**Acceptance criteria / tests**:
- Staleness query: hold-triggered inclusion even if otherwise recently active; retention-date-
  triggered inclusion; suppressed leads excluded; inactive pipeline stages excluded (can be tested
  independent of any LLM mock, in `test_leads.py` alongside the extracted `latest_activity_at`).
- Digest: empty-candidate list never calls the fake manager's `generate_structured` (assert this
  explicitly); a hallucinated `lead_id` outside the candidate set is filtered out of the response;
  `limit` capped at 25 even if the caller requests more.

## 8. Build order

1. **Foundational refactor** (§2) — regression gate, must pass unmodified existing tests before
   anything else.
2. **Feature: outreach refine** (§3) — smallest, proves the pattern inside an existing domain.
3. **Feature: filter translation** (§4) — smallest of the four `lead_assistant` features; proves
   the new domain scaffold (`schemas.py`/`prompt.py`/`service.py`/routes, `require_local_ai_enabled`,
   `generate_structured` call) with minimal surface area.
4. **Feature: briefing** (§5) — adds score-history/notes context assembly on top of the proven
   scaffold.
5. **Feature: bulk autofill** (§6) — most complex: touches `automation/enrichment.py` (shared with
   another domain), per-lead partial-failure handling, a new bulk-update endpoint, a two-step
   frontend flow. Deliberately after filter translation and briefing.
6. **Feature: stalled digest** (§7) — needs the `latest_activity_at` extraction (touches existing
   `LeadService` export code) plus a new setting; benefits from being last since every other
   convention is already proven three times over.

## 9. New invariants (add to `AI_INTEGRATION_ARCHITECTURE.md` §2 once built)

- No AI suggestion from any of the 5 features is auto-persisted; each routes through an existing or
  new explicit save action (outreach `PATCH`, new `PATCH /leads/bulk`, existing note-creation,
  in-memory filter state only, or — for the digest — no save action at all).
- All 5 share the single `CampaignAssistantManager` lock via `generate_structured`; a busy 409 from
  any AI surface in the app (general chat, campaign assistant, or any of these 5) blocks all the
  others, by design, not as a bug.
- The stalled-lead digest's candidate selection is 100% deterministic backend logic; the model only
  proposes text for backend-selected leads, and every returned `lead_id` is re-validated against
  the candidate set the backend actually sent.
- The filter-translation endpoint only ever sets existing structured filter state; it must never be
  described as searching note/email content, and must never bypass the existing client-side
  `filteredLeads` matching logic.
- The autofill feature's `visible_text` enrichment field is capped (~3,000 chars) and never
  persisted beyond the single prompt build that consumes it.
- Any JSON schema built for Ollama's `format` field must avoid `$defs` and `maxLength` (grammar
  compiler compatibility, confirmed by an existing test); length limits are Pydantic-side only.

## 10. Verification

From `apps/backend`: `python -m pytest`, `python -m ruff check`, `python -m mypy app` after the
foundational refactor and after each feature. From `apps/frontend`: existing
lint/typecheck/build/test scripts (read `package.json` for exact script names before running).
Acceptance criteria per feature are listed in each section above, following the existing
fake-manager pattern in `test_campaign_assistant.py`/`test_general_assistant.py` (a fake object
implementing `generate_structured`, injected via `app.state.campaign_assistant_manager`). A manual
live-Ollama smoke test against real `llama3.2:3b` for each new endpoint before considering a
feature done, matching the non-automated bullet already in `AI_INTEGRATION_ARCHITECTURE.md` §21.

### Critical files

- `apps/backend/app/domains/campaign_assistant/ollama.py`, `manager.py`, new `gate.py` (foundational)
- `apps/backend/app/domains/outreach/service.py`, `schemas.py`, new `prompt.py` (outreach refine)
- `apps/backend/app/domains/lead_assistant/` — new domain (filter, briefing, autofill, digest)
- `apps/backend/app/domains/automation/enrichment.py` (autofill)
- `apps/backend/app/domains/leads/service.py`, `schemas.py`, new `activity.py` (autofill, digest)
- `apps/backend/app/core/config.py` (digest new setting)
- `apps/frontend/src/components/EmailDraftsWorkspace.tsx` (outreach refine, autofill)
- `apps/frontend/src/components/LeadWorkspace.tsx` (filter, digest)
- `apps/frontend/src/components/PipelineWorkspace.tsx` (briefing)
- `apps/frontend/src/api.ts`, `types.ts`, `WorkspaceActionsContext.tsx`, `App.tsx` (all 5)
- `docs/architecture/AI_INTEGRATION_ARCHITECTURE.md` (new invariants + source map, once built)
