# Etch ’N’ Shine Universal Application Design System

## Purpose

This document defines a reusable design system and implementation standard for all Etch ’N’ Shine applications.

It is intended to be given directly to a coding agent whenever building or redesigning:

- Local desktop applications
- Web applications
- Internal business tools
- Admin dashboards
- Product-management utilities
- Image-processing tools
- Pricing tools
- Shopify or Etsy support tools
- Production and operations software

The objective is consistency.

Any application built using this system should feel like part of the same Etch ’N’ Shine software family, even when the application serves a different purpose or uses a different technical framework.

The system should produce interfaces that are:

- Professional
- Premium
- Modern
- Calm
- Efficient
- Clear
- Desktop-first where appropriate
- Branded without becoming decorative
- Suitable for frequent production use

## 1. Core Design Principle

The visual identity must be based on a dark navy application shell, structured blue-grey surfaces, off-white text, and restrained champagne-gold accents.

The interface must not be created as a simple colour reskin.

Consistency must come from shared layout rules, spacing, typography, interaction patterns, iconography, control styling, feedback states, navigation structure, visual hierarchy, and behaviour standards.

Every design decision must support usability first and brand recognition second.

## 2. Design Personality

All Etch ’N’ Shine applications should feel:

- Premium but practical
- Elegant but not ornamental
- Modern but not trendy
- Dense enough for professional use
- Calm rather than visually noisy
- Clear rather than overly minimal
- Branded but not promotional
- Serious enough for business operations
- Accessible and predictable

Avoid interfaces that resemble gaming dashboards, neon or cyberpunk themes, generic Bootstrap admin panels, highly rounded mobile apps, marketing landing pages, glassmorphism-heavy designs, overly animated product demos, crowded enterprise software, Adobe Photoshop clones, developer-only utilities, or unstyled native controls.

## 3. Brand Colour System

Use semantic colour tokens throughout the application.

Do not hardcode raw colours in individual components unless technically unavoidable.

### 3.1 Core Brand Colours

#### Deep Navy

`#07131E`

Use for main application background, title bar, sidebar, top navigation, large structural surfaces, dark canvas surroundings, and modal backdrops.

#### Slate Blue

`#4C647C`

Use for secondary surfaces, hover states, selected backgrounds, borders, secondary controls, muted panels, and navigation highlights.

#### Champagne Gold

`#DDBF93`

Use for primary actions, active states, focus indicators, selected icons, key values, slider handles, toggle-on states, important headings, and progress emphasis.

#### Warm Taupe

`#5E584A`

Use sparingly for supporting neutral states, warm secondary accents, non-critical status indicators, and optional tertiary surfaces.

#### Soft Olive Grey

`#7C7C6B`

Use sparingly for disabled states, muted utility elements, neutral indicators, and low-priority labels.

## 4. Semantic Colour Tokens

Use a central theme file or design-token object.

```css
:root {
  --ens-app-background: #07131E;

  --ens-surface-1: #0D1D2A;
  --ens-surface-2: #142838;
  --ens-surface-3: #1A3042;
  --ens-surface-hover: rgba(76, 100, 124, 0.24);
  --ens-surface-selected: rgba(76, 100, 124, 0.46);
  --ens-surface-disabled: rgba(124, 124, 107, 0.14);

  --ens-border-subtle: rgba(221, 191, 147, 0.12);
  --ens-border-default: rgba(221, 191, 147, 0.22);
  --ens-border-strong: rgba(221, 191, 147, 0.38);
  --ens-border-active: #DDBF93;

  --ens-text-primary: #F5F3EE;
  --ens-text-secondary: #BBC5CD;
  --ens-text-muted: #85939E;
  --ens-text-accent: #DDBF93;
  --ens-text-on-accent: #07131E;

  --ens-action-primary: #DDBF93;
  --ens-action-primary-hover: #E5C99E;
  --ens-action-primary-pressed: #C9AA78;
  --ens-action-secondary: #4C647C;

  --ens-success: #76A98C;
  --ens-warning: #D4A85C;
  --ens-error: #CF7777;
  --ens-info: #73A2C5;

  --ens-overlay: rgba(2, 9, 15, 0.72);
}
```

