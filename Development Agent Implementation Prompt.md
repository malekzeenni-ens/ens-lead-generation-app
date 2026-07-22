# Etch 'N' Shine Lead Intelligence App
## Approved UX Redesign Implementation

Act as a Senior Front-End Engineer, UX-focused Full-Stack Engineer and Software Regression Specialist.

You must implement the approved UX redesign proposal for the existing Etch 'N' Shine Lead Intelligence application.

The application is currently functional. This is a user-interface restructuring and usability improvement exercise, not a feature redevelopment.

---

## 1. Mandatory First Step: Repository and Application Review

Before changing any code, inspect the complete existing application.

Review:

- Front-end framework and version
- Routing structure
- Page composition
- Shared layouts
- Component library
- CSS architecture
- Design tokens
- State-management approach
- API client implementation
- Backend routes
- Database models
- Campaign logic
- Lead-discovery logic
- Scoring logic
- Shortlist generation
- Pipeline state handling
- Form validation
- Integration status handling
- Error handling
- Loading states
- Existing automated tests
- Existing linting and type-checking
- Responsive behaviour
- Accessibility implementation

Produce a concise pre-implementation assessment before editing files.

The assessment must identify:

- Files and components expected to change
- Components that can be reused
- Existing risks
- Existing technical debt relevant to the redesign
- Any approved recommendation that may affect application behaviour
- Proposed implementation order

Do not begin broad code changes until this assessment is complete.

---

## 2. Source of Truth

Use the following in priority order:

1. Existing working application behaviour
2. Approved UX redesign proposal
3. Existing business rules
4. Existing tests
5. Existing visual identity and design tokens
6. Supplied reference screenshots

Where the approved proposal appears to conflict with working functionality, preserve functionality and report the conflict.

Do not guess.

---

## 3. Absolute Constraints

### Do not change functionality

Do not alter:

- Campaign creation behaviour
- Campaign editing behaviour
- Campaign duplication
- Campaign pause/resume behaviour
- Discovery-provider logic
- Google Places integration
- Instagram enrichment behaviour
- Lead deduplication
- Lead scoring
- Qualification rules
- Shortlist scoring
- Weekly capacity rules
- Approval behaviour
- Deferral behaviour
- Dismissal behaviour
- Replacement behaviour
- Pipeline stages
- Lead retention logic
- Contact classification
- Product matching
- Database persistence
- API response contracts
- Authentication or local-access behaviour
- Operator-controlled mode
- Messaging restrictions
- Any existing safeguard

### Do not change branding

Preserve:

- Logo
- Current navy colour system
- Current gold accent system
- Current visual identity
- Current premium styling direction
- Approved status colours
- Existing typography unless the approved proposal explicitly standardises sizes or weights

Do not introduce:

- A new colour palette
- Gradients unless already present
- Bright SaaS colours
- A generic white dashboard theme
- Unapproved fonts
- Unapproved branding changes

### Do not add scope

Do not add:

- New integrations
- New lead sources
- New AI workflows
- Automated messaging
- New scoring dimensions
- New campaign types
- New analytics
- New pipeline stages
- New database entities
- New account management

Only implement the approved presentation and interaction changes.

---

## 4. Implementation Strategy

Use incremental, low-risk refactoring.

Preferred sequence:

1. Establish regression baseline
2. Extract or standardise shared layout components
3. Implement navigation changes
4. Implement shared page-header and toolbar patterns
5. Improve Overview
6. Improve All Leads
7. Improve Weekly Shortlist
8. Improve Pipeline
9. Improve Campaign Register
10. Improve Campaign Creation
11. Improve Automation and Run History
12. Consolidate status presentation
13. Implement responsive rules
14. Complete accessibility improvements
15. Run full regression validation

Do not rewrite the application unless technically unavoidable.

Prefer adapting existing components over replacing the architecture.

---

## 5. Shared Layout Requirements

Implement a consistent application shell.

### Global header

Preserve:

- Etch 'N' Shine branding
- Workspace identity
- Refresh control
- API/service connection state

Improve only according to the approved proposal.

Ensure:

