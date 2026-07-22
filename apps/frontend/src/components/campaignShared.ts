export const DEFAULT_PRODUCT_CATEGORIES = [
  "Cake toppers",
  "Cake charms",
  "Bakery branding accessories",
];

export function formValue(form: FormData, name: string): string {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

export function formList(form: FormData, name: string): string[] {
  const unique = new Map<string, string>();
  for (const item of formValue(form, name).split(/[\n,]/)) {
    const cleaned = item.trim();
    const key = cleaned.toLocaleLowerCase();
    if (cleaned && !unique.has(key)) unique.set(key, cleaned);
  }
  return [...unique.values()];
}

export function hashtagValue(value: string): string {
  return [...value.toLocaleLowerCase()]
    .filter((character) => /[a-z0-9_]/u.test(character))
    .join("");
}

export async function pasteFromClipboard(): Promise<string | null> {
  try {
    const text = await navigator.clipboard?.readText();
    return text?.trim() || null;
  } catch {
    return null;
  }
}

export function runProviderLabel(trigger: string): string {
  if (trigger.endsWith("_google_places")) return "Google Places";
  if (trigger.endsWith("_instagram")) return "Instagram";
  if (trigger.endsWith("_public_registries")) return "Public registries";
  if (trigger.endsWith("_scoring")) return "Scoring only";
  return "Legacy combined run";
}
