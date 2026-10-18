# ADR-022: Background jobs for long local AI work

- **Status:** Accepted (18 October 2026)
- **Context:** Some local AI work ran inside a single HTTP request. Lead autofill handled up to 20 leads, each with a website fetch and up to 120 seconds of model time. Catalogue enrichment handled up to 200 products, which could take hours. The frontend had no timeout, progress or cancel, and enrichment held the app-wide busy state for the whole run. Enrichment had stayed in the foreground on purpose: every local generation shares one non-blocking model lock, so a background run would have made the operator's own assistant requests fail with "busy".
- **Decision:** A small general job runner, `app/jobs/`, with a `background_job` table (migration `0019`). Feature endpoints submit a job and return it with `202`. The frontend follows it by polling `GET /jobs/{id}` every 1.5 seconds, shows progress, and cancels with `POST /jobs/{id}/cancel`.

## How it works

- One worker thread. Jobs could not run model calls in parallel anyway, because they share the model lock.
- A handler gets its own session and a `JobContext`. `report_progress(current, total)` commits, so work finished before a cancellation is kept. The handler checks `cancelled()` between steps and raises `InterruptedError` to stop.
- **Sharing the model with the operator:** a job passes `cancelled=` to `generate_structured`. That makes it wait for the lock (checking for cancellation every second) instead of failing as busy. Interactive requests still fail fast rather than queue behind a job. So between a job's steps, the operator's own chat or refine request goes first.
- Outcomes: `succeeded` with a JSON `result`; `failed` with the `DomainError` code and message, or `JOB_FAILED` (logged with its traceback) for anything unexpected; `cancelled`; `interrupted` when the app closed mid-run.
- Startup recovery requeues jobs that never started and marks running ones `interrupted`; they are not resumable.
- `one_at_a_time=True` refuses a second active job of the same kind (`409 JOB_ALREADY_ACTIVE`), used for enrichment.
- Preconditions (local AI enabled, engraving software not running) are checked when the job is submitted, so the operator hears at once, and again when it starts.
- Every transition is logged with the job ID and kind.

## Kinds

| Kind | Endpoint | Why |
|---|---|---|
| `lead_autofill` | `POST /lead-assistant/autofill` | Up to 20 leads, each a website fetch plus a model call |
| `catalogue_enrichment` | `POST /catalogue/enrichment/run` | Up to 200 products, one model call each |

Single interactions stay synchronous: an assistant chat message, a campaign draft generation or refinement, a draft refine or polish, a lead briefing. Each is one model call that the operator waits for. The frontend gives these 200 seconds and other requests 60 seconds; a timed-out request says the work may still finish.

`CampaignRunManager` keeps its own richer model (phases, candidates, weekly batches) and was not folded in. That remains an option if the two converge.

## Consequences

- No request runs longer than one model call.
- The frontend's `api.autofillLeads` and `api.runEnrichment` keep their result types. They start the job and resolve with its result, taking optional `onProgress` and `signal`.
- Tests run jobs inline (`campaign_run_inline`); `test_background_jobs.py` drives the real worker thread for progress, cancellation, failures, recovery, the one-at-a-time rule and waiting for the model.
