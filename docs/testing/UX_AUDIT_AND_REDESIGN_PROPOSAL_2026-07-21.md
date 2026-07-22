# Etch 'N' Shine Lead Intelligence App — UX Audit and Navigation Redesign Proposal

| Field | Value |
|---|---|
| Date | 2026-07-21 |
| Method | Full source review (no screenshots supplied — audited against live component/CSS source, which is authoritative) |
| Scope | App shell, all 8 workspace sections, design tokens, shared components |
| Prior round | [`workflow-audit-2026-07-19/report.md`](workflow-audit-2026-07-19/report.md) — introduced task-tabs to split 6 overloaded screens. This is round 2, building on that baseline. |
| Status | **Proposal only — no implementation.** Approval-ready. |

---

## A. Executive assessment

### What's working well

- The 2026-07-19 tabbing pass already solved the biggest structural problem (multiple unrelated workflows sharing one scrolling page) for Campaigns, All leads, Catalogue, Pipeline and Settings. That decision should stand — round 2 works *within* that tab structure, not against it.
- `TaskTabs`/`TaskPanel`, `SectionHeading`, `EmptyState`/`LoadingState`, and `Pagination` are already genuinely shared and reused consistently across every screen. This is a strong foundation — round 2 should extend this pattern, not replace it.
- The brand system (navy/gold palette, control heights, spacing scale, border tokens) is coherently tokenized in `:root` and consistently referenced almost everywhere.
- Loading/empty state handling is granular and screen-appropriate (e.g. Shortlist distinguishes "no shortlist yet" from "no eligible leads"; Dashboard handles its three panels independently).

### The five most important usability problems

1. **`CampaignWorkspace.tsx` (1224 lines) is still doing too much inside one tab.** Tabbing separated the four *top-level* workflows, but the Social tab alone nests a second-level `TaskTabs` three levels deep (Campaigns tab → Social panel → Instagram/Facebook sub-tabs) plus a two-column layout and a conditional metrics card. This is the single densest, most disorientating screen in the app. **P0.**
2. **The "inline expand-in-place edit" pattern is implemented three different, inconsistent ways** (Campaigns: controlled-state toggle; Catalogue/Templates: native `<details>`), and in Campaigns it injects a 17-field form directly into a scrolling list row, pushing everything below it far down the page. **P1.**
3. **No real typographic scale.** ~40 distinct hand-picked `font-size` values exist across `styles.css`, 8 of them within a visually indistinguishable 0.64–0.74rem band. This is invisible to a user in any single screenshot but makes every screen subtly inconsistent with its neighbors and multiplies the CSS surface engineers have to reason about. **P1.**
4. **Inconsistent destructive-action confirmation.** Lead deletion requires typing the literal word "DELETE"; Template deletion is a two-click button toggle. Two different intensities for two different-severity actions is defensible in principle, but it isn't a *documented* rule anywhere — it reads as accidental rather than deliberate. **P1.**
5. **The global navigation order doesn't reflect the operating workflow.** Catalogue and Templates (configuration/reference data) sit between "All leads" (acquisition) and "Weekly shortlist"/"Pipeline" (operations), breaking the natural left-to-right journey described in the app's own workflow (campaign → discover → score → shortlist → pipeline). **P1.**

There is also one outright CSS bug worth fixing regardless of the broader redesign: `.lead-contact-routes a` (`styles.css:1828`) references `var(--color-accent, #e1bd86)` — a custom property that is never defined anywhere else in the file (the app uses `--ens-*` naming everywhere else) and a hardcoded fallback gold (`#e1bd86`) that doesn't match either brand gold token (`#ddbf93`). It currently renders correctly only because the fallback happens to be *close* to brand gold — it is one CSS variable rename away from silently breaking. **P0, near-zero risk, one-line fix.**

### Recommended redesign direction

Do **not** rebuild or re-tab anything. Round 2 is refinement inside the existing shell and tab structure:
- Split `CampaignWorkspace.tsx` into per-tab sub-components (no behavior change — pure extraction) and demote the Social tab's nested tabs to a flatter selector-driven layout.
- Introduce a single shared `<InlineEditToggle>`/expand pattern used identically by Campaigns, Catalogue, and Templates.
- Introduce a minimal type scale (5–6 sizes) and migrate the ad-hoc font-sizes onto it opportunistically as touched, not as a big-bang rewrite.
- Document (and lightly adjust) the destructive-confirmation rule: type-to-confirm for account/data-loss actions (lead delete), two-step confirm for reversible/low-blast-radius actions (template delete) — already close to correct, just needs to be a named, intentional pattern rather than two accidental one-offs.
- Reorder the sidebar into three visually grouped clusters (Acquisition / Operations / Configuration) with a small non-interactive group label above each — same routes, same counts, same active-state logic.

