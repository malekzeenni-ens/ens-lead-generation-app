# Etch ’N’ Shine Lead Generation App
## Business Requirements Document (BRD) and Functional Specification Document (FSD)

**Document status:** Draft for Solution Architecture Review  
**Business owner:** Etch ’N’ Shine  
**Primary user:** Business owner / administrator  
**Prepared for:** Solution Architect review and technical architecture proposal  
**Version:** 1.0  
**Date:** 18 July 2026

---

# 1. Document Purpose

This document defines the business requirements and functional specification for a locally hosted lead generation, lead intelligence, outreach preparation, and lightweight sales pipeline application for Etch ’N’ Shine.

The document is intended to be reviewed by a solution architect who will:

- Validate the proposed functional scope.
- Assess feasibility and technical constraints.
- Recommend the most appropriate target architecture.
- Identify external data-source, API, licensing, compliance, security, and operational risks.
- Propose an implementation approach and phased delivery plan.
- Challenge any requirement that creates disproportionate cost, risk, or complexity.

This document deliberately avoids prescribing a final architecture. Where technical options are mentioned, they represent functional assumptions or possible implementation directions, not mandatory design decisions.

---

# 2. Executive Summary

Etch ’N’ Shine requires a local-first application that helps identify, qualify, prioritise, and contact commercially relevant business prospects.

The initial focus is on bakeries and home-baking businesses within 25 miles of Luton. Wedding planners are the second-priority segment, followed by coffee shops, estate agents, small independent restaurants, and independent gyms.

The app must maintain a broader lead database while surfacing only the best 5–10 leads each week. It must explain why each lead is commercially relevant, recommend suitable Etch ’N’ Shine products, generate personalised email and Instagram outreach, and track the lead through a lightweight sales pipeline.

The application must prioritise lead quality over volume. It must not operate as a bulk contact scraper, mass-mailing platform, automated Instagram bot, or generic enterprise CRM.

The initial release will support assisted and automated lead discovery, local storage, AI-assisted lead analysis, outreach drafting, manual approval, pipeline tracking, follow-up reminders, analytics, and data export. Direct Zoho email integration will be delivered in a later phase after the manual-draft workflow is validated.

---

# 3. Business Context

Etch ’N’ Shine is a UK-based personalised laser engraving and cutting business. Its products include:

- Acrylic and wooden cake toppers.
- Cake charms and cupcake charms.
- Acrylic tabletop signs.
- Small-format acrylic and wooden signs.
- Personalised tumblers.
- Branded event and business accessories.
- Personalised gifts and small-batch business products.

The business currently sells through Shopify, Etsy, Instagram, direct enquiries, repeat customers, and business relationships.

The business requires a more structured method for identifying relevant prospects and converting them into qualified commercial opportunities.

---

# 4. Business Problem

Lead generation is currently expected to rely heavily on manual searching, ad hoc outreach, direct enquiries, and marketplace traffic.

The main business problems are:

1. There is no structured prospect database.
2. There is no repeatable process for identifying the most relevant local businesses.
3. Manual research takes time and produces inconsistent results.
4. There is no standard method for comparing or prioritising leads.
5. Product recommendations and outreach messaging must currently be prepared manually.
6. Follow-up activity can be missed or handled inconsistently.
7. There is limited visibility of which segments, products, sources, and outreach channels produce results.
8. There is no consistent suppression or do-not-contact control across prospecting activity.

---

# 5. Business Objectives

The application must support the following business objectives:

## 5.1 Primary Objectives

- Build a reusable and searchable database of relevant business prospects.
- Surface the best 5–10 prospects each week.
- Reduce time spent manually researching low-quality businesses.
- Improve the relevance and personalisation of outreach.
- Increase the number of qualified replies, mock-up requests, quote requests, and orders.
- Create a repeatable lead generation process that can later scale beyond Luton.

## 5.2 Secondary Objectives

- Provide visibility of campaign and segment performance.
- Standardise the lead qualification process.
- Support consistent follow-up activity.
- Retain control over all external communication.
- Prepare for future Zoho integration.
- Support additional customer segments without redesigning the entire application.

## 5.3 Non-Objectives

The application is not intended to:

- Replace a full enterprise CRM.
- Send large volumes of unsolicited emails.
- Automate Instagram DMs.
- Monitor social accounts continuously for every lead.
- Purchase or manage advertising campaigns.
- Create customer orders automatically.
- Commit pricing or discounts without user approval.
- Scrape platforms in ways that violate platform terms.
- Produce guaranteed sales outcomes.

---

# 6. Scope

## 6.1 In Scope for MVP

- Local-first application.
- Single primary user.
- Campaign creation and configuration.
- Lead discovery through supported and assisted sources.
- Manual lead entry.
- CSV lead import.
- Lead deduplication.
- Lead enrichment.
- Lead scoring with explanation.
- AI-assisted business summarisation.
- Product-to-lead matching.
- Weekly lead shortlist.
- Email drafting.
- Instagram DM drafting.
- Explicit approval before any communication is considered ready.
- Manual email sending through Zoho in the MVP.
- Manual Instagram DM sending.
- Lightweight sales pipeline.
- Follow-up reminders.
- Contact history.
- Lead notes.
- Do-not-contact and suppression controls.
- Basic analytics.
- CSV and JSON export.
- Backup and restore.
- Settings and API-key management.

## 6.2 In Scope for Phase 2

- Zoho draft creation.
- Zoho approved-email sending.
- Email status and delivery tracking where supported.
- Shopify product catalogue synchronisation.
- Reusable campaign templates.
- Improved scoring models by customer segment.
- UK-wide campaign support.
- Quote-request tracking.
- Mock-up and physical sample workflow.
- Advanced duplicate detection.
- More configurable scheduling.

## 6.3 In Scope for Phase 3

- Integrated quote builder.
- Repeat-customer opportunity identification.
- Revenue attribution.
- Multi-user support.
- Geographic mapping.
- Local AI model option.
- Learning-based recommendations.
- Mobile companion or responsive field-use mode.
- Referral campaign support.

