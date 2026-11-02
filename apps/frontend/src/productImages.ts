/** Only Shopify-hosted images are loaded; imported image references can also be local text. */
export function productImageUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && (url.hostname === "cdn.shopify.com" || url.hostname.endsWith(".shopify.com"))
      ? url.href : null;
  } catch { return null; }
}