### Expected operational improvement

- Fewer clicks-to-context-loss in Campaigns (flattened Social tab).
- Faster visual scanning once font sizes stop competing at near-identical weights.
- A predictable "how do I edit this row" pattern across three screens instead of three different affordances.
- A sidebar that reads top-to-bottom as the actual weekly workflow, reducing "which section do I use for X" hesitation for new operators.

None of the above touches scoring, campaign logic, shortlist logic, discovery-provider behavior, API contracts, or the database.

---

## B. Screen-by-screen audit

Severity/priority key: **P0** critical usability problem · **P1** high-value improvement · **P2** useful refinement · **P3** optional polish.

### B.1 App shell (header + sidebar) — `App.tsx`

| | |
|---|---|
| Strengths | Fixed single-viewport grid with one scrolling region is a good pattern for a dense operational tool; `ConnectionBadge` and the run indicator communicate live state without a full page reload. |
| Friction | (a) Header's "Workspace / Local lead intelligence" label is static — doesn't reflect which of the 8 sections is active, wasting the one piece of header real estate that could orient the user. (b) Two overlapping `useEffect`s both reset scroll position on section change (`App.tsx:274-279` and `:337-341`) — redundant, not user-visible but worth cleaning up while touching this file. (c) `--ens-sidebar-collapsed` token exists but no collapse interaction is implemented — sidebar is full-width-or-horizontal-strip only. |
| Proposed change | Make the header context label dynamic (derive from `activeSection`'s label). Merge the two scroll-reset effects. Leave the collapse token as dead/removed rather than half-implemented (see D.2). (Verified during implementation: the success toast is `position: fixed`, so it already behaves as a floating notification independent of the active section — briefly persisting across a navigation is standard toast behavior, not a bug. Withdrawn from scope.) |
| Priority | P1 (dynamic header context), P3 (effect cleanup, dead token removal) |
| Risk | Low — presentation only, no state-shape change. |

### B.2 Overview / Dashboard — `DashboardWorkspace.tsx`

| | |
|---|---|
| Strengths | Compact (202 lines), no unnecessary framing, three independently-loading panels, click-through rows go straight to the relevant workspace. |
| Friction | 5 `MetricCard`s in a hardcoded `repeat(4, 1fr)` grid (`.metrics-grid`) — the 5th card wraps alone onto its own row, visually orphaned. |
| Proposed change | Change the grid to `repeat(auto-fit, minmax(200px, 1fr))` (or an explicit 5-column definition) so all 5 metrics sit on one row at desktop widths and wrap evenly at narrower ones. |
| Priority | P2 |
| Risk | Low — CSS-only. |

### B.3 Campaigns — `CampaignWorkspace.tsx` (1224 lines)

This is the file with the most findings; already flagged as the #1 executive priority.

| | |
|---|---|
| Strengths | The four top-level tabs (Register / Create / Automation / Social) are the right split and already shipped in round 1. Automation run cards present a clear 6-stat summary per run. |
| Friction | (a) **Social tab nests a second `TaskTabs` inside the first** (Instagram import / Find profiles / Facebook capture), itself laid out as a 2-column form-plus-preview — the deepest nesting in the app (Section → Tab → sub-Tab → 2-col layout → conditional preview card). (b) **Campaign register's inline edit is a 17-field form injected directly into the scrolling list row** (`CampaignWorkspace.tsx:1091-1201`) — opening one edit can push every campaign below it off-screen. (c) Automation tab stacks two independently-paginated lists (run history + duplicate-candidate review) in one tab — a lot to scan even after the top-level split. (d) The single file mixes four different concerns (register/create/automation/social), each large enough to be its own component. |
| Proposed change | Extract each tab's content into its own component file (`CampaignRegisterTab.tsx`, `CampaignCreateTab.tsx`, `CampaignAutomationTab.tsx`, `CampaignSocialTab.tsx`) — pure extraction, `CampaignWorkspace.tsx` becomes a thin tab-router. Flatten the Social tab's nested tabs into a single selector (segmented control or select) that swaps the panel content, removing one level of nesting. Convert the register's inline edit into the shared inline-edit pattern proposed in D.4 with a capped max-height + internal scroll so it can't push the whole list off-screen. Give the duplicate-review list its own visually separated sub-heading with a collapsed-by-default state when empty (already conditional; make the "has items" state visually distinct from run history via a divider/heading rather than just stacking). |
| Priority | P0 (file split + Social flattening), P1 (inline-edit containment) |
| Risk | Medium for the component split (pure refactor, but high line-count file — mitigate with incremental extraction, one tab at a time, running tests after each). Low for the CSS-only containment fix. |

### B.4 All leads register — `LeadWorkspace.tsx`

| | |
|---|---|
| Strengths | Already tab-split (Browse / Add) from round 1. Filter bar (5 controls) sits directly above the table. Good empty-state differentiation (no leads at all vs. no leads matching filters). Compact, single-purpose. |
| Friction | The "Business" column stacks name + segment + phone + email in one cell — four distinct facts compressed into one visual block, harder to scan a column of names quickly. |
| Proposed change | Keep business name as the sole primary line in that column; move phone/email into their own (narrower) column or into a hover/expand affordance, consistent with how Pipeline already separates contact routes. This is a column-reprioritization, not a data-removal — every field currently shown stays visible. |
| Priority | P2 |
| Risk | Low — table markup change only, no data or filter logic touched. |

### B.5 Weekly shortlist — `ShortlistWorkspace.tsx`

| | |
|---|---|
| Strengths | Compact generator form (one row), good 3-way empty-state handling, decision-gated action buttons (Approve/Defer/Dismiss/Replace only show for `recommended` items). |
| Friction | 2-column card grid makes side-by-side comparison of more than 2 candidates require scrolling; score/rationale sit inside prose rather than being independently scannable at a glance across cards. |
| Proposed change | As per the original brief's 5.8: keep the card format (it already carries rich per-lead rationale that a table would flatten) but tighten card height — pull score and product-fit into a compact stat row at the top of the card (already-existing data, just repositioned) so a user can compare 4+ cards without opening each one mentally. Do not convert to a table — the original audit brief explicitly leaves this to judgment, and the card format is closer to the "compare qualitative rationale" job this screen does. |
| Priority | P1 |
| Risk | Low-medium — layout/positioning of already-rendered fields, no new data, no change to Approve/Defer/Dismiss/Replace logic or persistence. |

### B.6 Pipeline workspace — `PipelineWorkspace.tsx` (882 lines)

| | |
|---|---|
| Strengths | Round 1's 6-tab split (Overview / Contact / Score & products / Opportunity / Activity & follow-up / Privacy) correctly isolates high-risk privacy actions from daily sales work. Master-detail layout (250px selector + detail pane) is the right shape for this job. |
| Friction | (a) **The activity timeline renders as a sibling block after the `TaskPanel` closes** (`PipelineWorkspace.tsx:847-874`) rather than inside the Activity & follow-up tab's own panel boundary — a structural inconsistency that likely also means the timeline isn't correctly associated with its tab for assistive tech (`role="tabpanel"` semantics). (b) That same tab bundles 3 forms (Notes / Follow-ups / Manual communication) plus 2 paginated lists — the densest single tab in the app. (c) Score & products tab has no sub-sectioning beyond native `<details>` for its evidence breakdown — metrics row, breakdown grid, product matches and override form all compete in one flow. |
| Proposed change | Move the timeline block inside the Activity & follow-up `TaskPanel` (fixes both the visual grouping and the a11y association) — presentation-only, zero data change. Within that tab, group the 3 forms under a lightweight 2-column layout (forms left, timeline+list right) rather than fully stacked, matching the pattern Settings already uses for Data & backup. Add a `SectionHeading`-style sub-label above each of the Score tab's three zones (metrics / evidence / override) for scan-ability, no new component needed. |
| Priority | P1 (timeline placement — also technically a correctness fix), P2 (form regrouping, score tab sub-labels) |
| Risk | Low — the timeline move is a JSX relocation with no data/prop changes; verify existing Pipeline tests still target the right DOM region. |

### B.7 Catalogue / Products — `CatalogueWorkspace.tsx`

| | |
|---|---|
| Strengths | Already tab-split (Products / Add product / Import / Scoring model) from round 1. Products tab reuses the same card/grid CSS as Templates — good cross-screen consistency. |
| Friction | (a) Add product tab exposes only 3 of the ~8 fields `ProductInput` accepts (description, use-cases, image-reference, pricing-guidance, sample-eligible are hardcoded via hidden inputs at creation, only editable afterward via the per-card edit form) — a real inconsistency between "quick add" and "full edit," though not a UI bug per se. (b) Scoring tab's 7 weight inputs must sum to 100, but this is stated only in a description line — no live running total shown while typing. |
| Proposed change | (a) Optionally expose the remaining fields in Add product using the same field set already defined in the per-card edit form (no new fields, no schema change — purely surfacing existing accepted input in one more place). Flag this one for explicit confirmation since it changes the Add-product form from 3 fields to ~8 — a bigger visual change than the rest of this batch, even though it's zero functional/API change. (b) Add a live running-total readout next to the weight grid, computed client-side from the same 7 fields already bound to the form. |
| Priority | P1 (live weight total — pure UI, clear win), P2 (Add product field parity — recommend confirming appetite before building since it enlarges a currently-short form) |
| Risk | Low for both — no backend, schema, or validation-rule change; the weight total is a derived display value, not a new validation path (the server already validates the sum). |

### B.8 Templates — `TemplatesWorkspace.tsx`

| | |
|---|---|
| Strengths | Smallest, cleanest screen in the app (226 lines). Reuses Catalogue's card/grid CSS well — verified during implementation that `template.body` and `product.description` are both direct-child `<p>` elements of `.catalogue-card`, so the existing `.catalogue-card > p` 4-line clamp already applies identically to both. No change needed here; the round-1 exploration pass that flagged this as unclamped was incorrect. |
| Friction | None found on closer inspection. |
| Priority | Withdrawn |
| Risk | N/A |

### B.9 Settings — `SettingsWorkspace.tsx`

| | |
|---|---|
| Strengths | Already tab-split (Connections / Defaults / Data & backup / Diagnostics) from round 1, verified at 1024×768 in the prior audit. |
| Friction | Connections/Meta card stacks up to 7 conditional sub-blocks (status, OAuth callout, App ID/Secret form, connect button, manual-fallback box, account selector, error message, disconnect controls) — even though most are mutually exclusive at runtime, the card's *maximum* height is the tallest single card in the app, and a first-time (fully-unconfigured) user sees several of these at once. |
| Proposed change | Group the conditional blocks into 2 explicit visual states ("Not connected" vs "Connected") with a single active container per state, instead of one container holding all 7 conditionally-rendered children — same conditions, same fields, just grouped so only the relevant state's card renders. |
| Priority | P2 |
| Risk | Low-medium — touches conditional rendering logic, so needs care to keep every existing condition byte-for-byte equivalent; recommend covering with a rendering test per connection state before refactoring. |

---

## C. Proposed information architecture

### Revised global navigation

Group the existing 8 items into 3 visually labelled clusters, same routes/order-within-cluster mostly preserved, only Catalogue/Templates move past Weekly shortlist/Pipeline:

```
LEAD ACQUISITION
  Overview
  Campaigns
  All leads

LEAD OPERATIONS
  Weekly shortlist
  Pipeline

CONFIGURATION
  Catalogue
  Templates
  Settings
```

- Group labels are small uppercase non-interactive `<div>`s above each cluster (mirrors the `SectionHeading` eyebrow-text pattern already used inside workspaces) — no new interaction pattern introduced.
- Every route, count badge, icon, and active-state highlight is preserved exactly; only the surrounding list order and the addition of 2 label rows change.
- This turns the sidebar into a left-to-right reading of the actual weekly workflow described in the app's own operating model (campaign → discover → score → shortlist → pipeline), with reference/config data pushed to the bottom where it belongs.

### Page relationships / journey

Unchanged from current behavior — Overview's action rows already deep-link into Pipeline/Weekly shortlist; "Manage" from All leads and "Open lead" from Weekly shortlist already route into Pipeline with the correct lead pre-selected (fixed in round 1's ISSUE-002). No new linking behavior proposed.

