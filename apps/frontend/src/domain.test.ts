import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  classificationLabel,
  formatCurrency,
  formatDate,
  formatDateTime,
  humanize,
  mondayIso,
  openFollowUps,
  todayIso,
} from "./domain";
import type { FollowUp, Lead } from "./types";

function buildLead(overrides: Partial<Lead> = {}): Lead {
  return {
    id: "lead-1",
    business_name: "Example Cakes",
    segment: "Bakeries and home bakers",
    location: "Luton",
    website: null,
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

function buildFollowUp(overrides: Partial<FollowUp> = {}): FollowUp {
  return {
    id: "follow-up-1",
    follow_up_type: "call",
    due_date: "2026-01-10",
    status: "open",
    notes: null,
    completed_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("humanize", () => {
  it("replaces underscores with spaces and capitalizes each word", () => {
    expect(humanize("recommended_this_week")).toBe("Recommended This Week");
  });
});

describe("classificationLabel", () => {
  it("returns the known label for a mapped classification", () => {
    expect(classificationLabel("corporate_subscriber")).toBe("Corporate");
  });

  it("falls back to a humanized label for an unmapped classification", () => {
    expect(classificationLabel("some_new_classification")).toBe("Some New Classification");
  });
});

describe("formatDate", () => {
  it("returns 'Not set' for a null value", () => {
    expect(formatDate(null)).toBe("Not set");
  });

  it("formats a date-only (10 char) value", () => {
    expect(formatDate("2026-03-05")).toBe("5 Mar 2026");
  });

  it("formats a full ISO datetime value", () => {
    expect(formatDate("2026-03-05T12:30:00Z")).toBe("5 Mar 2026");
  });
});

describe("formatDateTime", () => {
  it("formats a date and time", () => {
    expect(formatDateTime("2026-03-05T12:30:00Z")).toContain("2026");
  });
});

describe("formatCurrency", () => {
  it("returns 'Not set' for a null value", () => {
    expect(formatCurrency(null)).toBe("Not set");
  });

  it("formats a number as GBP with no decimal places", () => {
    expect(formatCurrency(1500)).toBe("£1,500");
  });

  it("formats zero as GBP", () => {
    expect(formatCurrency(0)).toBe("£0");
  });
});

describe("todayIso and mondayIso", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("todayIso returns the local date in YYYY-MM-DD form", () => {
    vi.setSystemTime(new Date("2026-03-05T10:00:00Z"));
    expect(todayIso()).toBe("2026-03-05");
  });

  it("mondayIso returns the same day when today is already Monday", () => {
    vi.setSystemTime(new Date("2026-03-02T10:00:00Z"));
    expect(mondayIso()).toBe("2026-03-02");
  });

  it("mondayIso rolls back to the preceding Monday mid-week", () => {
    vi.setSystemTime(new Date("2026-03-05T10:00:00Z"));
    expect(mondayIso()).toBe("2026-03-02");
  });

  it("mondayIso rolls back across a week boundary on Sunday", () => {
    vi.setSystemTime(new Date("2026-03-08T10:00:00Z"));
    expect(mondayIso()).toBe("2026-03-02");
  });
});

describe("openFollowUps", () => {
  it("includes only open follow-ups across all leads", () => {
    const leadA = buildLead({
      id: "lead-a",
      follow_ups: [
        buildFollowUp({ id: "fu-open", status: "open", due_date: "2026-03-10" }),
        buildFollowUp({ id: "fu-done", status: "completed", due_date: "2026-03-01" }),
      ],
    });
    const leadB = buildLead({
      id: "lead-b",
      follow_ups: [buildFollowUp({ id: "fu-other-open", status: "open", due_date: "2026-03-05" })],
    });

    const result = openFollowUps([leadA, leadB]);

    expect(result.map((entry) => entry.followUp.id)).toEqual(["fu-other-open", "fu-open"]);
  });

  it("sorts open follow-ups by due date ascending", () => {
    const lead = buildLead({
      follow_ups: [
        buildFollowUp({ id: "fu-late", status: "open", due_date: "2026-05-01" }),
        buildFollowUp({ id: "fu-early", status: "open", due_date: "2026-01-01" }),
        buildFollowUp({ id: "fu-mid", status: "open", due_date: "2026-03-01" }),
      ],
    });

    const result = openFollowUps([lead]);

    expect(result.map((entry) => entry.followUp.id)).toEqual(["fu-early", "fu-mid", "fu-late"]);
  });

  it("returns an empty array when there are no open follow-ups", () => {
    const lead = buildLead({
      follow_ups: [buildFollowUp({ status: "completed" })],
    });

    expect(openFollowUps([lead])).toEqual([]);
  });
});
