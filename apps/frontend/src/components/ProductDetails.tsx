import { ExternalLink, ImageOff, Package } from "lucide-react";
import { useState } from "react";

import { formatDate, humanize } from "../domain";
import { openExternalUrl } from "../external";
import { productImageUrl } from "../productImages";
import type { Product } from "../types";
import { StatusPill } from "./DesignSystem";

export function ProductImage({ src, name }: { src: string | null; name: string }) {
  const [failed, setFailed] = useState(false);
  return src && !failed ? (
    <img src={src} alt={name} loading="lazy" referrerPolicy="no-referrer" onError={() => setFailed(true)} />
  ) : <span className="product-image-placeholder"><ImageOff size={26} aria-hidden="true" /><span>No image</span></span>;
}

export function ProductDetails({ product, readOnly }: { product: Product; readOnly: boolean }) {
  const shopify = product.shopify_details;
  const images = [...new Set([product.image_reference, ...(shopify?.image_urls ?? [])].map(productImageUrl).filter((url): url is string => !!url))];
  const [imageIndex, setImageIndex] = useState(0);
  const [variantQuery, setVariantQuery] = useState("");
  const [linkError, setLinkError] = useState("");
  const variants = shopify?.variants ?? [];
  const filtered = variants.filter((variant) => [variant.title, variant.sku, ...Object.values(variant.selected_options)].join(" ").toLocaleLowerCase().includes(variantQuery.toLocaleLowerCase()));
  const facts = [
    ["Vendor", shopify?.vendor], ["Product type", shopify?.product_type],
    ["Shopify status", shopify?.status ? humanize(shopify.status) : null],
    ["Handle", product.shopify_handle], ["Last imported", product.last_seen_import_at ? formatDate(product.last_seen_import_at) : null],
  ].filter(([, value]) => value);
  return <div className="product-detail">
    <div className="product-detail__overview">
      <div className="product-gallery">
        <div className="product-gallery__main"><ProductImage key={images[imageIndex]} src={images[imageIndex] ?? null} name={product.name} /></div>
        {images.length > 1 ? <div className="product-gallery__thumbnails" aria-label="Product images">
          {images.map((src, index) => <button type="button" key={src} aria-label={`Show image ${index + 1}`} aria-pressed={index === imageIndex} onClick={() => setImageIndex(index)}><img src={src} alt="" loading="lazy" /></button>)}
        </div> : null}
      </div>
      <div className="product-detail__summary">
        <StatusPill tone={product.active ? "success" : "neutral"}>{product.active ? "Active" : "Inactive"}</StatusPill>
        <p className="product-detail__category">{product.category}</p>
        <p className="product-detail__price">{product.pricing_guidance ?? "Price not supplied"}</p>
        <p className="supporting-copy">{product.variant_count} {product.variant_count === 1 ? "variant" : "variants"} · {product.source === "shopify_csv" ? "Shopify" : "Manually added"}</p>
        {product.summary ? <p>{product.summary}</p> : null}
        {product.product_url && /^https?:\/\//.test(product.product_url) ? <button type="button" className="secondary-action" onClick={() => { setLinkError(""); void openExternalUrl(product.product_url!).catch(() => setLinkError("The product link could not be opened. Please try again.")); }}><ExternalLink size={16} aria-hidden="true" /> View on store</button> : null}
        {linkError ? <p role="alert">{linkError}</p> : null}
      </div>
    </div>
    <section className="product-detail__section" aria-labelledby="product-description-heading">
      <h3 id="product-description-heading">Full description</h3>
      <p className="product-detail__description">{product.description || "No description supplied."}</p>
      {shopify?.description && shopify.description !== product.description ? <details><summary>Original Shopify description</summary><p className="product-detail__description">{shopify.description}</p></details> : null}
    </section>
    <section className="product-detail__section" aria-labelledby="product-variants-heading">
      <div className="product-detail__section-heading"><h3 id="product-variants-heading"><Package size={18} aria-hidden="true" /> Variants <span>{variants.length || product.variant_count}</span></h3></div>
      {variants.length ? <>
        <label className="product-variant-search">Find a variant<input type="search" value={variantQuery} onChange={(event) => setVariantQuery(event.target.value)} placeholder="Search options or SKU" /></label>
        <div className="product-variants">
          {filtered.map((variant, index) => <article className="product-variant" key={`${variant.legacy_resource_id}-${index}`}>
            <div className="product-variant__heading"><h4>{variant.title && variant.title !== "Default Title" ? variant.title : "Standard"}</h4><strong>{variant.price ? `£${Number(variant.price).toFixed(2)}` : "Price not supplied"}</strong></div>
            {Object.keys(variant.selected_options).length ? <dl className="product-facts">{Object.entries(variant.selected_options).map(([name, value]) => <div key={name}><dt>{name}</dt><dd>{value}</dd></div>)}</dl> : null}
            <div className="product-variant__meta"><span>SKU: <b>{variant.sku || "Not supplied"}</b></span><span>{variant.inventory_tracked === false ? "Stock not tracked" : variant.inventory_quantity !== null ? `${variant.inventory_quantity} in stock` : "Stock not supplied"}</span></div>
          </article>)}
          {!filtered.length ? <p className="supporting-copy">No variants match your search.</p> : null}
        </div>
        <p className="form-hint">Prices and stock reflect the last Shopify sync.</p>
      </> : <p className="product-detail__notice">Variant details have not been imported yet. {readOnly ? "Sync from Shopify on your PC, then refresh this page." : "Use Update from Shopify → Sync from Shopify to load options, SKUs, prices and stock."}</p>}
    </section>
    <section className="product-detail__section" aria-labelledby="product-listing-heading"><h3 id="product-listing-heading">Shopify listing</h3>
      {facts.length ? <dl className="product-facts">{facts.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl> : <p className="supporting-copy">This product has no Shopify listing details.</p>}
      {shopify?.tags.length ? <div className="product-tags" aria-label="Shopify tags">{shopify.tags.map((tag) => <span key={tag}>{tag}</span>)}</div> : null}
      {shopify?.seo_description ? <div className="product-detail__seo"><h4>SEO description</h4><p>{shopify.seo_description}</p></div> : null}
    </section>
    <section className="product-detail__section" aria-labelledby="product-sales-heading"><h3 id="product-sales-heading">Sales knowledge</h3>
      <dl className="product-facts">{[
        ["Business buyers", product.b2b_relevant ? (product.bulk_ready ? "Suits bulk runs" : "Suits business orders") : "Not specified"],
        ["Target segments", product.target_segments.join(", ")], ["Materials", product.materials.join(", ")],
        ["Occasions", product.occasions.join(", ")], ["Use cases", product.example_use_cases.join(", ")],
        ["Personalisation", product.custom_options], ["Business notes", product.b2b_notes],
        ["Samples", product.sample_eligible ? "Eligible" : "Not eligible"],
      ].filter(([, value]) => value).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>
    </section>
  </div>;
}
