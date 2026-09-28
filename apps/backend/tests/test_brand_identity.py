from __future__ import annotations

import re

import pytest

from app.domains.assistant.prompt import GENERAL_SYSTEM_PROMPT, build_general_messages
from app.domains.brand.profile import (
    BRAND_PROFILE_VERSION,
    IdentityTier,
    identity_block,
)
from app.domains.campaign_assistant.prompt import SYSTEM_PROMPT as CAMPAIGN_SYSTEM_PROMPT
from app.domains.lead_assistant.prompt import (
    build_autofill_messages,
    build_briefing_messages,
    build_digest_messages,
    build_filter_messages,
)
from app.domains.outreach.prompt import SYSTEM_PROMPT as OUTREACH_SYSTEM_PROMPT

# Approximate token cost at four characters per token. These ceilings exist because the local
# model runs an 8,192-token window that halves to 4,096 in the protected profile.
_TIER_TOKEN_CEILINGS = {
    IdentityTier.BRIEF: 450,
    IdentityTier.CORE: 1_450,
    IdentityTier.WRITING: 2_100,
}


def test_brand_profile_version_is_set() -> None:
    assert BRAND_PROFILE_VERSION


@pytest.mark.parametrize("tier", list(IdentityTier))
def test_no_tier_hard_codes_a_price_or_a_product_count(tier: IdentityTier) -> None:
    # Pricing is the operator's to give, and counts go stale the moment the catalogue changes.
    block = re.sub(r"\s+", " ", identity_block(tier))
    assert re.search(r"£\s?\d", block) is None, f"{tier} hard-codes a price"
    assert "never quote" in block.casefold()


@pytest.mark.parametrize("tier", list(IdentityTier))
def test_every_tier_states_the_business_the_operator_and_uk_english(tier: IdentityTier) -> None:
    block = identity_block(tier)
    assert "Etch 'N' Shine" in block
    assert "Malek" in block
    assert "UK English" in block
    assert "£" in block


@pytest.mark.parametrize("tier", list(IdentityTier))
def test_every_tier_bans_the_generic_gift_shop_phrases(tier: IdentityTier) -> None:
    # The blocks are hard-wrapped for readability, so compare on collapsed whitespace.
    block = re.sub(r"\s+", " ", identity_block(tier)).casefold()
    for phrase in (
        "perfect for any occasion",
        "high quality materials",
        "a truly unique gift",
    ):
        assert phrase in block, f"{tier} must ban {phrase!r}"


@pytest.mark.parametrize("tier", list(IdentityTier))
def test_each_tier_stays_inside_its_token_budget(tier: IdentityTier) -> None:
    estimated_tokens = len(identity_block(tier)) // 4
    assert estimated_tokens <= _TIER_TOKEN_CEILINGS[tier]


def test_tiers_grow_from_brief_to_writing() -> None:
    brief = len(identity_block(IdentityTier.BRIEF))
    core = len(identity_block(IdentityTier.CORE))
    writing = len(identity_block(IdentityTier.WRITING))
    assert brief < core < writing


def test_the_writing_tier_carries_the_tone_principles() -> None:
    writing = identity_block(IdentityTier.WRITING)
    assert "Lead with the moment, not the product" in writing
    assert "Business and bulk buyers" in writing
    # The core tier must stay lean enough to leave room for the workspace snapshot.
    assert "Lead with the moment, not the product" not in identity_block(IdentityTier.CORE)


def test_the_copilot_system_prompt_keeps_its_scope_rules_and_gains_the_identity() -> None:
    prompt = build_general_messages(
        [],
        app_context={"snapshot_at": "2026-09-27T00:00:00+00:00"},
        attachment_context_chars=1_000,
        artifact_format=None,
    )
    system = prompt[0]["content"]
    assert system.startswith(GENERAL_SYSTEM_PROMPT)
    assert identity_block(IdentityTier.CORE) in system
    assert "Trusted local workspace snapshot" in system


def test_the_copilot_falls_back_to_the_brief_tier_under_a_tight_window() -> None:
    system = build_general_messages(
        [],
        app_context={},
        attachment_context_chars=1_000,
        artifact_format=None,
        identity_tier=IdentityTier.BRIEF,
    )[0]["content"]
    assert identity_block(IdentityTier.BRIEF) in system
    assert identity_block(IdentityTier.CORE) not in system


def test_outreach_refinement_gets_the_full_writing_voice() -> None:
    assert identity_block(IdentityTier.WRITING) in OUTREACH_SYSTEM_PROMPT
    assert "Return only the subject and body fields." in OUTREACH_SYSTEM_PROMPT


def test_the_outreach_rules_reach_conversation_and_copy_but_not_the_lean_tier() -> None:
    core = identity_block(IdentityTier.CORE)
    writing = identity_block(IdentityTier.WRITING)
    brief = identity_block(IdentityTier.BRIEF)

    # The essentials are needed whenever Malek asks for an email in conversation.
    for tier_text in (core, writing):
        assert "90 to 150 words" in tier_text
        assert "One ask only" in tier_text
        assert "[PRICE]" in tier_text

    # The long tail only earns its tokens where copy is actually produced.
    assert "circling back" in writing
    assert "circling back" not in core
    assert "90 to 150 words" not in brief


def test_every_tier_refuses_to_quote_a_price() -> None:
    for tier in IdentityTier:
        assert "never quote" in identity_block(tier).casefold()


def test_the_campaign_planner_gets_the_brief_voice_without_losing_its_rules() -> None:
    assert identity_block(IdentityTier.BRIEF) in CAMPAIGN_SYSTEM_PROMPT
    assert "Return exactly one JSON object matching the supplied schema." in CAMPAIGN_SYSTEM_PROMPT
    assert "draft_ready" in CAMPAIGN_SYSTEM_PROMPT


def test_lead_briefing_and_digest_get_the_brief_voice() -> None:
    brief = identity_block(IdentityTier.BRIEF)
    briefing = build_briefing_messages(context={"business_name": "Example Cafe"})
    digest = build_digest_messages(candidates=[])
    for messages in (briefing, digest):
        assert brief in messages[0]["content"]


def test_autofill_gets_the_full_writing_voice_and_the_field_formats() -> None:
    # These four fields are pasted into an email verbatim, so they need the voice and an
    # explicit shape, not just a topic.
    system = build_autofill_messages(
        business_name="Example Cafe",
        segment="cafe",
        location="Bristol",
        website_evidence=None,
        existing_notes="",
    )[0]["content"]
    assert identity_block(IdentityTier.WRITING) in system
    assert "one complete sentence addressed to the business" in system
    assert "one ask" in system


def test_autofill_drops_to_the_brief_voice_under_a_tight_window() -> None:
    system = build_autofill_messages(
        business_name="Example Cafe",
        segment="cafe",
        location="Bristol",
        website_evidence=None,
        existing_notes="",
        identity_tier=IdentityTier.BRIEF,
    )[0]["content"]
    assert identity_block(IdentityTier.BRIEF) in system
    assert identity_block(IdentityTier.WRITING) not in system


def test_the_filter_translator_stays_free_of_identity_context() -> None:
    # Mapping a phrase onto dropdown values needs no brand voice, and the window is precious.
    system = build_filter_messages(
        query="florists in Bristol",
        available_stages=["new"],
        available_source_types=["manual"],
        campaigns=[],
    )[0]["content"]
    assert "Etch 'N' Shine" not in system