## 6.4 Out of Scope

- Automated Instagram login, sending, or bot behaviour.
- Unattended bulk email sequences.
- Continuous monitoring of every prospect’s social activity.
- Automatic price negotiation.
- Automated product sample fulfilment.
- Fully autonomous AI decision-making.
- Data acquisition methods that bypass access controls.
- Multi-tenant SaaS hosting in the initial release.

---

# 7. Target Customer Segments

## 7.1 Priority 1: Bakeries and Home-Baking Businesses

Initial location: within 25 miles of Luton.

Relevant products:

- Acrylic cake toppers.
- Wooden cake toppers.
- Acrylic logo cake charms.
- Reusable bakery-branded charms.
- Cupcake charms.
- QR booking signs.
- Social-media handle signs.
- Tabletop display signs.

Key qualification indicators:

- Recent and regular posting.
- Consistent content quality.
- Celebration cake activity.
- Wedding or event cake activity.
- Evidence of active trading.
- Appropriate location.
- Public contact route.
- Potential repeat demand.

## 7.2 Priority 2: Wedding Planners

Relevant products:

- Table numbers.
- Reserved signs.
- Place names.
- Small event signs.
- Cake toppers and charms.
- Bridal-party tumblers.
- Event branding accessories.

## 7.3 Additional Segments

- Coffee shops.
- Estate agents.
- Small independent restaurants.
- Independent gyms.

The data model and campaign configuration must support these segments from the start, but segment-specific scoring and outreach optimisation may be delivered progressively.

---

# 8. Geographic Scope

## 8.1 Initial Scope

- Primary search centre: Luton, United Kingdom.
- Initial radius: 25 miles.
- Leads closer to Luton should receive stronger local-relevance weighting.

## 8.2 Future Scope

- Configurable UK locations.
- UK-wide campaigns.
- Optional territory and county filters.
- Optional collection-versus-delivery targeting.

---

# 9. Commercial Offer Rules

The app must support the following commercial positioning:

- Free digital mock-up may be offered by default.
- Introductory discount may be mentioned where appropriate.
- Pricing review may be offered where a prospect can commit to recurring minimum order quantities.
- A free physical sample should normally be considered only after the prospect replies positively.
- The app must not promise a discount, free sample, lead time, price, or order capacity without explicit user approval.

The user must be able to enable, disable, or edit each offer at campaign and lead level.

---

# 10. User Roles

## 10.1 MVP Role

### Administrator / Business Owner

The administrator can:

- Manage settings.
- Create campaigns.
- Discover and import leads.
- Edit lead details.
- Approve or reject AI recommendations.
- Approve outreach drafts.
- Record contact activity.
- Manage the pipeline.
- View analytics.
- Export and delete data.
- Manage suppression status.
- Configure AI and future Zoho integration.

## 10.2 Future Roles

Potential later roles may include:

- Sales assistant.
- Read-only analyst.
- Production reviewer.
- System administrator.

Role-based access control is not mandatory for the MVP but should not be precluded by the architecture.

---

# 11. Business Process Overview

The target business process is:

1. User creates or selects a lead-generation campaign.
2. User configures target segment, location, radius, sources, product focus, and weekly target.
3. The app discovers or imports candidate businesses.
4. The app normalises and deduplicates lead records.
5. The app enriches the lead using available public information.
6. The app records sources and collection dates.
7. The app calculates a transparent score.
8. AI summarises the business and suggests product fit and outreach angle.
9. The app ranks the lead against other prospects.
10. The app surfaces the best 5–10 leads for the week.
11. The user reviews the lead and evidence.
12. The user generates or edits an email and Instagram DM.
13. The user explicitly approves the outreach.
14. For MVP email, the user copies and sends through Zoho manually.
15. For Instagram, the app copies the message and opens the profile for manual sending.
16. The user confirms the contact was completed.
17. The app records the communication and follow-up date.
18. The lead progresses through the pipeline.
19. The user records reply, mock-up, sample, quote, won, lost, or do-not-contact outcomes.
20. Analytics update based on recorded activity.

---

# 12. Functional Requirements

Requirements are identified using the following format:

- **BR-xxx:** Business requirement.
- **FR-xxx:** Functional requirement.
- **NFR-xxx:** Non-functional requirement.
- **DR-xxx:** Data requirement.
- **INT-xxx:** Integration requirement.
- **SEC-xxx:** Security requirement.

Priority classifications:

- **Must:** Required for the stated phase.
- **Should:** High-value but not necessarily release-blocking.
- **Could:** Optional enhancement.
- **Won’t:** Explicitly excluded from the phase.

---

# 13. Campaign Management

## BR-001

The business must be able to define targeted lead-generation campaigns.

## FR-001 — Create Campaign

**Priority:** Must

The user must be able to create a campaign with:

- Campaign name.
- Description.
- Customer segment.
- Primary location.
- Search radius.
- Keywords.
- Exclusion keywords.
- Relevant product categories.
- Discovery sources.
- Weekly shortlist size.
- Minimum score threshold.
- Preferred outreach channels.
- Offer settings.
- AI model or provider selection.
- Manual, scheduled, or combined discovery mode.
- Campaign status.

## FR-002 — Edit Campaign

The user must be able to edit active and inactive campaigns without deleting historical lead relationships.

## FR-003 — Pause and Resume Campaign

The user must be able to pause discovery and recommendations while preserving existing data.

## FR-004 — Duplicate Campaign

The user should be able to duplicate a campaign and change segment or location parameters.

## FR-005 — Campaign Validation

The app must validate campaign inputs and prevent invalid configurations such as:

- Missing segment.
- Missing location.
- Zero or negative radius.
- Weekly shortlist below 1.
- Unsupported source selected without configuration.

---

# 14. Lead Discovery

## BR-002

The business must be able to build a larger prospect database using both assisted and automated discovery methods.

## FR-010 — Manual Lead Entry

The user must be able to enter a lead manually.

Minimum fields:

- Business name.
- Segment.
- Location.
- Source.
- Website or social profile.

## FR-011 — CSV Import

The user must be able to import a CSV file.

