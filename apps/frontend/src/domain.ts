import type { FollowUp, Lead } from "./types";

export type WorkspaceSection =
  | "overview"
  | "campaigns"
  | "leads"
  | "catalogue"
  | "templates"
  | "shortlist"
  | "pipeline"
  | "settings";

export const BAKERY_SEGMENT = "Bakeries and home bakers";

export function mondayIso(): string {
  const selected = new Date();
  const day = selected.getDay() || 7;
  selected.setDate(selected.getDate() - day + 1);
  const local = new Date(selected.getTime() - selected.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

export const PIPELINE_STAGES = [
  "new",
  "researching",
  "qualified",
  "recommended_this_week",
  "ready_to_contact",
  "contacted",
  "follow_up_due",
  "replied",
  "mock_up_requested",
  "sample_consideration",
  "quote_requested",
  "quote_sent",
  "negotiating",
  "won",
  "lost",
  "not_suitable",
  "do_not_contact",
] as const;

export const PIPELINE_GROUPS = [
  {
    label: "Prospecting",
    stages: ["new", "researching", "qualified", "recommended_this_week"],
  },
  {
    label: "Contact",
    stages: ["ready_to_contact", "contacted", "follow_up_due"],
  },
  {
    label: "Engaged",
    stages: [
      "replied",
      "mock_up_requested",
      "sample_consideration",
      "quote_requested",
      "quote_sent",
      "negotiating",
    ],
  },
  { label: "Closed", stages: ["won", "lost", "not_suitable", "do_not_contact"] },
] as const;

export function humanize(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function classificationLabel(value: string): string {
  const labels: Record<string, string> = {
    unknown: "Review required",
    corporate_subscriber: "Corporate",
    sole_trader_or_individual: "Sole trader / individual",
    partnership_individual_treatment: "Partnership review",
  };
  return labels[value] ?? humanize(value);
}

export function formatDate(value: string | null): string {
  if (!value) return "Not set";
  const source = value.length === 10 ? `${value}T00:00:00` : value;
  return new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(new Date(source));
}

export function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function formatCurrency(value: number | null): string {
  if (value === null) return "Not set";
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    maximumFractionDigits: 0,
  }).format(value);
}

export function todayIso(): string {
  const now = new Date();
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 10);
}

export function openFollowUps(leads: Lead[]): Array<{ lead: Lead; followUp: FollowUp }> {
  return leads
    .flatMap((lead) =>
      lead.follow_ups
        .filter((followUp) => followUp.status === "open")
        .map((followUp) => ({ lead, followUp })),
    )
    .sort((left, right) => left.followUp.due_date.localeCompare(right.followUp.due_date));
}
