import { describe, expect, it } from "vitest";

import {
  instagramDmUrl,
  instagramHandleFor,
  mailtoUrl,
  renderTemplate,
  whatsappUrl,
} from "./contact";
import type { Lead, Product } from "./types";

function buildProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: "product-1",
    shopify_handle: null,
    name: "Personalised Cake Topper",
    category: "Cake toppers",
    description: "",
    target_segments: [],
    example_use_cases: [],
    image_reference: null,
    active: true,
    pricing_guidance: null,
    sample_eligible: false,
    source: "manual",
    variant_count: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function buildLead(overrides: Partial<Lead> = {}): Lead {
  return {
    id: "lead-1",
    business_name: "Example Cakes",
    segment: "Bakeries and home bakers",
    location: "Luton",
    website: "https://example.test",
    social_profile: null,
    phone_number: null,
    public_email: null,
    social_identities: [],
    contact_classification: "unknown",
    pipeline_stage: "new",
    suppressed: false,
    estimated_order_value: null,
    quote_value: null,
    won_value: null,
    potential_recurrence: null,
    lost_reason: null,
    mock_up_status: "not_started",
    sample_status: "not_started",
    quote_status: "not_started",
    retention_review_date: null,
    current_score: null,
    score_updated_at: null,
    campaign_ids: [],
    sources: [],
    stage_events: [],
    notes: [],
    follow_ups: [],
    communications: [],
    suppression_records: [],
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("renderTemplate", () => {
  it("substitutes known placeholders from the lead", () => {
    const lead = buildLead({
      business_name: "Example Cakes",
      location: "Luton",
      phone_number: "+44 7438 186906",
      public_email: "hello@example.test",
    });
    expect(
      renderTemplate(
        "Hi {{business_name}} in {{location}}, call {{phone_number}} or email {{public_email}}.",
        lead,
      ),
    ).toBe("Hi Example Cakes in Luton, call +44 7438 186906 or email hello@example.test.");
  });

  it("substitutes missing optional fields with an empty string", () => {
    const lead = buildLead({ phone_number: null });
    expect(renderTemplate("Call {{phone_number}}.", lead)).toBe("Call .");
  });

  it("leaves unknown placeholders untouched", () => {
    const lead = buildLead();
    expect(renderTemplate("Hi {{unknown_token}}.", lead)).toBe("Hi {{unknown_token}}.");
  });

  it("substitutes {{products}} with one product per line, including pricing when set", () => {
    const lead = buildLead();
    const products = [
      buildProduct({ id: "p1", name: "Personalised Cake Topper", pricing_guidance: "£12.50" }),
      buildProduct({ id: "p2", name: "Cake Charm", pricing_guidance: null }),
    ];
    expect(renderTemplate("Take a look:\n{{products}}", lead, products)).toBe(
      "Take a look:\nPersonalised Cake Topper — £12.50\nCake Charm",
    );
  });

  it("substitutes {{products}} with an empty string when no products are supplied", () => {
    const lead = buildLead();
    expect(renderTemplate("Take a look:\n{{products}}", lead)).toBe("Take a look:\n");
  });
});

describe("instagramHandleFor", () => {
  it("returns the normalized handle from the lead's Instagram identity", () => {
    const lead = buildLead({
      social_identities: [
        {
          id: "identity-1",
          platform: "instagram",
          profile_url: "https://www.instagram.com/examplecakes",
          normalized_handle: "examplecakes",
          source_url: null,
          classification: "user_observed",
          collected_at: "2026-01-01T00:00:00Z",
        },
      ],
    });
    expect(instagramHandleFor(lead)).toBe("examplecakes");
  });

  it("returns null when the lead has no Instagram identity", () => {
    expect(instagramHandleFor(buildLead())).toBeNull();
  });
});

describe("whatsappUrl", () => {
  it("converts a UK local number to international format with no leading 0", () => {
    expect(whatsappUrl("07438 186906", "Hello")).toBe("https://wa.me/447438186906?text=Hello");
  });

  it("strips formatting from an already-international number", () => {
    expect(whatsappUrl("+44 7438 186906", "Hi there")).toBe(
      "https://wa.me/447438186906?text=Hi%20there",
    );
  });

  it("returns null when there is no phone number", () => {
    expect(whatsappUrl(null, "Hello")).toBeNull();
  });
});

describe("mailtoUrl", () => {
  it("builds a mailto link with an encoded subject and body", () => {
    expect(mailtoUrl("hello@example.test", "Hi there", "Line one")).toBe(
      "mailto:hello@example.test?subject=Hi%20there&body=Line%20one",
    );
  });

  it("returns null when there is no email address", () => {
    expect(mailtoUrl(null, "Subject", "Body")).toBeNull();
  });
});

describe("instagramDmUrl", () => {
  it("builds an ig.me deep link for the handle", () => {
    expect(instagramDmUrl("examplecakes")).toBe("https://ig.me/m/examplecakes");
  });

  it("returns null when there is no handle", () => {
    expect(instagramDmUrl(null)).toBeNull();
  });
});
