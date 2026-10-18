# Etch 'N' Shine Lead Intelligence App
## UX Audit and Navigation Redesign Proposal

Act as a Senior Product Designer, UX Architect and B2B SaaS usability specialist.

You are reviewing an existing local lead-generation and lead-management web application for Etch 'N' Shine.

The application is functional and operational. All existing features, workflows, calculations, integrations and business rules are working correctly.

Your task is to review the supplied screenshots and propose a clearer, more efficient and more user-friendly interface architecture.

Do not implement any changes during this phase.

---

## 1. Primary Objective

Improve the application's:

- Ease of navigation
- Information hierarchy
- Screen readability
- Workflow clarity
- Interaction efficiency
- Data density
- Discoverability of actions
- Consistency between screens
- Ability to understand what requires attention
- Ability to move quickly from lead discovery to lead action

The redesign should reduce cognitive load and make the application feel like a polished operational CRM and lead-intelligence workspace.

---

## 2. Non-Negotiable Constraints

### Preserve all functionality

Do not:

- Remove any existing feature
- Add unrelated features
- Change application behaviour
- Change calculations
- Change scoring logic
- Change campaign logic
- Change shortlist logic
- Change lead stages
- Change approval rules
- Change discovery-provider behaviour
- Change integrations
- Change database structure unless strictly required for UI state
- Change API contracts
- Change business rules
- Change outbound-message controls
- Change operator-controlled safeguards

Every current capability must remain available.

### Preserve branding

The current branding and visual language are approved.

Do not change:

- Colour palette
- Dark navy interface
- Gold accent colour
- Logo
- Typography direction
- Brand identity
- General premium appearance
- Icon style unless an icon is inconsistent or unclear
- Existing status colour meanings

You may refine:

- Spacing
- Layout
- Alignment
- Component proportions
- Card structure
- Table density
- Information grouping
- Placement of controls
- Responsive behaviour
- Navigation organisation
- Use of drawers, panels, tabs or sticky elements
- Visual hierarchy within the existing colour system

### No redesign for its own sake

Every proposed change must solve a specific usability problem.

Avoid decorative changes that do not improve usability.

---

## 3. Application Context

The application supports a controlled lead-generation workflow:

1. Define campaigns
2. Discover leads through supported providers
3. Enrich and score leads
4. Review discovered leads
5. Generate a weekly shortlist
6. Approve, defer, dismiss or replace recommendations
7. Manage selected leads
8. Record contact details and classifications
9. Progress leads through a manual pipeline
10. Track follow-ups and outcomes

The application is deliberately operator controlled.

AI and outbound messaging may be unavailable or disabled. The interface must make this operating model clear without repeatedly consuming excessive screen space.

---

## 4. Screens to Review

Review all supplied screenshots, including:

- Overview dashboard
- Campaign register
- Campaign creation form
- Campaign automation and run history
- All leads register
- Weekly shortlist
- Pipeline workspace
- Global navigation
- Header and footer status areas

Assess both each individual screen and the end-to-end journey between them.

---

## 5. Initial Areas Requiring Particular Attention

Validate these observations against the screenshots rather than assuming they are correct.

### 5.1 Excessive vertical space

Several screens use large cards, headers and explanatory blocks, resulting in:

- Low information density
- Excessive scrolling
- Important content appearing below the fold
- Actions being separated from the data they affect

Identify where cards can be compressed without making the interface cramped.

### 5.2 Repeated page framing

Many pages repeat:

- Large section labels
- Page titles
- Explanatory text
- Card-level titles
- Nested section headings

Review whether these layers create unnecessary repetition.

Propose a consistent hierarchy such as:

1. Page title and primary action
2. Optional short context line
3. Filters or workflow navigation
4. Main workspace

### 5.3 Campaign navigation

The Campaign area currently contains multiple top-level tabs:

- Campaigns
- Create campaign
- Run automation
- Social leads

Review whether these should remain equal tabs or whether some should become:

- Primary actions
- Secondary views
- Contextual actions
- A campaign detail workflow
- A side panel or drawer

Creating a campaign may be better represented as an action rather than a permanent navigation tab. Assess this objectively.

### 5.4 Campaign register density

Campaign records consume considerable height despite containing a limited amount of information.

Explore:

- A compact campaign summary row
- Expandable campaign details
- Better action prioritisation
- One primary action with secondary actions in an overflow menu
- Clear separation between campaign configuration and campaign execution
- Stronger presentation of last-run status and results

Do not hide critical actions unnecessarily.

### 5.5 Campaign creation form length

The campaign creation form is long and extends below the viewport.

Assess:

- Logical grouping into sections
- Progressive disclosure
- A step-based form versus a structured single-page form
- Sticky summary or sticky action bar
- Better use of two-column layouts
- Clear separation between required and optional inputs
- Inline validation and help text
- Better placement of provider toggles
- Persistent save/create action

Do not create unnecessary steps for a form that can remain simple.

### 5.6 Automation screen

The automation screen combines:

- Provider controls
- Campaign execution
- Run history
- Metrics
- Warnings

Review how to improve separation between:

- Starting an automation run
- Viewing current provider readiness
- Reviewing previous runs
- Investigating warnings

Warnings should not dominate the page when they are repetitive. Consider expandable warning groups, summaries and drill-down behaviour.

### 5.7 All Leads register

The lead register contains useful data but could improve:

- Scanability
- Column prioritisation
- Search and filter ergonomics
- Differentiation between stage and contact classification
- Row-level action clarity
- Handling of long names, addresses and contact details
- Responsive behaviour
- Visibility of the most commercially relevant information

Assess whether:

- Some secondary information should move into a row expansion
- Columns should be reordered
- Search and filters should remain sticky
- Saved views or quick filters can be represented using existing filters without adding new functionality
- The Manage action should be more visually direct
- Table density can be user-selectable only if this can be done without adding unnecessary scope

Do not remove information currently available.

### 5.8 Weekly shortlist

The shortlist is a high-value operational screen.

Review:

- Whether each recommendation card is too large
- Whether lead comparison is sufficiently easy
- Whether approval decisions can be made quickly
- Whether score, product fit, contactability and reason for recommendation are prominent enough
- Whether Approve, Defer, Dismiss and Replace have the correct visual priority
- Whether approved or deferred states are immediately visible
- Whether a compact ranking table or hybrid card/table layout would improve the workflow

The operator must retain full control over each recommendation.

### 5.9 Pipeline workspace

The pipeline uses a left-hand lead list and a detailed right-hand workspace.

Assess:

- Width allocation
- Whether the left panel is too narrow
- Whether lead names are truncated excessively
- Whether pagination is effective
- Whether tabs are consistently visible
- Whether the selected lead summary should remain sticky
- Whether Save actions remain visible after scrolling
- Whether read-only fields and editable fields are distinguishable
- Whether the large number of fields can be grouped more clearly
- Whether navigation between leads preserves the selected sub-tab

Do not change the underlying pipeline workflow.

### 5.10 Status communication

The application displays status information in multiple areas:

- API connected
- Controlled mode
- Messaging disabled
- Local database
- Operator-controlled mode

Review whether these can be consolidated.

The operator must still be able to determine system state quickly, but repeated persistent messages should not consume unnecessary space.

### 5.11 Responsiveness

The screenshots show wide desktop views.

Define behaviour for:

- 1920px and larger
- Standard laptop widths around 1366px
- Narrow laptop/tablet landscape widths
- Minimum supported width

This is primarily a desktop operational application. Do not force a consumer-mobile design onto it.

---

## 6. Required UX Analysis

For every screen, analyse:

### Purpose

- What is the primary job of the screen?
- What decision or action should the operator complete?

### Current friction

Identify:

- Excessive scrolling
- Weak hierarchy
- Redundant information
- Ambiguous actions
- Competing calls to action
- Inconsistent component patterns
- Poor use of available width
- Long lines of text
- Hidden or below-the-fold actions
- Difficult comparison
- Dense or sparse areas
- Unclear state transitions

### Proposed change

For each recommendation, document:

- Current issue
- Proposed adjustment
- User benefit
- Functional impact
- Technical risk
- Priority

Use the priorities:

- P0 — Critical usability problem
- P1 — High-value improvement
- P2 — Useful refinement
- P3 — Optional polish

---

## 7. Navigation Architecture Review

Review the global navigation labels and order:

- Overview
- Campaigns
- All leads
- Catalogue
- Templates
- Weekly shortlist
- Pipeline
- Settings

Determine whether the current order reflects the real operating workflow.

Consider a clearer grouping such as:

### Lead acquisition
- Overview
- Campaigns
- All leads

### Lead operations
- Weekly shortlist
- Pipeline

### Configuration
- Catalogue
- Templates
- Settings

This is only a hypothesis. Recommend the best structure based on the screenshots.

Evaluate:

- Whether labels should change
- Whether sections should be grouped
- Whether counts remain visible
- Whether the sidebar can collapse
- Whether active-page treatment is sufficiently clear
- Whether navigation order should follow frequency of use or workflow order

Do not remove access to any page.

---

## 8. Interaction Design Review

Propose consistent rules for:

- Primary buttons
- Secondary buttons
- Destructive actions
- Status badges
- Empty states
- Search fields
- Filter bars
- Data tables
- Pagination
- Form fields
- Toggles and checkboxes
- Tabs
- Accordions
- Drawers
- Modal windows
- Save confirmation
- Loading states
- Error states
- Success states
- Disabled controls
- Long-running automation states
- Warning presentation
- Confirmation requirements

Avoid excessive modal use.

Prefer direct manipulation, inline feedback and contextual actions where suitable.

---

## 9. Preserve User Context

The redesign should minimise context loss.

Propose how the application should preserve:

- Selected campaign
- Selected lead
- Search terms
- Applied filters
- Pagination position
- Active pipeline tab
- Scroll position where appropriate
- Form drafts
- Shortlist review state

Do not propose backend persistence unless it is necessary. Browser or client-side state may be sufficient.

---

## 10. Accessibility Review

Within the approved visual identity, assess:

- Text contrast
- Small secondary text
- Focus indicators
- Keyboard navigation
- Tab order
- Click-target size
- Form labelling
- Error association
- Status communication beyond colour
- Icon labels and tooltips
- Screen-reader naming
- Table semantics

Do not change the colour palette unless an existing combination fails accessibility. Where contrast is weak, adjust tone or treatment within the existing palette.

---

## 11. Required Deliverables

Produce the following.

### A. Executive assessment

Summarise:

- What is currently working well
- The five most important usability problems
- The recommended redesign direction
- Expected operational improvement

### B. Screen-by-screen audit

For each supplied screen:

- Current strengths
- Current friction
- Proposed layout
- Proposed interaction changes
- Priority
- Risks

### C. Proposed information architecture

Provide:

- Revised global navigation
- Page relationships
- Recommended campaign workflow
- Recommended lead-management workflow
- Breadcrumb requirements, if any
- Expected user journey from campaign creation to closed opportunity

### D. Proposed wireframe descriptions

Provide low-fidelity text wireframes for:

- Overview
- Campaign register
- Campaign creation
- Automation centre
- All leads
- Weekly shortlist
- Pipeline

Use structured blocks such as:

[Page header]
[Primary action]
[Summary strip]
[Filter toolbar]
[Main table]
[Context drawer]

Do not create visual mock-ups unless specifically requested.

### E. Component standardisation plan

Define reusable component patterns for:

- Page header
- Summary metric
- Section card
- Data table
- Filter toolbar
- Status badge
- Action menu
- Empty state
- Warning summary
- Form section
- Sticky action bar
- Master-detail workspace

### F. Change matrix

Create a matrix containing:

| Screen | Current issue | Proposed change | Priority | Functional change? | Development complexity | Regression risk |

The “Functional change?” value should normally be “No”.

### G. Acceptance criteria

Provide measurable UX acceptance criteria, including:

- Maximum expected scroll depth
- Visibility of primary actions
- Number of clicks for core workflows
- Preservation of selected context
- Responsive behaviour
- Keyboard accessibility
- No loss of current functionality

### H. Implementation sequence

Recommend phased delivery:

1. Shared layout and component standardisation
2. Navigation improvements
3. High-traffic operational screens
4. Campaign screens
5. Secondary refinements
6. Accessibility and regression validation

Include dependencies and rollback considerations.

---

## 12. Core Workflow Benchmarks

The redesign should aim for:

### Create a campaign

- Reach campaign creation in no more than two deliberate actions
- Understand required fields without reading long instructions
- Create a valid campaign without losing entered data
- Keep the Create action visible at the appropriate point

### Run discovery or scoring

- Clearly understand which provider will run
- Understand provider readiness before execution
- See immediate progress and completion state
- Access warnings without allowing them to overwhelm the main result

### Find and manage a lead

- Search or filter from the lead register quickly
- Open a lead in one clear action
- Return to the same table position and filters
- Understand current stage and review requirement immediately

### Review weekly shortlist

- Compare recommended leads efficiently
- Understand recommendation rationale
- Approve, defer, dismiss or replace with minimal friction
- See the outcome of each decision immediately

### Manage pipeline lead

- Move between lead list and detail workspace without losing context
- Access each detail category predictably
- Save edits with clear success feedback
- Keep selected lead context visible

---

## 13. Output Rules

- Be specific rather than generic.
- Base findings on the supplied screenshots.
- Do not recommend changing the product's colour palette or identity.
- Do not propose new business functionality.
- Distinguish layout changes from functional changes.
- Flag any recommendation that may require data-model or API changes.
- Prefer low-risk UI restructuring.
- Do not write implementation code.
- Do not start implementation.
- Produce an approval-ready UX proposal that can be reviewed before development begins.