Derived values may be adjusted slightly for contrast, platform rendering, or framework limitations. Do not replace the core palette with unrelated blues or bright metallic golds.

## 5. Colour Usage Rules

### 5.1 Gold

Use gold for primary action buttons, active tabs, selected navigation items, active tool icons, focus rings, slider handles, toggle-on states, key status values, important section headings, and progress indicators.

Do not use gold for long paragraphs, every label, disabled controls, large background areas, error messages, decorative gradients across the full interface, or excessive borders.

Gold should remain an accent, not the dominant colour.

### 5.2 Navy

Navy should remain the dominant structural colour and create visual calm and consistency.

### 5.3 White and Grey

Normal body text should use off-white or muted blue-grey. Pure white should be used sparingly.

### 5.4 Status Colours

Use green for success, amber for warning, red for error, and blue for information. Do not use status colours decoratively.

## 6. Typography

Use one clean sans-serif interface family across the entire application.

Preferred order:

1. Segoe UI
2. Inter
3. Geist
4. IBM Plex Sans
5. System UI fallback

```css
font-family:
  "Segoe UI",
  Inter,
  Geist,
  "IBM Plex Sans",
  system-ui,
  -apple-system,
  BlinkMacSystemFont,
  sans-serif;
```

### 6.1 Type Scale

```text
Application title       16–18 px / semibold
Page title              22–28 px / semibold
Panel title             15–17 px / semibold
Section heading         12–14 px / semibold
Control label           12–13 px / medium
Body text               13–14 px / regular
Supporting text         11–12 px / regular
Button text             12–14 px / medium
Table text              12–13 px / regular
Status text             11–12 px / regular
```

Use sentence case, avoid decorative fonts, use semibold rather than bold for most headings, use gold only for selected headings or priority values, use off-white for standard titles, and use muted grey for supporting descriptions.

## 7. Spacing System

Use a consistent 4-pixel base grid.

```text
4 px
8 px
12 px
16 px
20 px
24 px
32 px
40 px
48 px
```

Use 4 px for icon and micro-label gaps, 8 px for closely related controls, 12 px for field label spacing, 16 px for standard component spacing, 24 px for section spacing, 32 px for major layout spacing, and 40–48 px for page-level separation.

Do not use arbitrary values unless required by the rendering framework.

## 8. Border Radius

```text
Small controls        6 px
Standard controls     8 px
Cards and panels      10 px
Dialogs               12 px
Pills and tags        Full pill only when semantically appropriate
```

Avoid excessive rounding, bubble-shaped navigation, large pill buttons for ordinary actions, and inconsistent radius values.

## 9. Borders and Shadows

Use subtle borders to define hierarchy.

```css
border: 1px solid var(--ens-border-subtle);
```

Use stronger borders only for active fields, selected panels, focused controls, and important dialogs.

Use minimal shadows for floating menus, dialogs, elevated panels, and tooltips.

```css
box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
```

Do not use shadows on every control.

## 10. Iconography

Use one icon library consistently across all applications.

Preferred order:

1. Lucide
2. Phosphor
3. Fluent UI System Icons
4. Material Symbols Rounded

Use outline icons, consistent stroke weight, 18–20 px toolbar icons, and 20–24 px sidebar or tool-rail icons. Pair icons with text for major actions. Use icon-only buttons only for universally understood actions. Every icon-only control requires a tooltip. Do not use emoji as production icons.

### 10.1 Common Icon Mapping

| Function | Recommended Icon |
|---|---|
| Open | Folder Open |
| Save | Save |
| Export | File Output |
| Settings | Sliders Horizontal |
| Delete | Trash |
| Edit | Pencil |
| Search | Search |
| Filter | Funnel |
| Refresh | Refresh CW |
| Undo | Rotate CCW |
| Redo | Rotate CW |
| Add | Plus |
| Remove | Minus |
| Start | Play |
| Stop | Square |
| Restart | Rotate CW |
| Success | Check Circle |
| Warning | Triangle Alert |
| Error | Circle X |
| Information | Info |
| Upload | Upload |
| Download | Download |
| Dashboard | Layout Dashboard |
| Image | Image |
| List | List |
| Grid | Grid |
| Expand | Chevron Down |
| Collapse | Chevron Up |