### Breadcrumbs

Not needed — the app is single-level (8 flat sections, no nested routes), and the dynamic header context label proposed in B.1 already gives "where am I" orientation without a second navigation element competing for header space.

---

## D. Proposed wireframe descriptions (text, low-fidelity)

### D.1 Overview

```
[Page header: "Overview" | New campaign]
[Metrics strip: 5 metric cards, one row, evenly wrapped]
[Section: Operating queue]
  [Weekly shortlist panel] [Open follow-ups panel]
  [Pipeline summary panel — spans both columns below the pair, unchanged]
```

### D.2 Campaign register (Campaigns tab)

```
[Page header: "Campaigns" | tabs: Register* / Create / Automation / Social]
[Search control, right-aligned above list]
[Campaign card list]
  [Card: identity | status | stats dl | actions row]
  [Card, expanded: same as above, PLUS capped-height scrollable inline edit panel below]
```

### D.3 Campaign creation (Create tab)

```
[Page header: "Campaigns" | tabs: Register / Create* / Automation / Social]
[Form panel, bounded width — unchanged field set and order]
[Create button — unchanged position]
```
No structural change proposed here beyond what round 1 already delivered; this screen was not flagged in round 2 findings.

### D.4 Automation centre (Automation tab)

```
[Page header: "Campaigns" | tabs: Register / Create / Automation* / Social]
[Provider readiness + bulk-run toolbar]
[Run history list — heading: "Recent runs (N)"]
[Divider]
[Duplicate review — heading: "Needs review (N)", collapsed if N=0]
```

