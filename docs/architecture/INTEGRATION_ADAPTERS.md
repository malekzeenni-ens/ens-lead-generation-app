# Integration adapters

**Status:** Google Places, official Instagram discovery, bounded public-site enrichment, assisted social capture and operator-controlled email handoff implemented; automatic outbound messaging disabled

The local core depends only on domain interfaces. Provider DTOs and raw payloads must not become canonical tables. Every adapter requires policy/terms confirmation, least-privilege credentials, timeouts, retries, budgets, audit evidence, operator-visible failure states, and a manual fallback.

| Boundary | Approved mode | Gate before enablement | Fallback |
|---|---|---|---|
| Google Places/Text Search | Implemented official Text Search (New) plus Geocoding v4; operator-triggered, selected fields, query/result caps and exact radius post-filter | Restricted key, billing/budget alert and operator campaign selection | Existing/manual leads |
| Meta/Instagram | Official Facebook Login and Business Discovery for operator-selected or already-saved professional profiles; direct hashtag links assist selection; no scraping or DM | App-role testing now; required permissions; Meta review/business verification before unrelated accounts | Prepared public search and verified Facebook capture |
| Public websites | Implemented bounded enrichment for home plus at most two same-domain contact/about pages | Public-IP DNS validation, redirect revalidation, robots, MIME/size/time limits; ongoing adversarial review | Keep provider evidence without enrichment |
| AI provider | Advisory, minimised evidence packets, schema-constrained outputs | DPA/privacy choice, prompt/evidence validation, budgets, audit metadata | Deterministic/manual workflow |
| Zoho | Assisted `mailto:` handoff of the current approved version through the OS default composer; no Zoho API or direct send | Fresh suppression/contact/hold/stage and version-bound approval check before each open; operator must configure Zoho as the default composer | Approved body is also copied to clipboard |
| Email/social hand-off | Human-approved content only; no autonomous send; opening a composer is not sending evidence | Suppression/legal gates plus explicit post-send operator confirmation | Manual copy/open workflow |
| Shopify | Operator-selected local product-export CSV; API sync deferred | File size/row/header validation and local-only normalisation are implemented | Manual catalogue entry/edit |

## Port contract

Google and Instagram adapters return normalised candidates with provider identity, source URL, query summary and request count. Google discovers new businesses and supplies exact distance evidence. Instagram enriches a profile URL selected by the operator, or profiles already attached to campaign leads; its campaign location is review context and is not an exact-radius claim. Raw provider payloads and homepage HTML are not retained. Domain services stage candidates, apply exclusions/suppression, resolve exact matches, send ambiguous fuzzy matches to review, and only then promote canonical leads.

## Failure policy

Missing credentials skip discovery and complete the run with a warning; existing-lead scoring still runs. Provider/geocoding failures are recorded as safe provider attempts and do not change existing lead data. Weekly preparation catches up when the app opens and isolates a failed campaign for operator retry; there is no operating-system scheduler or blind provider retry while the app is closed. An adapter outage does not prevent viewing, editing, manual capture, scoring, or matching local data.

The Shopify CSV path is not an external adapter call: the browser reads the selected file, the authenticated loopback API validates and normalises the content, and the raw file is not retained. It requires no Shopify credentials and provides no live inventory, order, or product synchronisation.