## 11. Universal Application Shell

For standard management applications:

```text
┌─────────────────────────────────────────────────────┐
│ Application Header                                  │
├──────────────┬──────────────────────────────────────┤
│ Sidebar      │ Main Content                         │
│              │                                      │
├──────────────┴──────────────────────────────────────┤
│ Optional Status Bar                                 │
└─────────────────────────────────────────────────────┘
```

For image, design, or production tools:

```text
┌─────────────────────────────────────────────────────┐
│ Header                                              │
├─────────────────────────────────────────────────────┤
│ Primary Toolbar                                     │
├────────┬─────────────────────────────┬──────────────┤
│ Tool   │ Main Canvas / Workspace     │ Properties   │
│ Rail   │                             │ Panel        │
├────────┴─────────────────────────────┴──────────────┤
│ Status Bar                                          │
└─────────────────────────────────────────────────────┘
```

For dashboards:

```text
┌─────────────────────────────────────────────────────┐
│ Header                                              │
├──────────────┬──────────────────────────────────────┤
│ Sidebar      │ Page Header                          │
│              ├──────────────────────────────────────┤
│              │ Filters / Actions                    │
│              ├──────────────────────────────────────┤
│              │ Main Data / Cards / Tables           │
└──────────────┴──────────────────────────────────────┘
```

## 12. Application Header

Every application should have a consistent header containing a small Etch ’N’ Shine logo, application name, current workspace, project, or page name, optional unsaved indicator, optional settings, optional help, window controls for local apps, and user/account area only where relevant.

Recommended height: `44–56 px`.

Do not make the header promotional. The logo should be small and secondary to the application name.

## 13. Navigation

### 13.1 Sidebar

Use for applications with multiple sections.

```text
220–260 px expanded
68–80 px collapsed
```

Sidebar items should include an icon, short label, selected state, hover state, optional badge, and tooltip when collapsed.

Selected item treatment:

- Slate-blue background
- Gold icon or left accent line
- Off-white or gold label
- Clear contrast

### 13.2 Tool Rail

Use for direct manipulation tools.

Recommended width: `68–88 px`.

Each tool should have an icon, short label or tooltip, selected state, and shortcut hint where useful.

### 13.3 Tabs

Use tabs for closely related views. Use gold text and a gold underline or border for the active tab. Avoid oversized pill backgrounds unless appropriate.

## 14. Buttons

### 14.1 Primary Button

Use for the most important action on a page or panel.

```css
background: var(--ens-action-primary);
color: var(--ens-text-on-accent);
border: 1px solid var(--ens-action-primary);
```

### 14.2 Secondary Button

Use a slate-blue or dark surface, off-white text, and subtle gold or blue-grey border.

### 14.3 Tertiary Button

Use a transparent background, off-white or muted text, and hover surface only.

### 14.4 Destructive Button

Use a red accent and clear label. Require confirmation where appropriate.

### 14.5 Button Rules

- Minimum height: 36 px
- Preferred primary height: 40–44 px
- Use icon plus text for major actions
- Avoid multiple primary buttons in the same section
- Avoid green buttons unless the action is semantically successful
- Avoid gold-filled buttons for every action

## 15. Form Controls

All form controls should share a consistent height, border, and focus state.

Recommended height: `36–40 px`.

### 15.1 Text Inputs

Use a dark surface, off-white input text, muted placeholder, subtle border, gold focus ring, and clear error state.

### 15.2 Dropdowns

Use when there are multiple options, the list may grow, or all options do not need to remain visible.

### 15.3 Segmented Controls

Use for 2–4 mutually exclusive, short options where immediate visibility is valuable.

### 15.4 Toggle Switches

Use for persistent binary states. Do not use toggles for immediate actions. Use a gold track or thumb for the on state.

### 15.5 Sliders

Every slider must include a label, current value, minimum and maximum, optional numeric input, and reset action where useful. Use a gold handle and restrained gold progress track.

## 16. Cards and Panels

Use cards only when content benefits from separation.

Standard card:

- Surface 1 or Surface 2
- 1 px subtle border
- 8–10 px radius
- 16–24 px internal padding
- Minimal shadow
- Clear heading
- Optional action area

Avoid excessive card nesting.

## 17. Tables

Use tables for structured operational data.

Table rules:

- Dark surface
- Sticky header where helpful
- Clear row hover
- Gold or blue-grey selected row state
- Muted dividers
- Right-align numeric data
- Left-align text data
- Consistent action column
- Compact but readable row height
- No zebra striping unless needed for dense datasets

Recommended row height: `40–48 px`.

## 18. Modals and Dialogs

Use dialogs for confirmation, destructive actions, critical settings, focused multi-step input, and errors requiring action.

Dialog structure:

- Clear title
- Concise description
- Main content
- Secondary action
- Primary action
- Close control
- Keyboard focus management

Use deep navy or elevated blue surface. Use gold only for the primary action and focus state.

## 19. Tooltips

Use tooltips for icon-only buttons, abbreviated labels, keyboard shortcuts, and technical controls.

Tooltips should be short, delayed slightly, high contrast, and predictably positioned. They must not replace essential instructions.

## 20. Feedback and Status

All applications must clearly communicate loading, success, warning, error, disabled, empty, and offline or disconnected states where relevant.

### 20.1 Loading

Use a spinner for short operations, progress bar for measurable operations, skeletons for data loading, and processing overlay for blocking operations. Do not use fake progress.

### 20.2 Toasts

Use toasts for save completed, export completed, background operation completed, and non-critical errors. Do not use toasts for errors requiring user action.

### 20.3 Empty States

Every empty state should include a clear title, one-line explanation, relevant primary action, and optional supporting icon.

## 21. Accessibility

Every application must include keyboard navigation, visible focus rings, accessible labels, sufficient contrast, logical tab order, tooltips, no colour-only meaning, clear disabled states, minimum click targets of approximately 36 × 36 px, and support for common zoom or scaling settings where feasible.

```css
outline: 2px solid var(--ens-border-active);
outline-offset: 2px;
```

## 22. Motion and Animation

Use motion only to support clarity.

Approved uses include panel open and close, tab transitions, hover transitions, toast appearance, progress indicators, and small state changes.

```text
120–180 ms for control transitions
180–240 ms for panel transitions
```

Avoid bouncing, large-scale movement, decorative looping animations, slow transitions, and excessive fades. Respect reduced-motion preferences in web applications.

## 23. Responsive Behaviour

### 23.1 Web Applications

Design for 1366 × 768, 1440 × 900, 1920 × 1080, 2560 × 1440, tablet where relevant, and mobile only when the workflow genuinely requires it.

Responsive priority:

1. Preserve primary actions
2. Preserve main workspace
3. Collapse secondary panels
4. Convert labels to icon-only with tooltips
5. Stack supporting content
6. Avoid horizontal scrolling

### 23.2 Local Desktop Applications

Design desktop-first. Allow collapsible panels, resizable sidebars, persistent layout preferences, compact controls, and a high-density workspace. Do not redesign desktop applications as oversized mobile screens.

## 24. Application-Specific Flexibility

The system must remain consistent without forcing every application into the exact same layout.

### Image or design tools

Use toolbar, tool rail, canvas, properties panel, and status bar.

### Dashboards

Use sidebar, page header, summary cards, filters, tables, and charts.

### Configuration tools

Use sidebar or tabs, grouped settings panels, save bar, and validation messages.

### Workflow tools

Use step navigation, main task area, context panel, and progress summary.

The visual language must remain consistent even when the layout differs.

## 25. Brand Logo Rules

The Etch ’N’ Shine logo may be used in the application header, login screen, About screen, splash screen, and restrained empty-state branding.

Do not stretch, recolour, shadow, repeat, watermark, or use the logo as a decorative background. Never insert it into customer exports.

## 26. Consistency Requirements

Every application must use the same core colour tokens, typography family, spacing scale, border-radius scale, icon family, button hierarchy, focus treatment, tooltip style, modal style, status colours, navigation treatment, primary action treatment, disabled-state treatment, and loading-state treatment.

Application-specific deviations must be documented.

## 27. Coding-Agent Implementation Rules

The coding agent must:

1. Inspect the existing application first.
2. Identify the current framework and component library.
3. Reuse existing logic.
4. Create a central theme or token file.
5. Build reusable components.
6. Avoid duplicated styling.
7. Avoid inline hardcoded colours.
8. Avoid changing business logic.
9. Avoid changing defaults.
10. Avoid replacing working functionality without approval.
11. Validate accessibility.
12. Test at required resolutions.
13. Preserve existing keyboard behaviour.
14. Preserve save and export behaviour.
15. Provide a visual regression summary.
16. Provide a list of files changed.
17. Document any design-system deviations.

## 28. Recommended Components

```text
AppShell
ApplicationHeader
Sidebar
SidebarItem
ToolRail
ToolButton
PageHeader
PrimaryToolbar
ToolbarGroup
Panel
Card
ActionButton
IconButton
TextInput
NumericInput
SelectField
SegmentedControl
ToggleSwitch
SliderField
Tabs
Badge
Table
Modal
ConfirmationDialog
Tooltip
Toast
EmptyState
StatusBar
ProcessingOverlay
```

Component names may differ by framework. Behaviour and visual rules should remain consistent.

## 29. Design Tokens Beyond Colour

```css
:root {
  --ens-space-1: 4px;
  --ens-space-2: 8px;
  --ens-space-3: 12px;
  --ens-space-4: 16px;
  --ens-space-5: 20px;
  --ens-space-6: 24px;
  --ens-space-8: 32px;
  --ens-space-10: 40px;
  --ens-space-12: 48px;

  --ens-radius-sm: 6px;
  --ens-radius-md: 8px;
  --ens-radius-lg: 10px;
  --ens-radius-xl: 12px;

  --ens-control-height-sm: 32px;
  --ens-control-height-md: 38px;
  --ens-control-height-lg: 44px;

  --ens-sidebar-expanded: 240px;
  --ens-sidebar-collapsed: 76px;
  --ens-tool-rail-width: 80px;
  --ens-properties-panel-width: 340px;

  --ens-transition-fast: 140ms;
  --ens-transition-standard: 200ms;
}
```

## 30. Design Review Checklist

### Brand

- Deep Navy is the dominant shell colour
- Champagne Gold is used selectively
- The approved logo is used correctly
- The approved font family is used
- One icon family is used

### Layout

- Clear hierarchy
- Consistent spacing
- No overcrowding
- Main task is visually dominant
- Secondary controls are grouped logically
- No clipped content

### Controls

- Primary action is obvious
- Secondary actions are visually quieter
- Toggle usage is correct
- Slider usage is correct
- Dropdown usage is correct
- Tooltips exist for icon-only actions
- Focus states are visible

### Accessibility

- Contrast is acceptable
- Keyboard navigation works
- Disabled states are clear
- Error messages are understandable
- Colour is not the only status indicator

### Behaviour

- Loading states are visible
- Success states are visible
- Errors are actionable
- Destructive actions require confirmation
- Existing functionality is preserved

### Consistency

- Tokens are used centrally
- No arbitrary colours
- No inconsistent radii
- No mixed icons
- No random spacing
- No one-off button styles

## 31. Approval Criteria

An application is compliant when:

- It is immediately recognisable as part of the Etch ’N’ Shine application family.
- The colour hierarchy matches this design system.
- The same button, input, navigation, and feedback patterns are used.
- The main user task is clear within three seconds.
- Primary actions are visible without searching.
- The interface feels professional and production-ready.
- It remains usable at 1366 × 768.
- It is accessible using keyboard and mouse.
- It avoids excessive decoration.
- It preserves existing functionality.
- Any deviation is documented and justified.

## 32. Final Coding-Agent Instruction

Apply this design system as a functional standard, not merely as visual inspiration.

Do not approximate the palette with unrelated colours. Do not create a new style for each application. Do not overuse gold. Do not reduce usability for visual effect. Do not alter working functionality unless explicitly approved.

Build all applications so they share the same visual language, interaction logic, component hierarchy, spacing discipline, typography, iconography, action hierarchy, accessibility standard, and professional production-focused character.

The result should feel like one coherent suite of Etch ’N’ Shine applications.