The import process must:

- Preview data.
- Map columns.
- Validate required fields.
- Identify invalid rows.
- Detect potential duplicates.
- Allow user confirmation before creating records.
- Produce an import result summary.

## FR-012 — Google-Based Discovery

The app should support discovery of businesses through an approved or supported Google-based method.

The solution architect must assess whether this is delivered through:

- Google Places API.
- Google Maps links and assisted search.
- Search-engine result enrichment.
- Another compliant provider.

The app must not rely on unauthorised scraping.

## FR-013 — Instagram Discovery

The app should support discovery or capture of public Instagram business profiles.

The solution architect must assess:

- Available official APIs.
- Business account limitations.
- Manual or assisted capture.
- Search result use.
- Data that can legally and reliably be stored.

The MVP may use assisted search, manual profile capture, or approved search-provider results.

## FR-014 — Facebook Discovery

The app should support discovery or capture of public Facebook business pages through supported or assisted methods.

## FR-015 — Website Discovery and Enrichment

The app should identify and inspect public business websites for relevant information.

## FR-016 — Discovery Run

The user must be able to start a discovery run manually.

The run must record:

- Campaign.
- Start and finish times.
- Sources queried.
- Number of candidates found.
- Number created.
- Number merged.
- Number rejected.
- Errors.
- API usage where relevant.

## FR-017 — Scheduled Discovery

The app should support scheduled campaign runs.

Minimum scheduling options:

- Weekly.
- Selected weekday.
- Manual plus scheduled.

## FR-018 — Discovery Limits

The user must be able to define limits per campaign or run to control API cost and database growth.

## FR-019 — Assisted Search Workflow

Where automated discovery is not supported, the app should provide:

- Prebuilt search queries.
- Open-search actions.
- Profile capture form.
- Browser-to-app copy workflow.
- Source-link storage.

---

# 15. Lead Deduplication and Identity Resolution

## BR-003

The app must reduce duplicate prospect records and duplicate outreach.

## FR-020 — Duplicate Detection

The app must detect likely duplicates using combinations of:

- Normalised business name.
- Website domain.
- Email address.
- Telephone number.
- Instagram handle.
- Facebook page URL.
- Postal address.
- Geographic proximity.

## FR-021 — Duplicate Confidence

Potential duplicates must be classified as:

- Confirmed duplicate.
- High-confidence match.
- Possible match.
- Not a duplicate.

## FR-022 — Merge Leads

The user must be able to merge records while preserving:

- Source evidence.
- Notes.
- Communications.
- Pipeline history.
- Scores.
- Suppression status.

## FR-023 — Duplicate Outreach Prevention

The app must warn the user before preparing or recording outreach to a lead with a recent communication or an associated duplicate record.

---

# 16. Lead Enrichment

## BR-004

The app must provide sufficient information for the user to judge whether a business is worth contacting.

## FR-030 — Business Details

The app should store, where publicly available:

- Business name.
- Trading name.
- Segment.
- Description.
- Address.
- Town or city.
- Postcode.
- Geographic coordinates.
- Distance from campaign location.
- Website.
- Public email.
- Public telephone number.
- Instagram URL and handle.
- Facebook page URL.
- Follower count.
- Posting frequency.
- Most recent post date.
- Services or product categories observed.
- Opening or collection information.

## FR-031 — Source Evidence

Every enriched field should store, where applicable:

- Source type.
- Source URL.
- Collection date.
- Verification status.
- Extraction method.

## FR-032 — Information Classification

The app must classify information as:

- Verified.
- Inferred.
- Suggested.
- Unknown.

## FR-033 — Lead Summary

The app should generate a concise business summary using verified data.

## FR-034 — Missing Information

The app must display missing information and must not create fabricated substitutes.

## FR-035 — Refresh Lead

The user should be able to manually refresh a lead’s public information.

Continuous social monitoring is out of scope for MVP.

---

# 17. Lead Qualification and Scoring

## BR-005

The business must be able to compare prospects using a transparent and editable qualification model.

## FR-040 — Score Calculation

Each lead must receive a score from 0 to 100.

## FR-041 — Bakery Scoring Model

The initial bakery model should support the following configurable categories:

### Business Relevance — default 25 points

- Valid bakery or home-baking business.
- Celebration cake focus.
- Personalised or event work.

### Activity — default 20 points

- Recent activity.
- Regular posting.
- Consistency.

### Product Fit — default 20 points

- Potential need for cake toppers.
- Potential need for charms.
- Existing personalised products.
- Evidence of cake/event demand.

### Local Relevance — default 15 points

- Distance from Luton.
- Local collection or service coverage.

### Commercial Potential — default 10 points

- Repeat-order indicators.
- Event and wedding work.
- Broad or active order portfolio.

### Reach and Credibility — default 5 points

- Follower base.
- Engagement or professional presentation.

### Contactability — default 5 points

- Public email.
- Instagram messaging route.
- Website contact option.

## FR-042 — Score Explanation

The app must provide a human-readable explanation showing:

- Points awarded.
- Points not awarded.
- Evidence used.
- Missing evidence.
- Any AI inference.

## FR-043 — Configurable Weights

The user should be able to adjust scoring weights by campaign or segment.

## FR-044 — Manual Override

The user must be able to override the score and record a reason.

## FR-045 — Disqualification

The user must be able to mark a lead as not suitable and record a reason.

## FR-046 — Segment-Specific Models

The architecture should support separate scoring models for wedding planners, coffee shops, estate agents, restaurants, and gyms.

---

# 18. Product Matching

## BR-006

The app must recommend relevant Etch ’N’ Shine products for each qualified lead.

## FR-050 — Product Catalogue

The app must contain an editable product catalogue with:

- Product name.
- Category.
- Description.
- Target segments.
- Example use cases.
- Image or image reference.
- Active status.
- Optional pricing guidance.
- Sample eligibility.

## FR-051 — Matching Rules

The app must support deterministic product-to-segment rules.

## FR-052 — AI-Assisted Product Fit

AI may recommend products based on verified lead information.

## FR-053 — Recommendation Explanation