### D.5 All leads

```
[Page header: "All leads" | tabs: Browse* / Add]
[Filter bar: search, campaign, source, stage, suppression]
[Table: Business name | Phone/Email | Source | Stage | Location | Next action | Contact | Manage]
[Pagination]
```

### D.6 Weekly shortlist

```
[Page header: "Weekly shortlist"]
[Generator row: campaign, week, capacity, Generate]
[Card grid, 2-col]
  [Card: rank | name/segment/location | compact stat row (score, product fit) | reason | actions]
```

### D.7 Pipeline

```
[Page header: "Pipeline"]
[Left: search + lead selector list + pagination]
[Right: lead header (name, routes, badges)]
  [tabs: Overview / Contact / Score & products / Opportunity / Activity & follow-up* / Privacy]
  [Activity & follow-up panel]
    [Notes form] [Follow-ups form + list]
    [Manual communication form]
    [Activity timeline — now inside the panel boundary]
```

---

## E. Component standardisation plan

| Component | Purpose | Current state |
|---|---|---|
| `InlineEditToggle` | One shared expand/collapse-to-edit affordance | 3 divergent implementations today (Campaigns state-toggle, Catalogue/Templates `<details>`) — consolidate to one, used by all three |
| `StatGrid` | Bordered `<dt>/<dd>` metric tile grid | 5 bespoke implementations today (automation metrics, pipeline summary, opportunity value summary, diagnostics grid, Instagram preview metrics) — consolidate presentation, keep each screen's data |
| `DangerConfirm` | Destructive-action confirmation, with a `intensity: "type-to-confirm" | "two-step"` prop | Two one-off implementations today; formalize as one component with the two already-in-use modes |
| `PageHeader` | Title + primary action + optional context line | Implicit today via `page-intro` CSS class repeated per screen — extract to a component for consistency, no visual change |
| `MetricCard` | Already exists, single-consumer (Dashboard) | Reuse for Diagnostics' stat tiles instead of its hand-rolled `<dl>` |

