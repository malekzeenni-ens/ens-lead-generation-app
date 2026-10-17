# ADR-023: Suppression covers every identifier

- **Status:** Accepted
- **Context:** A suppression stored one hash, of normalised business name and location. Locations are free text: a manually entered lead says "Leeds", while Google reports "12 High Street, Leeds LS1 1AA, UK". After a suppressed lead was privacy-deleted (FR-163), the next Google run hashed differently and created the business again. Phone, email, website and social handle were never checked against suppressions, in discovery or in manual create and edit.
- **Decision:** When a lead is suppressed, store a hash of every identifier it carries in `suppression_identifier`, one row per identifier. Check all of them wherever a lead is created, edited or promoted from discovery.

## Identifiers and how they are normalised

| Kind | Normalised value | Effect when it matches an active suppression |
|---|---|---|
| `name_location` | `lead_identifier_hash(name, location)`, the original format | Blocks |
| `website_host` | Host, lowercased, without `www.` | Blocks |
| `phone` | `phone_match_key` (last ten digits); ignored below nine digits | Blocks |
| `email` | Public and contact email, lowercased | Blocks |
| `social` | `platform:handle` for Instagram and Facebook | Blocks |
| `name` | `normalize_business_name(name)` | Discovery candidate goes to review |

Every value except `name_location` is hashed as `sha256("<kind>|<value>")`. A bare name is not unique, so it never blocks: a discovery candidate whose only match is a suppressed name goes to `review_required` with a `review_reason`, and the operator may promote it. A blocking identifier cannot be overridden from the review queue.

## Where the check runs

- `LeadService.create` and `LeadService.update`: an edit that adds a suppressed identifier is refused with `409 LEAD_IDENTIFIER_SUPPRESSED`, and `details.matched_identifier` names the kind. Edits to the suppressed lead itself are allowed.
- `CampaignAutomationService._promote_candidate`: for every provider and for assisted social capture.
- `LeadService.suppress` records the identifiers. `LeadService.delete` records any learned since the suppression, before the lead is removed.

Lifting a suppression releases its identifiers, because the lookup joins on `suppression_record.active`.

## Hashing choice

Plain SHA-256 is reversible by brute force for a phone number. A keyed hash would prevent that, but its key would have to live in the Windows DPAPI vault, so a backup restored on another machine could no longer match suppressions. The database is local and holds far more sensitive data in clear, so the plain hash was chosen, consistent with the original name/location hash.

## Known limitation

Migration `0017_suppression_identifiers` backfills identifiers from leads that still exist. A suppression whose lead was deleted before this change keeps only its name/location hash. The name-only review rule still catches most rediscoveries of such a business.

## Consequences

- Logs record the suppression ID and the matched identifier kind, never a value or hash.
- `tests/test_suppression_identifiers.py` covers rediscovery by each identifier, name-only review and promotion, manual create and edit, lifting, identifiers learned after suppression, and agreement between the migration's frozen hashing and the application's.
