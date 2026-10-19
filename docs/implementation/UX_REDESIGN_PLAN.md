# UX redesign plan

**Plan date:** 18 October 2026
**Source:** Senior product design review, approved by the operator the same day, plus one addition: the AI assistant as a floating button, like a website's "contact us" button.
**Branch:** `ux/redesign`, one commit per item.
**Scope:** Frontend only. No API, scoring, campaign, outreach or data changes. Every safety rule (manual send, approval gates, suppression, type-to-confirm deletes) behaves exactly as today.

## 1. Goals

From the operator's point of view, the app should:

- answer "what do I do today?" on the first screen;
- show the work before the explanation, with one level of cards per page;
- speak in the operator's words, not the system's;
- remember where they were (filters, page, open sections);
- use motion to explain change, never to decorate;
- keep the AI assistant one click away on every screen.

## 2. How each item is delivered and checked

- **Gates per item:** TypeScript, ESLint (zero warnings), Vitest. Tests that assert old wording are updated to the new wording, never deleted.
- **Visual check per item:** the real app runs locally against a throwaway copy of the database (backend plus Vite dev server), and `agent-browser` screenshots each changed screen at 1366×768 and 720×600 (the window's minimum). Screenshots stay in the scratchpad; none go into the repo, because they would show real business data.
- **Accessibility:** keyboard focus order, visible focus rings, `aria-expanded` and `aria-controls` on every disclosure, focus trapped and restored for drawers and dialogs, and every animation disabled under `prefers-reduced-motion`.
- **Record:** each item gets a `DELIVERY_LOG.md` entry; user-visible changes go in `CHANGELOG.md`; the full `npm.cmd run quality` gate runs at the end of each phase.

## 3. Phase A: Foundations

### A1. Design tokens

- **Type scale:** six steps on `:root`: 12, 14, 16, 20, 24 and 32 px (`--ens-type-xs` … `--ens-type-3xl`). Existing small-text tokens map onto the nearest step; one-off sizes migrate as each screen is touched.
- **Motion tokens:** `--ens-motion-fast` 120 ms, `--ens-motion-base` 200 ms, `--ens-motion-slow` 300 ms; `--ens-ease-out` (enter) and `--ens-ease-in-out` (move). Under reduced motion, all of them become 0 ms.
- **Status semantics:** gold means primary action or needs you; green means done or healthy; amber means attention; red means blocked or destructive; grey means neutral. Fix "Review required" and similar badges currently shown green.
- **Density:** `--ens-row-height` and table padding driven by a `data-density` attribute (used by E1).

### A2. Shared components (`DesignSystem.tsx`)

- **`Collapsible`:** header with chevron, title, optional summary shown when collapsed, optional actions. Open state is remembered per screen. Height animates. A screen-level "Expand all / Collapse all" control.
- **`Drawer`:** right-hand slide-over for editing and previews: title, close button, scrollable body, sticky footer for actions. Focus is trapped and restored, and Esc closes it. Widths: 480 px default, 760 px wide.
- **`StatusPill`:** dot plus label, one shape, the five semantic tones.
- **`Toolbar`:** search, filter chips (each removable), sort, view switch and a result count ("Showing 1–10 of 248"). Sticks below the page header while scrolling.
- **`SkeletonRows`:** placeholder rows shaped like the real ones.
- **`Pagination`:** add a rows-per-page choice (10, 25, 50).
- **`useRememberedState`:** keeps a value per screen for the session (filters, page, view, open sections). Storage access is wrapped in try/catch, with a memory fallback.

### A3. Motion

Page and tab content fades in and rises 6 px (200 ms). Sections expand and collapse with a height animation and a rotating chevron. Drawers slide in, with the background dimmed. Toasts slide up. A row changed by an action is briefly highlighted in gold (800 ms). All of it is turned off under reduced motion.

## 4. Phase B: App shell and navigation

### B1. Header and status

- Replace the "API connected · Local service" badge with a small status dot (tooltip: "Local service running"). When the service is unavailable or restarting, a full-width banner says so, which reuses the existing notice.
- Remove the footer status bar and the sidebar "Controlled mode" card. Their information moves to Settings → About as a "How this app protects you" panel, and to small chips where it matters.

### B2. Sidebar

- **Groups:** **Find** (Overview, Campaigns, All leads), **Work** (Weekly shortlist, Pipeline, Email drafts), **Set up** (Catalogue, Templates, Settings).
- **Badges** show only work that needs the operator, in gold: leads needing review, follow-ups due today or overdue, drafts awaiting approval, and an unseen shortlist. Plain totals are removed.
- **Collapse to icons** (tooltips on hover and focus), remembered between sessions. On a narrow window it collapses automatically.

### B3. Floating AI assistant (operator addition)

- A round gold button, bottom-right on every screen, with a sparkle icon and a "Ask AI" label that appears on hover. It shows a dot when the local model is not ready.
- Opens an assistant panel that slides up from the button: about 440×640 px, resizable to a wide mode (about 900 px) for reviewing a campaign draft.
- The panel hosts the existing assistant unchanged: App copilot and Campaign draft modes, conversations, attachments and the context picker.
- "Ask AI" actions elsewhere (lead row, pipeline) open the panel with that context instead of switching screens.
- The "AI assistant" sidebar entry is removed. Campaigns → New campaign gets "Plan with AI", which opens the panel in Campaign draft mode.
- The conversation survives closing and reopening the panel. The panel is created on first open, so the model status isn't checked at startup. Esc closes it and focus returns to the button.

### B4. Global search (Ctrl+K)

A command palette that finds screens ("Go to Pipeline"), leads, campaigns, products and templates by name from data already loaded, plus quick actions (new campaign, add lead, ask AI). Keyboard first: arrows move, Enter opens, Esc closes. Results are grouped by type.

## 5. Phase C: Page anatomy and wording

### C1. One level of cards

`PageHeader` (title, a one-line description only where needed, primary action on the right), then the toolbar, then content. Remove the repeated eyebrow, title and description inside cards ("Campaign register" twice). Keep `SectionHeading` only where a page genuinely has several sections.

### C2. Wording

An operator-language pass across every screen. Examples:

- "Discover & refresh scoring" → "Find new leads";
- "Campaign register" → "Your campaigns";
- "Operating queue" → "Today";
- "Lead intelligence dashboard" → "Overview".

Descriptions are one sentence at most. Safety explanations appear once, in Settings → About, and as small chips ("Manual send") where relevant. All tests are updated to the new text.

### C3. Remembered list state

Every paged list keeps its filters, search, page and rows-per-page per screen for the session, through `useRememberedState`.

## 6. Phase D: Daily workflow screens

### D1. Overview becomes "Today"

- **Action cards in priority order:** automation that failed, drafts to approve, follow-ups due or overdue, shortlist ready, leads needing review. Each card says what to do and has one button that goes straight to the filtered screen.
- **Below:** a compact funnel (discovered → qualified → contacted → won) from the summary, the weekly run status, and a slim row of totals.
- **Empty day:** "You're up to date" with the next scheduled weekly run.

### D2. All leads

- **Saved-view chips:** All, Needs review, Ready to contact, Following up, Won, Do not contact. Each maps onto the existing server filters.
- **Filter chips** show what's active.
- **Clicking a row opens a lead preview drawer** with summary, contact details and next follow-up, plus "Open in pipeline" and "Ask AI".
- Paged with the server register built in R10.

### D3. Pipeline

- **Board view** beside the list view (the choice is remembered): one column per stage group, cards showing name, score, next action and value.
- **Moving a card** between columns uses the existing stage-change action and its rules: suppressed leads cannot leave Do Not Contact, and the reason prompt is kept.
- **Keyboard alternative:** a "Move to…" menu on each card.
- **Lead detail:** a summary strip (stage, score, next follow-up, value) above the tabs. "Lead details" opens by default, with privacy and audit collapsed.

### D4. Email drafts review queue

- **Layout:** queue on the left, preview on the right, and a progress line ("3 of 12 reviewed").
- **Keyboard shortcuts** (A approve, E edit, J/K next and previous, ? help) only while the queue has focus, never while typing in a field. Every action still uses the existing approval rules and confirmations.

### D5. Campaigns

- **Cards grouped** into collapsible Active, Paused and Archived sections, each showing status, last run and this week's leads.
- **Editing** happens in a wide drawer instead of inside the list.
- **New campaign** becomes a stepped form (Basics → Audience → Discovery → Weekly outreach → Review) over the same fields and validation, with "Plan with AI" as an alternative start.

### D6. Shortlist

Ranked cards with a short reason for the score ("Strong product fit · Instagram active · Local") and accept or skip on each card, with an undo toast where the existing action can be reversed.

### D7. Catalogue and Settings

- **Catalogue:** a grid or table toggle, grouped by product group in collapsible sections, with a completeness badge where sales knowledge is missing.
- **Settings:** a left sub-navigation (General, AI and models, Connections, Outreach, Data and privacy, About). Each connection gets a status card: connected, needs attention, or not set up.

## 7. Phase E: Preferences

### E1. Density

A Comfortable or Compact choice in Settings → General, applied through `data-density` and remembered.

### E2. Light theme

Light or dark, following the system setting by default and switchable in Settings. The light palette is built from the same brand colours, with contrast checked to WCAG AA for text and controls.

## 8. Order and sizes

| Order | Item | Size |
|---|---|---|
| 1 | A1 tokens | S |
| 2 | A2 shared components | M |
| 3 | A3 motion | S |
| 4 | B1 header and status | S |
| 5 | B2 sidebar | M |
| 6 | B3 floating AI assistant | M |
| 7 | C1 + C2 page anatomy and wording | L |
| 8 | C3 remembered list state | S |
| 9 | D1 Today overview | M |
| 10 | D2 All leads | M |
| 11 | D3 Pipeline board | L |
| 12 | D4 Email drafts queue | M |
| 13 | D5 Campaigns | L |
| 14 | D6 Shortlist | S |
| 15 | D7 Catalogue and Settings | M |
| 16 | B4 global search | M |
| 17 | E1 density, E2 light theme | M |

Sizes: **S** is up to half a day, **M** is one to two days, **L** is three to five days.

Global search comes after the screens are settled, so it can link to their final filtered views.

## 9. Risks

| Risk | Mitigation |
|---|---|
| Wording changes break many tests | Update the text, not the intent, of each assertion; keep accessible names stable where a label is only shortened |
| A drag-and-drop board bypasses a rule | Moving a card calls the same stage-change action with the same confirmations; the "Move to…" menu offers the same path without dragging |
| Motion feels slow | Durations are 120–300 ms, nothing animates while typing, and reduced motion turns it off |
| Keyboard shortcuts fire while typing | Shortcuts are only active when focus is on the queue, never in inputs, text areas or selects |
| Light theme contrast | Checked against WCAG AA before release; dark stays the default if the system has no preference |

## 10. Status

Delivered on branch `ux/redesign`, one commit per item, in the order of section 8; each is recorded in `DELIVERY_LOG.md`. Phase gates (`npm run quality`) passed after Phase B and Phase D, and at the end.

Deliberately left for later, each noted in the delivery log with its reason:

- Shortlist undo: the backend has no action that reopens a decided entry.
- Campaign cards' "last run" and "this week's leads": the screen does not load per-campaign figures yet.
- Catalogue groups by the knowledge pack's eight product groups: not exposed on the product list yet; grouping uses the Shopify category instead.
- Stage names in sentence case ("Ready to contact" instead of "Ready To Contact") across every screen.
- Pipeline: folding Privacy into a collapsed section of the lead.
- A "Weekly outreach" step in New campaign: the create form has never had those fields; they stay in Edit.