Every recommendation must explain:

- Why the product is relevant.
- Which evidence supports the recommendation.
- Whether the recommendation is rule-based or AI-assisted.

## FR-054 — User Override

The user must be able to add, remove, reorder, or edit recommendations.

## FR-055 — Suggested Offer

The app may recommend:

- Free digital mock-up.
- Introductory discount.
- Recurring-order pricing review.
- Physical sample after positive reply.

No offer should be treated as approved until the user confirms it.

---

# 19. Weekly Recommendation Engine

## BR-007

The app must surface only the strongest 5–10 opportunities each week while preserving the larger prospect database.

## FR-060 — Weekly Shortlist

The app must generate a weekly shortlist using:

- Lead score.
- Product fit.
- Local relevance.
- Contactability.
- Previous contact history.
- Suppression status.
- Campaign status.
- Lead freshness.
- Pipeline stage.
- User capacity.

## FR-061 — Shortlist Size

The default shortlist is 5–10 leads per week and must be configurable.

## FR-062 — Recommendation Reason

Each shortlisted lead must display why it was selected.

## FR-063 — Replace Lead

The user must be able to defer, dismiss, or replace a shortlisted lead.

## FR-064 — Contact Capacity Control

The app should warn when the user attempts to approve more leads than the configured weekly capacity.

## FR-065 — No Duplicate Recommendation

A lead should not be re-recommended too soon unless:

- Follow-up is due.
- The user manually requests it.
- The lead was deferred rather than rejected.

---

# 20. Outreach Drafting and Approval

## BR-008

The app must prepare personalised outreach while keeping the user in full control.

## FR-070 — Email Draft Generation

The app must generate:

- Subject.
- Email body.
- Recommended product proposition.
- Suggested call to action.

## FR-071 — Instagram DM Generation

The app must generate concise Instagram DM copy.

## FR-072 — Evidence-Based Personalisation

Outreach may use only recorded business facts and clearly marked suggestions.

## FR-073 — Prohibited AI Inventions

The app must not invent:

- Contact names.
- Existing relationships.
- Events.
- Purchase intent.
- Customer requirements.
- Contact information.
- Unsupported compliments.

## FR-074 — Draft Editing

The user must be able to edit all generated content.

## FR-075 — Approval Status

Drafts must have statuses such as:

- Generated.
- Edited.
- Approved.
- Sent manually.
- Sent through integration.
- Rejected.

## FR-076 — Explicit Approval

No external email may be sent without a specific approval action.

## FR-077 — Copy Email

The MVP must allow the subject and body to be copied for manual use in Zoho.

## FR-078 — Instagram Assisted Send

The app must:

- Copy the DM.
- Open the relevant Instagram profile.
- Prompt the user to confirm whether it was sent.

## FR-079 — Outreach Templates

The app should support editable base templates by segment and channel.

## FR-080 — Tone Controls

The user should be able to choose or configure tone such as:

- Professional.
- Friendly.
- Concise.
- Premium.
- Local-business focused.

---

# 21. Zoho Email Integration

## BR-009

The app should later integrate with Zoho for email draft creation and approved sending.

## INT-001 — Zoho Integration Phase

Zoho integration is Phase 2, not MVP.

## INT-002 — Authentication

The solution architect must assess the appropriate Zoho authentication model, likely OAuth-based.

## INT-003 — Create Draft

The app should be able to create a Zoho email draft.

## INT-004 — Send Approved Email

The app should send an email only after explicit approval.

## INT-005 — Message Tracking

Where supported, the app should store:

- Zoho message ID.
- Send timestamp.
- Delivery status.
- Failure reason.

## INT-006 — Reply Handling

The solution architect should assess whether reply detection is feasible and proportionate.

## INT-007 — Failure Handling

Zoho integration failures must not delete the draft, alter the lead incorrectly, or mark the communication as sent.

---

# 22. Pipeline and Opportunity Management

## BR-010

The app must track each prospect from discovery to outcome.

## FR-090 — Pipeline Stages

The system must support the following stages:

- New.
- Researching.
- Qualified.
- Recommended This Week.
- Ready to Contact.
- Contacted.
- Follow-Up Due.
- Replied.
- Mock-Up Requested.
- Sample Consideration.
- Quote Requested.
- Quote Sent.
- Negotiating.
- Won.
- Lost.
- Not Suitable.
- Do Not Contact.

## FR-091 — Simplified View

The default pipeline view should show a reduced set of grouped stages to avoid unnecessary complexity.

## FR-092 — Stage Change

The user must be able to move leads between stages.

## FR-093 — Stage History

Every stage change must be recorded with:

- Previous stage.
- New stage.
- Timestamp.
- User.
- Optional reason.

## FR-094 — Opportunity Value

The user should be able to record:

- Estimated order value.
- Quote value.
- Won value.
- Potential recurrence.

There is no mandatory minimum opportunity value.

## FR-095 — Lost Reason

Lost leads should support reasons such as:

- No response.
- Not interested.
- Price.
- No current need.
- Already has supplier.
- Outside scope.
- Other.

---

# 23. Follow-Up Management

## BR-011

The app must reduce missed follow-ups.

## FR-100 — Follow-Up Date

The user must be able to assign a next-action date.

## FR-101 — Follow-Up Type

The user should be able to record:

- Email follow-up.
- Instagram follow-up.
- Mock-up action.
- Sample action.
- Quote action.
- General reminder.

## FR-102 — Follow-Up Dashboard

The dashboard must show:

- Due today.
- Overdue.
- Due this week.

## FR-103 — Completion

The user must be able to mark a follow-up as completed and create the next one.

## FR-104 — No Unattended Sequences

Automated multi-step outreach sequences are out of scope for MVP.

---

# 24. Communication History

## FR-110 — Record Communication

The system must record:

- Channel.
- Subject where relevant.
- Message content or snapshot.
- Draft status.
- Sent status.
- Sent date.
- User confirmation.
- External message ID where available.

## FR-111 — Manual Confirmation

For Instagram and manually sent Zoho email, the user must confirm that the communication was sent.

