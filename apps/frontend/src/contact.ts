import type { Lead, Product } from "./types";

const TEMPLATE_TOKENS: Record<string, (lead: Lead) => string> = {
  business_name: (lead) => lead.business_name,
  location: (lead) => lead.location,
  segment: (lead) => lead.segment,
  phone_number: (lead) => lead.phone_number ?? "",
  public_email: (lead) => lead.public_email ?? "",
  website: (lead) => lead.website ?? "",
};

/** One line per product, e.g. "Personalised Cake Topper — £12.50", for the {{products}} token. */
export function productListText(products: Product[]): string {
  return products
    .map((product) =>
      product.pricing_guidance ? `${product.name} — ${product.pricing_guidance}` : product.name,
    )
    .join("\n");
}

/**
 * Substitutes {{token}} placeholders in a template subject/body. Lead-derived
 * tokens (business_name, location, ...) always resolve from `lead`; {{products}}
 * resolves from the caller-supplied list — typically every product across the
 * template's assigned product families — so it renders as a plain empty string
 * when the template has no families and the caller passes nothing.
 */
export function renderTemplate(text: string, lead: Lead, products: Product[] = []): string {
  return text.replaceAll(/\{\{\s*(\w+)\s*\}\}/g, (match, token: string) => {
    if (token === "products") return productListText(products);
    const resolve = TEMPLATE_TOKENS[token];
    return resolve ? resolve(lead) : match;
  });
}

export function instagramHandleFor(lead: Lead): string | null {
  return lead.social_identities.find((identity) => identity.platform === "instagram")
    ?.normalized_handle ?? null;
}

/** wa.me needs a full international number with no leading 0 or +; assumes UK local numbers. */
export function whatsappUrl(phoneNumber: string | null, message: string): string | null {
  if (!phoneNumber) return null;
  let digits = phoneNumber.replace(/\D/g, "");
  if (digits.startsWith("0")) digits = `44${digits.slice(1)}`;
  if (!digits) return null;
  return `https://wa.me/${digits}?text=${encodeURIComponent(message)}`;
}

export function mailtoUrl(email: string | null, subject: string, body: string): string | null {
  if (!email) return null;
  return `mailto:${email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
}

/**
 * Opens Instagram's direct-message thread with the given handle. Instagram has no
 * public way to pre-fill message text via URL (unlike WhatsApp/email), so only the
 * conversation opens — the rendered message still needs to be pasted in manually.
 */
export function instagramDmUrl(handle: string | null): string | null {
  if (!handle) return null;
  return `https://ig.me/m/${encodeURIComponent(handle)}`;
}