Do not build: `Modal`/`Drawer` as a new generic overlay system — the app deliberately uses inline expansion everywhere today (per the structural map, no modal exists anywhere), and introducing one would be the kind of "redesign for its own sake" the brief explicitly rules out. The one place this was considered (Campaign register's 17-field inline edit) is better served by capping and scrolling the existing inline panel than by introducing a new interaction paradigm app-wide.

---

## F. Change matrix

| Screen | Current issue | Proposed change | Priority | Functional change? | Dev complexity | Regression risk |
|---|---|---|---|---|---|---|
| App shell | Static header context label | Derive label from active section | P1 | No | Low | Low |
| App shell | Duplicate scroll-reset effects | Merge into one effect | P3 | No | Low | Low |
| Global CSS | Orphaned `--color-accent` var | Point at `--ens-text-accent` | P0 | No | Trivial | None |
| Dashboard | 5 cards in 4-col grid | `auto-fit` grid | P2 | No | Trivial | Low |
| Campaigns | 1224-line single file | Extract per-tab components | P0 | No | Medium | Medium |
| Campaigns | Social tab 3 levels deep | Flatten nested tabs to one selector | P0 | No | Medium | Medium |
| Campaigns | 17-field inline edit in list row | Shared capped/scrollable inline-edit component | P1 | No | Medium | Low |
| Campaigns | Two stacked paginated lists in Automation tab | Add divider + collapsed-when-empty heading | P2 | No | Low | Low |
| All leads | 4 facts packed in one table cell | Separate phone/email into own column | P2 | No | Low | Low |
| Weekly shortlist | Hard to compare >2 cards | Compact stat row at card top | P1 | No | Low | Low |
| Pipeline | Timeline outside its tab panel | Move inside Activity & follow-up panel | P1 | No | Low | Low (verify test selectors) |
| Pipeline | Activity tab bundles 3 forms + 2 lists | 2-column regroup within tab | P2 | No | Medium | Low |
| Pipeline | Score tab lacks sub-sectioning | Add sub-labels to 3 zones | P2 | No | Low | Low |
| Catalogue | Add product exposes 3/8 fields | Expose remaining existing fields | P2 | No (surfaces existing accepted fields) | Low | Low — confirm appetite first |
| Catalogue | No live weight-sum total | Add derived running total | P1 | No | Low | Low |
| Settings | 7 conditional blocks in one card | Group into 2 explicit connection-state containers | P2 | No | Medium | Medium — cover with per-state test first |
| Sidebar | Nav order breaks workflow | Reorder into 3 labelled clusters | P1 | No | Low | Low |
| Design tokens | ~40 ad-hoc font sizes | Introduce 5–6 size scale, migrate opportunistically | P1 | No | Ongoing/low per-touch | Low |

---

## G. Acceptance criteria

- No feature, route, field, button, or data value present today is removed or hidden without an explicit approved exception.
- Maximum scroll depth: no single tab panel should require more than ~2.5 viewport heights of scrolling at 1366×768 to reach its last control (currently Campaigns' Social tab and Pipeline's Activity tab exceed this — both addressed above).
- Primary action (the one most-used button per screen) remains visible without scrolling on a 1366×768 viewport.
- Core workflow click counts do not increase: Create campaign, Run discovery, Find/manage a lead, Review shortlist, and Manage pipeline lead all complete in the same or fewer clicks than today.
- Selected context (active tab, selected lead, active campaign, search/filter state, pagination position) survives every proposed change exactly as it does today — none of the above changes alter state-preservation behavior.
- Responsive: no horizontal page overflow, no clipped/overlapping controls, at 1920×1080, 1600×900, 1440×900, and 1366×768. Sidebar behavior below 900px (already a horizontal strip) is unchanged.
- Keyboard: existing `TaskTabs` arrow-key navigation (already implemented per the 2026-07-19 audit) continues to pass; any newly-extracted components preserve existing tab/focus order.
- Zero change to API request/response shapes, database schema, scoring/qualification logic, campaign/discovery logic, or shortlist logic.
- All 37 backend tests and all existing frontend tests continue to pass; new tests added only for genuinely new DOM structure (e.g. Pipeline timeline relocation, Settings connection-state grouping).

---

## H. Implementation sequence

1. **Zero-risk fixes first** (can ship independently, immediately): CSS variable fix (`--color-accent`), Dashboard metrics grid, Templates card clamp — all trivial, no test risk.
2. **Shared component extraction**: `InlineEditToggle`, `StatGrid`, `DangerConfirm`, `PageHeader` — build against existing screens' current markup one at a time, verifying no visual/behavioral diff before moving to the next screen.
3. **Navigation**: sidebar reordering + group labels + dynamic header context label.
4. **Campaigns split**: extract per-tab components, then flatten the Social tab's nested tabs — the largest single change, done last among "high-traffic" work so the shared components from step 2 are already available to reuse inside it.
5. **Pipeline**: timeline relocation (verify test selectors first), Activity tab regrouping, Score tab sub-labels.
6. **Weekly shortlist**: compact stat row.
7. **Catalogue**: live weight total, then (only if confirmed) Add-product field parity.
8. **Settings**: connection-state grouping, covered by a rendering test per state before refactor.
9. **Typography**: introduce the scale as a token addition (additive, non-breaking), then migrate obviously-adjacent duplicate sizes opportunistically rather than in one pass.
10. **Full regression pass**: backend pytest, frontend vitest, ESLint, mypy/tsc, production build, manual pass at all 4 documented viewports.

Rollback: every stage above is an independently revertible commit (per the implementation prompt's "small, reviewable stages" requirement) — no stage depends on a later one, so any stage can be reverted without unwinding subsequent work except stage 4 (Campaigns), which depends on stage 2's shared components being in place first.