## FR-112 — Reply Logging

The user must be able to record a reply and add notes.

## FR-113 — Communication Timeline

Each lead must have a chronological activity timeline.

---

# 25. Mock-Up, Sample, and Quote Tracking

## BR-012

The app should support the commercial steps that occur after a positive reply.

## FR-120 — Mock-Up Request

The user should be able to mark that a free digital mock-up was requested.

## FR-121 — Mock-Up Status

Suggested statuses:

- Not offered.
- Offered.
- Requested.
- In progress.
- Sent.
- Approved.
- Rejected.

## FR-122 — Sample Consideration

The app should record whether a physical sample is:

- Not applicable.
- Under consideration.
- Approved.
- Sent.
- Declined.

## FR-123 — Quote Status

The app should record:

- Quote requested.
- Quote being prepared.
- Quote sent.
- Quote accepted.
- Quote declined.

Detailed quote generation is out of scope for MVP.

---

# 26. Analytics and Reporting

## BR-013

The business must be able to understand whether the lead-generation process is working.

## FR-130 — Core Metrics

The dashboard should report:

- Leads discovered.
- Leads created.
- Leads qualified.
- Leads shortlisted.
- Leads contacted.
- Replies.
- Mock-up requests.
- Sample considerations.
- Quote requests.
- Quotes sent.
- Won opportunities.
- Lost opportunities.
- Recorded revenue.

## FR-131 — Conversion Metrics

The app should calculate:

- Discovery-to-qualified rate.
- Qualified-to-contacted rate.
- Contacted-to-reply rate.
- Reply-to-quote rate.
- Quote-to-win rate.

## FR-132 — Segment Performance

The user should be able to compare performance by customer segment.

## FR-133 — Source Performance

The user should be able to compare performance by lead source.

## FR-134 — Product Performance

The user should be able to compare recommended products and resulting opportunities.

## FR-135 — Channel Performance

The user should be able to compare email and Instagram results based on recorded outcomes.

## FR-136 — Date Filters

Analytics must support date filtering.

## FR-137 — Export

Analytics should be exportable to CSV.

---

# 27. Dashboard and Navigation

## BR-014

The app must provide a simple operational view suitable for a small-business owner.

## FR-140 — Primary Navigation

Recommended top-level navigation:

1. Dashboard.
2. Weekly Leads.
3. All Leads.
4. Campaigns.
5. Pipeline.
6. Outreach.
7. Analytics.
8. Settings.

## FR-141 — Dashboard Panels

The dashboard should include:

- Recommended leads this week.
- Follow-ups due.
- Approved but unsent emails.
- Instagram DMs ready to copy.
- Recent replies.
- Quotes requested.
- Pipeline summary.
- Data-quality warnings.
- Suppression warnings.

## FR-142 — Lead Card

Each lead card should display:

- Business name.
- Segment.
- Location and distance.
- Lead score.
- Score explanation.
- Product recommendations.
- Reason to contact.
- Website and social links.
- Contact routes.
- Recent activity.
- Outreach status.
- Pipeline stage.
- Follow-up date.
- Compliance or suppression status.

## FR-143 — Search and Filters

The user must be able to search and filter by:

- Name.
- Segment.
- Location.
- Campaign.
- Score.
- Stage.
- Contactability.
- Source.
- Follow-up status.
- Suppression status.

---

# 28. AI Functional Requirements

## BR-015

AI should improve research efficiency and message quality without controlling factual truth or external actions.

## FR-150 — AI Provider Abstraction

The system should support an interchangeable AI provider.

## FR-151 — Supported AI Tasks

AI may be used for:

- Business summary.
- Business categorisation.
- Product-fit recommendation.
- Outreach-angle recommendation.
- Email drafting.
- Instagram DM drafting.
- Score explanation.
- Lead-note summarisation.

## FR-152 — Human Review

All AI-generated external communication requires human review.

## FR-153 — Evidence References

AI outputs must identify the input evidence used where feasible.

## FR-154 — Confidence and Uncertainty

AI outputs should identify missing information and uncertainty.

## FR-155 — Regenerate

The user must be able to regenerate an output.

## FR-156 — Cost Controls

The app must support:

- Token or request logging.
- Per-run limits.
- Optional cheaper model selection.
- Avoiding repeated analysis when source data has not changed.
- User confirmation for high-cost bulk operations.

## FR-157 — Safe Failure

AI failure must not prevent manual lead entry, manual scoring, or pipeline use.

---

# 29. Data Requirements

## DR-001 — Lead

Suggested fields:

- Lead ID.
- Business name.
- Normalised name.
- Segment.
- Description.
- Website.
- Email.
- Telephone.
- Instagram handle and URL.
- Facebook URL.
- Address.
- Postcode.
- Latitude and longitude.
- Distance from campaign origin.
- Follower count.
- Posting frequency.
- Latest post date.
- Score.
- Score override.
- Qualification status.
- Pipeline stage.
- Suppression status.
- Created date.
- Updated date.

## DR-002 — Campaign

Suggested fields:

- Campaign ID.
- Name.
- Segment.
- Location.
- Radius.
- Keywords.
- Exclusions.
- Product categories.
- Sources.
- Schedule.
- Shortlist size.
- Scoring configuration.
- Offer configuration.
- Status.

## DR-003 — Source Evidence

Suggested fields:

- Evidence ID.
- Lead ID.
- Source type.
- Source URL.
- Field or claim supported.
- Extracted value.
- Verification classification.
- Collection method.
- Collection date.

## DR-004 — Lead Score

Suggested fields:

- Score ID.
- Lead ID.
- Campaign ID.
- Total score.
- Category scores.
- Explanation.
- Model version.
- Manual override.
- Override reason.
- Calculation date.

## DR-005 — Product

Suggested fields:

- Product ID.
- Name.
- Category.
- Description.
- Target segments.
- Use cases.
- Active status.
- Image reference.
- Pricing guidance.

## DR-006 — Product Recommendation

Suggested fields:

- Recommendation ID.
- Lead ID.
- Product ID.
- Rank.
- Reason.
- Evidence.
- Recommendation method.
- User decision.

