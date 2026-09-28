# ADR-021: Product sales knowledge, no pricing, and a choosable local model

- **Status:** Accepted
- **Context:** After ADR-020 the assistant knew the brand voice but not the products, so it could not answer "which products suit a physio clinic?" with anything useful. Three measured causes. The Shopify export reaches the model almost empty: `Type` is filled on 22 of 840 rows, so `category` fell back to a taxonomy path, and no listing uses the `segment:` or `use-case:` tag prefixes the importer looked for, so `target_segments` and `example_use_cases` were empty for every product while `description` was imported but never sent. Pricing leaked into both the assistant snapshot and the `{{products}}` email token, though pricing is quoted per job. And products missing from a newer export stayed active forever.
- **Decision:** Derive sales fields from the CSV, import the shipped `product_enrichment.json` pack on top, rank products per request, and add a knowledge layer of trade notes and past jobs. Retire products absent from a newer export. Allow a larger local model to be chosen from Settings.

## Two rules enforced in code, not in the prompt

A rule the data cannot break is worth more than a rule the model is asked to follow, so both of these live in `assistant/context.py` rather than in prompt text:

- **No pricing reaches a model or an email.** `pricing_guidance` stays in the database for the operator's own reference and is removed from the snapshot and from `{{products}}`. `strip_prices` also scrubs price phrasing out of any summary or note, including a percentage or a "bundle and save", because a percentage is a price. `tests/test_product_knowledge.py` fails if a `£` appears anywhere in a snapshot built from catalogue data.
- **An unconfirmed job never carries its client's name.** `_fit_summary` substitutes the anonymous label unless the fit is confirmed *and* name sharing was allowed. The prompt says the same thing, but the prompt is the second line of defence.

## Ownership of enrichment

`enrichment_source` records who last wrote a product's sales knowledge, and precedence is `manual` > `seed` > `ai` > never enriched:

- A CSV import always refreshes the fields the CSV owns, and fills sales fields only on a product that has never been enriched.
- Editing any sales field by hand marks the product `manual`, which nothing else overwrites.
- The AI run targets never-enriched products. Refreshing a changed listing is opt-in.

**Why stale refresh is opt-in, against the pack's own rule.** The pack says `seed` may be replaced when the listing's `source_hash` changes. Taken literally that would have destroyed the pack's value immediately: the pack was generated from the live Shopify API on 27 September while the local export dates from 19 July, so 74 of 104 matching titles already differ and only 2 of 104 hashes agree. Staleness is therefore baselined against *this database* — `enriched_hash` is set to the current fingerprint when enrichment is applied — so it means "the listing changed after we enriched it here", and replacing seed content needs the operator to ask.

## Retrieval

A fully enriched product costs roughly 170 tokens, so sending thirty would crowd out everything else. Products are scored on name, category, summary, materials, trades, use cases and occasions against the request terms plus the selected lead's trade, with a bonus for business-ready products when the context is a lead, campaign, batch or shortlist. The top five go in full and the next seven as a name plus a line. At most two knowledge notes and two past jobs join them. A `_prune` pass drops empty values before serialising.

## Foreground enrichment

The AI enrichment run is a button, not a background job, because every local generation shares one non-blocking lock (`campaign_assistant/manager.py`): a background run would make the operator's own assistant requests fail with a busy error while it worked. It is refused while LightBurn or xTool is running.

## Model choice

`ALLOWED_OLLAMA_MODELS` allows `llama3.2:3b`, `qwen3:8b`, `llama3.1:8b` and `gemma3:12b`, defaulting to the 3B so an existing install keeps working before a larger model is pulled. `Settings` is env-based and not writable from the UI, so the choice is a persisted `local_ai_model` workspace setting that the client prefers over the env default. The protected profile always uses `ollama_protected_model`. A non-3B model gets at least a 16,384-token window; `qwen3` is sent `think: false`.

## Measured results

On the real export: 0 empty categories and no taxonomy paths (previously every fallback was a path), summaries on 93% of products with zero prices, and materials and trades on 97 and 99 products where both were empty for all of them. The pack matched 104 of its 110 handles and added 10 trade notes and 4 past jobs, all unconfirmed. Live against `llama3.2:3b`, "which products suit a physio clinic?" now returns five real product names with a typical order for each.

## Limitations

- **A typical request is about 4,800 prompt tokens, not the 3,000 originally aimed at.** Roughly 2,100 of that is fixed instruction (the system prompt plus the identity) and 2,700 is the snapshot, which came down from 3,454 by removing prose the system prompt already carries, a 51-entry category histogram and over-long excerpts. Reaching 3,000 would mean dropping either the knowledge layer or the outreach rules. On the 3B's 8,192-token window this still leaves room to answer; on an 8B at 16,384 it is comfortable. That is the argument for the model dropdown.
- The 3B still occasionally pads an answer or echoes an instruction back. All AI output remains advisory and reviewable.
- Knowledge notes are refreshed only where this app generated them. Seed notes are better than anything assembled from product summaries, and an edited note is `manual`, so neither is rewritten.
- One shipped past job carries the trade "Wholesale and distributors", which is not in the pack's own 16-trade list. It is imported as given and surfaced in the Knowledge tab rather than silently remapped.

## Alternatives considered

Fine-tuning a local model on the catalogue, rejected because the catalogue changes often and retrieval keeps answers current for far less work; deriving everything from the CSV without the pack, which cannot produce "why a trade buys this"; a background enrichment worker, which fights the generation lock; trusting the prompt to withhold prices and client names, which a test cannot enforce.

## If the local model is not good enough

The Overview "Draft edit rate" is the evidence. If it settles above about 0.25 once a reasonable
number of drafts have been approved, the first lever is a larger local model from the Settings
dropdown. Only if that is already in use and still falls short is a cloud model worth considering,
and that is specified separately in
[Cloud_Draft_Polish_Specification.md](../specifications/Cloud_Draft_Polish_Specification.md) —
deliberately not built, because the measurement has to justify it first.

## Rollback

Set `local_ai_model` back to empty to return to the 3B. The enrichment columns can be left unused: the CSV import path works without the pack, and dropping the pack import leaves products with CSV-derived fields only. Migration `0015` is reversible.