- Controls align consistently
- System status remains visible
- Header height is not unnecessarily large
- Long status messages do not dominate the workspace
- Status controls remain keyboard accessible

### Sidebar

Implement the approved navigation grouping and ordering.

Requirements:

- Preserve access to every existing route
- Preserve navigation counts
- Preserve active-route highlighting
- Support a collapsed state only when included in the approved proposal
- Provide clear accessible names for icons
- Maintain usability at narrower desktop widths
- Do not allow navigation text to become unreadable

### Main workspace

Standardise:

- Maximum content width, where appropriate
- Horizontal padding
- Page title position
- Primary-action position
- Section spacing
- Card padding
- Toolbar placement
- Sticky behaviour
- Responsive breakpoints

Avoid excessive empty space on wide screens.

---

## 6. Reusable Components

Create or refine reusable components where appropriate.

Candidate components include:

- `AppShell`
- `GlobalHeader`
- `SidebarNavigation`
- `PageHeader`
- `PageToolbar`
- `MetricCard`
- `StatusBadge`
- `FilterBar`
- `SearchInput`
- `DataTable`
- `Pagination`
- `SectionCard`
- `EmptyState`
- `WarningSummary`
- `ActionMenu`
- `StickyActionBar`
- `FormSection`
- `ProviderStatus`
- `MasterDetailLayout`
- `LeadSummaryHeader`
- `RunHistoryItem`

Use names consistent with the existing codebase.

Do not create abstractions where only one use case exists.

Do not force dissimilar screens into an inflexible generic component.

---

## 7. Overview Screen

Implement the approved Overview redesign.

Requirements:

- Preserve every displayed metric
- Preserve metric values and data sources
- Preserve weekly shortlist content
- Preserve open follow-up content
- Preserve pipeline summary
- Preserve links and actions
- Improve the hierarchy between:
  - Current status
  - Items requiring attention
  - Operational queue
  - Pipeline state
- Reduce unnecessary card height
- Ensure important actions appear within the initial desktop viewport where practical
- Make empty states compact but understandable
- Avoid presenting a large empty panel when a smaller empty state communicates the same information

No metric logic may change.

---

## 8. Campaign Register

Implement the approved campaign register layout.

Requirements:

- Preserve campaign search
- Preserve campaign status
- Preserve all campaign metadata
- Preserve:
  - Run Google Places
  - Refresh Instagram profiles
  - Refresh scoring only
  - Edit
  - Pause/resume
  - Duplicate
- Preserve the exact behaviour of every action
- Improve campaign scanning and comparison
- Reduce repeated vertical padding
- Clearly distinguish:
  - Campaign identity
  - Configuration
  - Current status
  - Last-run information
  - Execution actions
  - Management actions

Where approved, move lower-priority actions into a clearly labelled overflow menu.

Do not hide execution actions behind an ambiguous icon-only menu.

---

## 9. Campaign Creation

Implement the approved campaign form structure.

Requirements:

- Preserve every existing field
- Preserve default values
- Preserve validation rules
- Preserve provider controls
- Preserve product-category selection
- Preserve optional versus mandatory behaviour
- Preserve campaign creation payload
- Preserve error handling

Improve:

- Grouping
- Field order
- Use of available width
- Label clarity
- Help-text placement
- Visibility of the submission action
- Error summaries
- Focus movement after validation failure

If implementing a sticky action bar:

- It must not cover content
- It must reflect form validity correctly
- It must not submit duplicate requests
- It must work at all supported viewport sizes

Do not convert the form into a stepper unless explicitly approved.

---

## 10. Automation and Run History

Implement a clearer distinction between:

- Provider readiness
- Run controls
- Current execution state
- Run results
- Previous run history
- Warnings

Requirements:

- Preserve each automation action
- Preserve provider-specific execution
- Preserve scoring-only execution
- Preserve campaign-level statistics
- Preserve timestamps
- Preserve completion states
- Preserve warnings verbatim unless presentation-only formatting is approved
- Preserve historical records

Where warnings are grouped:

- Show the warning count
- Show a concise summary
- Allow access to every individual warning
- Do not discard warning text
- Do not suppress errors
- Ensure expanded state is accessible

Long-running actions must communicate:

- Starting
- In progress
- Completed
- Completed with warnings
- Failed

Do not fabricate progress percentages if they are not available from the current application.

---

## 11. All Leads Register

Implement the approved lead-register improvements.

Requirements:

- Preserve every existing lead
- Preserve search behaviour
- Preserve all filters
- Preserve campaign filtering
- Preserve lead-source filtering
- Preserve stage filtering
- Preserve contact-state filtering
- Preserve pagination
- Preserve Manage behaviour
- Preserve contact and location information
- Preserve source badges
- Preserve stage and review status

Improve:

- Column widths
- Alignment
- Long-content truncation
- Accessible tooltips or expansion for truncated content
- Table scanability
- Sticky filter behaviour where approved
- Responsive handling
- Distinction between pipeline stage and contact classification
- Return-state preservation after opening a lead

Do not reduce the available data. Secondary information may move into an expandable row only when approved.

Ensure table headers remain aligned with cells at all breakpoints.

---

## 12. Weekly Shortlist

Implement the approved shortlist layout.

Requirements:

- Preserve ranking order
- Preserve campaign selection
- Preserve week selection
- Preserve capacity
- Preserve minimum score
- Preserve shortlist generation
- Preserve lead score
- Preserve recommendation state
- Preserve Approve
- Preserve Defer
- Preserve Dismiss
- Preserve Replace
- Preserve Open Lead
- Preserve existing decision persistence

Improve:

- Comparison between candidates
- Visibility of score and rationale
- Action hierarchy
- Decision-state feedback
- Use of horizontal space
- Density of recommendation items

After an action:

- Update the visible state immediately
- Prevent accidental repeated submissions
- Show clear success or error feedback
- Preserve the user's position in the shortlist
- Do not reorder leads unless current behaviour already does so

Destructive or irreversible actions must retain existing confirmation behaviour.

---

## 13. Pipeline Workspace

Implement the approved master-detail layout.

Requirements:

- Preserve the lead list
- Preserve search
- Preserve pagination
- Preserve lead selection
- Preserve all detail tabs
- Preserve every editable field
- Preserve Save behaviour
- Preserve lead stage
- Preserve activity history
- Preserve follow-up functionality
- Preserve privacy controls
- Preserve score and product views
- Preserve opportunity details

Improve:

- Width balance between lead list and detail panel
- Lead-name readability
- Selected-row visibility
- Tab visibility
- Sticky lead summary
- Save-action visibility
- Form grouping
- Read-only versus editable field distinction
- Responsive behaviour

Preserve the selected lead and selected detail tab during ordinary navigation and save operations.

Do not reset the form unless the current operation explicitly requires it.

Warn about unsaved changes before switching leads only if such a safeguard already exists or was explicitly approved.

---

## 14. Status and System-State Presentation

Implement the approved consolidation of:

- API connected state
- Local service state
- Controlled mode
- Messaging-disabled state
- Local database state
- Operator-controlled mode

Requirements:

- Do not remove any status information
- Do not imply messaging is enabled when it is disabled
- Do not hide degraded or disconnected states
- Preserve existing status logic
- Keep critical failure states visible
- Allow secondary detail to appear in a tooltip, popover or status panel if approved

Status presentation must not rely on colour alone.

---

## 15. Responsive Requirements

The application remains desktop first.

Validate at minimum:

- 1920 × 1080
- 1600 × 900
- 1440 × 900
- 1366 × 768
- Narrow desktop or landscape tablet width defined by the existing application

Requirements:

- No horizontal page overflow unless a data table explicitly supports controlled horizontal scrolling
- No hidden primary actions
- No overlapping sticky elements
- No clipped dropdowns
- No inaccessible menus
- No unreadable table columns
- No form controls below unusable widths
- Sidebar and main content must coexist predictably
- Master-detail panels must degrade gracefully

Document the minimum supported viewport width.

---

## 16. Accessibility Requirements

Implement:

- Visible keyboard focus
- Logical tab order
- Correct semantic heading hierarchy
- Accessible names for icon-only buttons
- Associated labels for form fields
- Error messages linked to their fields
- Status updates through appropriate live regions where necessary
- Button states communicated beyond colour
- Sufficient click-target dimensions
- Semantic table markup
- Keyboard-operable menus, accordions and tabs
- Escape-key handling for drawers or dialogs
- Focus restoration after overlays close

Do not materially change branding to meet accessibility. Refine contrast and component treatment within the current design system.

---

## 17. State Preservation

Preserve user context where technically appropriate:

- Current route
- Active campaign tab or campaign context
- Search terms
- Selected filters
- Current page
- Selected lead
- Active pipeline tab
- Expanded warning groups
- Form contents before submission
- Shortlist review position

Use the application's existing state strategy where possible.

Avoid introducing a new global state library solely for the redesign.

---

## 18. Regression Protection

Before implementation, establish a regression checklist for every screen.

At minimum test:

### Campaigns

- Create
- Edit
- Pause
- Resume
- Duplicate
- Search
- Google Places execution
- Instagram refresh
- Scoring refresh
- Automation history
- Warning display

### Leads

- Search
- Filter
- Pagination
- Open lead
- Contact-state display
- Stage display
- Source display

### Weekly shortlist

- Generate
- Approve
- Defer
- Dismiss
- Replace
- Open lead
- Campaign capacity
- Week selection

### Pipeline

- Search
- Select lead
- Navigate tabs
- Edit fields
- Save
- Paginate lead list
- Preserve selection
- Follow-up actions
- Privacy view

### Global

- Navigation
- Refresh
- API-state display
- Empty states
- Loading states
- Error states
- Keyboard navigation
- Responsive layouts

All pre-existing automated tests must continue to pass.

Add focused UI tests for newly restructured components.

Do not rewrite passing business-logic tests merely to accommodate UI changes.

---

## 19. Code Quality

Requirements:

- Follow the existing project conventions
- Preserve type safety
- Avoid duplicated layout logic
- Avoid oversized components
- Separate presentation from data logic where practical
- Keep API calls unchanged unless a documented defect requires correction
- Avoid magic spacing values when design tokens exist
- Reuse current theme variables
- Remove obsolete UI code only after confirming it is no longer referenced
- Do not leave commented-out legacy implementations
- Do not introduce console errors or warnings
- Do not weaken linting or compiler settings

---

## 20. Delivery Method

Implement in small, reviewable stages.

For each stage provide:

- Files changed
- What was changed
- Why it was changed
- Confirmation that behaviour was preserved
- Tests run
- Screens manually verified
- Known limitations
- Screenshots where the environment supports them

Do not combine unrelated changes into one large refactor.

---

## 21. Definition of Done

The implementation is complete only when:

- Every current feature remains available
- Every current workflow behaves as before
- Branding and colour identity remain intact
- Approved layouts are implemented
- Navigation is consistent
- Primary actions are easier to find
- Excessive vertical spacing is reduced
- Data-heavy screens are easier to scan
- Forms are easier to complete
- Warnings remain fully available
- System status remains accurate
- Responsive layouts pass the defined viewport checks
- Keyboard navigation works
- Existing tests pass
- New UI tests pass
- No console errors are present
- No API or database regression is introduced
- A final change report is provided

---

## 22. Final Report

At completion, provide:

### Implementation summary

- Screens changed
- Shared components created or modified
- Navigation changes
- Layout changes
- Accessibility improvements
- Responsive improvements

### Functional preservation statement

List each major workflow and confirm how it was validated.

### Test evidence

Include:

- Automated tests
- Type checking
- Linting
- Build result
- Manual test scenarios
- Viewports tested

### Deviations

Document any approved proposal item that was:

- Modified
- Deferred
- Rejected
- Technically constrained

Explain the reason.

### Remaining recommendations

Only include recommendations directly related to implementation quality or usability. Do not introduce new product scope.

---

## Final Instruction

Do not interpret “redesign” as permission to rebuild the application.

Retain the working system and improve its interface through controlled, testable and reversible UI changes.