## DR-007 — Communication

Suggested fields:

- Communication ID.
- Lead ID.
- Channel.
- Subject.
- Content.
- Draft status.
- Approval status.
- Sent status.
- Sent timestamp.
- External message ID.
- Response status.

## DR-008 — Follow-Up

Suggested fields:

- Follow-up ID.
- Lead ID.
- Type.
- Due date.
- Status.
- Notes.
- Completion date.

## DR-009 — Pipeline Event

Suggested fields:

- Event ID.
- Lead ID.
- Previous stage.
- New stage.
- Timestamp.
- Reason.

## DR-010 — Suppression Record

Suggested fields:

- Suppression ID.
- Lead or contact identifier.
- Suppression type.
- Reason.
- Effective date.
- Source.
- Notes.

## DR-011 — Discovery Run

Suggested fields:

- Run ID.
- Campaign ID.
- Start time.
- Finish time.
- Status.
- Sources used.
- Results count.
- Created count.
- Merged count.
- Rejected count.
- Error summary.
- API usage.

## DR-012 — Audit Event

Suggested fields:

- Audit ID.
- Event type.
- Entity type.
- Entity ID.
- Before value where relevant.
- After value where relevant.
- Timestamp.
- User.

---

# 30. Data Retention, Deletion, and Compliance Controls

This section defines application controls and does not constitute legal advice.

## FR-160 — Source Attribution

The app must retain the source and collection date for public lead data.

## FR-161 — Suppression

A lead marked Do Not Contact must not appear in outreach queues.

## FR-162 — Unsubscribe or Objection

The user must be able to record an objection or unsubscribe request.

## FR-163 — Data Deletion

The user must be able to delete a lead and associated personal data, subject to retention of minimal suppression evidence where appropriate.

## FR-164 — Data Export

The user must be able to export lead information and activity history.

## FR-165 — Retention Review

The app should support configurable retention review dates.

## FR-166 — Data Minimisation

The app should collect only information needed for qualification, outreach, and relationship tracking.

## FR-167 — Contact Classification

Where relevant, the app should distinguish:

- Business contact.
- Sole trader or individual contact.
- Unknown classification.

## FR-168 — Compliance Warning

The app should display warnings where contact classification or outreach basis is uncertain.

The solution architect should recommend where legal review is required before implementation.

---

# 31. Security Requirements

## SEC-001 — Local Access Control

The solution architect must assess whether local authentication is required for the MVP.

## SEC-002 — Password Storage

Where authentication is implemented, passwords must be securely hashed.

## SEC-003 — Secret Management

API keys and OAuth credentials must not be stored in frontend code or committed to source control.

## SEC-004 — Encryption

Sensitive credentials must be encrypted or stored using an appropriate operating-system or secrets-management mechanism.

## SEC-005 — Input Validation

All imported, scraped, API-returned, and user-entered data must be validated.

## SEC-006 — Output Sanitisation

Stored content must be sanitised before rendering.

## SEC-007 — Import Protection

CSV and other imports must be protected against malformed input and spreadsheet formula injection on export.

## SEC-008 — Least Privilege

External integrations must use minimum required permissions.

## SEC-009 — Audit Logging

Sensitive actions should be auditable, including:

- Sending email.
- Changing suppression status.
- Deleting lead data.
- Changing API configuration.
- Merging records.

## SEC-010 — Backup Protection

Backups containing lead and contact data must be protected from unauthorised access.

---

# 32. Non-Functional Requirements

## NFR-001 — Local-First Operation

Core lead, campaign, pipeline, and outreach-draft functions must operate from the locally hosted application.

## NFR-002 — Internet Dependency

Internet access may be required for:

- Lead discovery.
- Website enrichment.
- AI services.
- Zoho integration.

The app should clearly indicate when a feature is unavailable offline.

## NFR-003 — Performance

Indicative targets:

- Main dashboard loads within 3 seconds under normal local use.
- Lead search returns within 2 seconds for up to 10,000 leads.
- Lead-detail view loads within 2 seconds excluding external refresh.
- Bulk import of 1,000 leads completes without application failure.

The solution architect should validate realistic performance targets.

## NFR-004 — Availability

The local application should recover cleanly after restart and not require manual database repair after normal shutdown.

## NFR-005 — Reliability

External API failures must be isolated and must not corrupt lead data.

## NFR-006 — Usability

The app should be usable by a single small-business owner without CRM training.

## NFR-007 — Accessibility

The interface should follow practical accessibility standards, including keyboard navigation, contrast, labels, and focus states.

## NFR-008 — Maintainability

The solution should be modular and avoid hardcoding:

- A single AI provider.
- A single lead source.
- A single customer segment.
- A single email provider.

## NFR-009 — Observability

The app should include:

- Structured logs.
- Error logs.
- Integration status.
- Discovery-run status.
- Basic health check.

## NFR-010 — Backup and Restore

The app must support manual backup and restore.

Scheduled backup should be considered.

## NFR-011 — Port Management

If the app runs separate frontend and backend services, startup should detect and clearly report port conflicts.

## NFR-012 — Windows Compatibility

The app must run reliably in the user’s Windows environment.

## NFR-013 — Scalability

The MVP should support at least:

- 10,000 lead records.
- 100 campaigns.
- 50,000 evidence records.
- 100,000 activity and audit records.

The architect should validate whether higher targets are appropriate.

---

# 33. Integration Requirements and Assessment Areas

The solution architect must assess each integration for feasibility, cost, terms, security, and fallback.

## 33.1 Google Business Discovery

Assess:

- Google Places API suitability.
- Search quotas and costs.
- Available business fields.
- Radius search capability.
- Restrictions on storage and caching.
- Attribution requirements.
- Manual fallback.

## 33.2 Instagram

Assess:

- Official API limitations.
- Public business profile access.
- Discovery feasibility.
- Follower and posting data availability.
- Manual or assisted workflow.
- Terms and platform risk.

## 33.3 Facebook

Assess:

- Official API access.
- Business page discovery.
- Public field availability.
- Manual fallback.

## 33.4 Business Websites

Assess:

- Respect for robots and site terms.
- Request throttling.
- HTML extraction.
- Contact-page discovery.
- Structured data use.
- Data provenance.
- Error handling.

## 33.5 AI Provider

Assess:

- OpenAI, Claude, Gemini, or other provider options.
- Cost.
- Data handling.
- Model quality.
- Rate limits.
- Provider abstraction.
- Local model future option.

## 33.6 Zoho Mail

Assess:

- OAuth flow.
- Draft and send APIs.
- Message status.
- Rate limits.
- Token refresh.
- Local credential storage.
- Failure recovery.

---

# 34. Suggested Screen Catalogue

## 34.1 Dashboard

Purpose:

- Show weekly priorities and operational alerts.

Key components:

- Weekly recommended leads.
- Follow-ups due.
- Outreach ready.
- Pipeline summary.
- Recent replies.
- Warnings.

## 34.2 Weekly Leads

Purpose:

- Review and process the current 5–10 recommended leads.

Key actions:

- Review evidence.
- Adjust score.
- Approve or dismiss lead.
- Generate outreach.
- Defer.

## 34.3 All Leads

Purpose:

- Search and manage the full database.

Views:

- Table.
- Cards.
- Saved filters.

## 34.4 Lead Detail

Sections:

- Overview.
- Evidence.
- Scoring.
- Product recommendations.
- Outreach.
- Activity timeline.
- Follow-ups.
- Notes.
- Compliance and suppression.

## 34.5 Campaigns

Purpose:

- Create, edit, schedule, run, pause, and review campaigns.

## 34.6 Pipeline

Purpose:

- Manage leads by stage.

Suggested views:

- Kanban.
- Filtered table.

## 34.7 Outreach

Purpose:

- Manage generated, edited, approved, and sent outreach.

## 34.8 Analytics

Purpose:

- Evaluate lead quality and commercial performance.

## 34.9 Settings

Sections:

- Business profile.
- Product catalogue.
- Segments.
- Scoring models.
- AI provider.
- Zoho integration.
- Discovery sources.
- Scheduling.
- Backup and restore.
- Data retention.

---

# 35. Key User Stories

## US-001

As the business owner, I want to create a bakery campaign within 25 miles of Luton so that I can focus discovery on my highest-priority segment.

## US-002

As the business owner, I want the app to discover and store more leads than I contact each week so that I build a reusable prospect database.

## US-003

As the business owner, I want each lead to show why it is relevant so that I do not waste time on unsuitable businesses.

## US-004

As the business owner, I want the app to recommend products based on the lead’s activity so that outreach is commercially relevant.

## US-005

As the business owner, I want the app to surface only 5–10 strong leads weekly so that the process remains manageable.

## US-006

As the business owner, I want the app to draft email and Instagram messages so that I can contact leads quickly.

## US-007

As the business owner, I want all external messages to require approval so that the app cannot contact prospects without me.

## US-008

As the business owner, I want to record replies, mock-up requests, samples, and quotes so that I can manage each opportunity.

## US-009

As the business owner, I want do-not-contact controls so that I do not accidentally contact a suppressed business.

## US-010

As the business owner, I want to compare lead sources and segments so that I know where to focus my effort.

---

# 36. Acceptance Criteria

## 36.1 Campaign Acceptance Criteria

- A user can create a bakery campaign with Luton as the centre and a 25-mile radius.
- Invalid campaign settings are rejected with a clear message.
- A paused campaign does not run on schedule.

## 36.2 Discovery Acceptance Criteria

- A user can manually add a lead.
- A user can import a CSV and map columns.
- Duplicate candidates are shown before import.
- Every created lead records at least one source.
- Discovery errors do not remove previously stored leads.

## 36.3 Qualification Acceptance Criteria

- Every qualified lead receives a score from 0 to 100.
- The score includes a category-level explanation.
- The user can override a score.
- The override reason is stored.
- Missing data is shown as unknown rather than fabricated.

## 36.4 Weekly Lead Acceptance Criteria

- The system can generate a shortlist of 5–10 leads.
- Suppressed leads are excluded.
- Recently contacted leads are not selected as new prospects.
- The user can replace a recommendation.

## 36.5 Outreach Acceptance Criteria

- The app can generate an email and Instagram DM.
- Generated content can be edited.
- The app does not send an email without approval.
- The MVP can copy the email for manual use in Zoho.
- The app can open the Instagram profile and copy the DM.
- The user must confirm manual sending.

## 36.6 Pipeline Acceptance Criteria

- A lead can move through all defined stages.
- Stage changes are retained in history.
- Follow-up dates can be set and completed.
- Won and lost outcomes can be recorded.

## 36.7 Suppression Acceptance Criteria

- A Do Not Contact lead cannot be approved for outreach.
- An unsubscribe or objection can be recorded.
- A suppressed record remains protected during import and merge.

## 36.8 Data Acceptance Criteria

- Data can be exported to CSV or JSON.
- The local database can be backed up.
- The backup can be restored in a test environment.
- Deleting a lead removes associated personal data according to the configured deletion rules.

---

# 37. Initial Validation Plan

## 37.1 Pilot Campaign

**Name:** Luton Bakery Partnerships  
**Segment:** Bakeries and home bakers  
**Radius:** 25 miles from Luton  
**Prospect database target:** 50–100  
**Weekly shortlist:** 5–10  
**Products:** Cake toppers, cake charms, bakery branding accessories  
**Channels:** Email and Instagram  
**Offer:** Free digital mock-up and introductory pricing  
**Physical sample:** Consider only after positive reply

## 37.2 Pilot Duration

Recommended review period: 4–6 weeks.

## 37.3 Pilot Metrics

- Percentage of discovered businesses judged relevant.
- Percentage with a usable contact route.
- Number shortlisted.
- Number contacted.
- Reply rate.
- Mock-up request rate.
- Quote request rate.
- Win rate.
- Revenue generated.
- Average time spent per lead.
- Performance by source.
- Performance by channel.
- Product proposition response.

## 37.4 Validation Decision

At the end of the pilot, decide whether to:

- Refine bakery scoring.
- Add wedding planners.
- Expand the radius.
- Introduce Zoho integration.
- Improve discovery sources.
- Pause or remove low-performing features.

---

# 38. Key Risks and Mitigations

## Risk 1 — Poor Lead Quality

**Impact:** High  
**Mitigation:** Narrow campaign scope, transparent scoring, evidence requirements, manual review.

## Risk 2 — Platform Restrictions

**Impact:** High  
**Mitigation:** Use official APIs, approved providers, or assisted workflows; avoid unauthorised scraping.

## Risk 3 — AI Hallucination

**Impact:** High  
**Mitigation:** Source-linked data, fact classifications, human approval, deterministic controls.

## Risk 4 — Reputational Damage from Outreach

**Impact:** High  
**Mitigation:** Low weekly volume, personalised messaging, approval gates, suppression controls.

## Risk 5 — Excessive API Costs

**Impact:** Medium  
**Mitigation:** Usage limits, caching, manual runs, model selection, run previews.

## Risk 6 — Duplicate Contact

**Impact:** Medium to High  
**Mitigation:** Identity resolution, merge workflow, communication history, warning rules.

## Risk 7 — Data Protection or Marketing Compliance

**Impact:** High  
**Mitigation:** Data minimisation, source records, classification, suppression, retention review, legal assessment.

## Risk 8 — Overly Complex MVP

**Impact:** High  
**Mitigation:** Keep direct Zoho integration and advanced monitoring out of MVP.

## Risk 9 — Low User Adoption

**Impact:** Medium  
**Mitigation:** Weekly workflow, simple navigation, limited recommendations, clear next actions.

## Risk 10 — Dependency on One Provider

**Impact:** Medium  
**Mitigation:** Integration adapters and provider abstraction.

---

# 39. Assumptions

- The app is primarily used by one person in the MVP.
- The user has a Windows computer capable of running a local web application.
- Internet access is available for discovery and AI features.
- The user is willing to configure external API credentials where required.
- The user will review all outreach before sending.
- Instagram messages will be sent manually.
- Zoho integration is not required for the first MVP release.
- The initial focus is bakeries and home bakers within 25 miles of Luton.
- The business will contact approximately 5–10 qualified leads per week.
- No minimum order value will be enforced initially.
- Commercial offers remain subject to user approval.

---

# 40. Dependencies

Potential dependencies include:

- Approved business-discovery provider or API.
- AI API account.
- Website parsing capability.
- Optional geocoding service.
- Future Zoho developer application and OAuth setup.
- Product catalogue content and images.
- Outreach templates and brand tone.
- Local backup location.
- Legal or compliance review of prospecting workflows.

---

# 41. Open Questions for Solution Architect

The solution architect should explicitly answer the following:

1. What is the recommended local application architecture?
2. Should the app use a desktop wrapper, local web app, or another deployment model?
3. Is SQLite appropriate for the projected scale and concurrency?
4. What is the safest and most cost-effective Google business discovery approach?
5. What Instagram and Facebook data can be accessed through supported means?
6. Should website enrichment use a crawler, browser automation, structured data extraction, or a third-party service?
7. What controls are required to respect site terms, robots directives, and request limits?
8. What AI provider and model abstraction should be used?
9. How should evidence and AI outputs be versioned?
10. What job scheduler is appropriate for a local Windows app?
11. How should background tasks recover after shutdown or failure?
12. What credential-storage method is suitable on Windows?
13. How should Zoho OAuth and token refresh be implemented in Phase 2?
14. What level of audit logging is proportionate?
15. Should local authentication be mandatory for a single-user home environment?
16. What backup, encryption, and restore design should be used?
17. What database migration strategy should be adopted?
18. What browser-assisted capture method can improve Instagram and Facebook workflows without creating platform risk?
19. What legal and compliance review is required before launch?
20. What elements of the MVP should be simplified further?

---

# 42. Requested Architecture Deliverables

Following review of this BRD/FSD, the solution architect should provide:

1. Architecture assessment.
2. Recommended target architecture.
3. System context diagram.
4. Container or component diagram.
5. Data-flow diagrams.
6. Integration architecture.
7. Data architecture and logical data model.
8. Security architecture.
9. Background-job and scheduling design.
10. AI integration design.
11. Lead-source acquisition strategy.
12. Zoho integration strategy.
13. Local deployment model.
14. Backup and disaster-recovery design.
15. Logging and observability approach.
16. Technology-stack recommendation.
17. Build-versus-buy assessment for data sources.
18. API cost estimate and assumptions.
19. Architecture risks and mitigations.
20. MVP implementation roadmap.
21. Phase 2 and Phase 3 technical roadmap.
22. Testing strategy.
23. Deployment and support approach.
24. Architecture decision records for major choices.
25. Any recommended amendments to this BRD/FSD.

---

# 43. Definition of MVP Success

The MVP will be considered successful when:

- The user can create and run the Luton bakery campaign.
- The app can build a usable prospect database.
- The app reliably identifies duplicate prospects.
- Each lead includes evidence, score, explanation, and product recommendations.
- The app surfaces 5–10 suitable weekly leads.
- The app creates usable email and Instagram outreach drafts.
- No communication can be sent without explicit user approval.
- The user can track replies, mock-ups, samples, quotes, wins, and losses.
- The user can see which sources and channels are producing results.
- Data can be backed up, restored, exported, and deleted.
- The workflow produces measurable time savings or commercial opportunities during the pilot.

---

# 44. Final Architecture Principle

The application should be designed as a focused lead intelligence and outreach assistant for Etch ’N’ Shine.

The architecture must optimise for:

- Lead quality rather than lead volume.
- Explainability rather than opaque automation.
- Human approval rather than autonomous outreach.
- Modularity rather than provider lock-in.
- Local ownership of business data.
- Low operating complexity.
- Safe and proportionate scaling.

The solution architect should reject any design that turns the MVP into a large enterprise CRM, an uncontrolled scraping platform, or a mass outreach engine.
