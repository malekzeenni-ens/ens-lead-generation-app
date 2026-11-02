import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Product } from "../types";
import { CatalogueWorkspace } from "./CatalogueWorkspace";

vi.mock("../WorkspaceActionsContext", () => ({ useWorkspaceActions: () => ({ loading: false, busy: false }) }));
vi.mock("../api", () => ({ api: { shopifyConnection: () => Promise.resolve({ configured: true }) } }));

const product: Product = {
  id: "sign", shopify_handle: "acrylic-sign", name: "Custom acrylic sign", category: "Business signs",
  description: "A made-to-order sign.\n\nThe full description ends with installation instructions.",
  summary: "Made for your reception.", target_segments: ["Offices"], example_use_cases: ["Reception"],
  image_reference: "https://cdn.shopify.com/sign.jpg", active: true, pricing_guidance: "£17.00 to £39.00",
  sample_eligible: false, source: "shopify_csv", variant_count: 2, materials: ["Acrylic"], occasions: [],
  product_url: "https://etchnshine.com/products/acrylic-sign", b2b_relevant: true, bulk_ready: true,
  b2b_notes: "Matching signs for every room.", custom_options: "Your logo", enrichment_source: "seed",
  stale_enrichment: false, last_seen_import_at: "2026-11-02T20:00:00Z", created_at: "2026-11-02", updated_at: "2026-11-02",
  shopify_details: {
    vendor: "Etch N Shine", product_type: "Signage", status: "active", tags: ["Office"], image_urls: [],
    description: "A made-to-order sign.\n\nThe full description ends with installation instructions.", seo_description: "Signs for business.",
    variants: [
      { legacy_resource_id: "1", title: "Black / Small", sku: "SIGN-B-S", price: "17.00", selected_options: { Colour: "Black", Size: "Small" }, image_url: "", inventory_tracked: true, inventory_quantity: 8 },
      { legacy_resource_id: "2", title: "White / Large", sku: "SIGN-W-L", price: "39.00", selected_options: { Colour: "White", Size: "Large" }, image_url: "", inventory_tracked: false, inventory_quantity: 0 },
    ],
  },
};

function catalogue(readOnly = false, item = product) {
  return <CatalogueWorkspace products={[item]} scoringProfile={null} productFamilies={[]} enrichmentStatus={null} knowledgeNotes={[]} provenFits={[]} readOnly={readOnly} />;
}

describe("Catalogue product details", () => {
  it.each([false, true])("opens the complete description and variant details (phone: %s)", async (phone) => {
    const user = userEvent.setup();
    render(catalogue(phone));
    await user.click(screen.getByRole("button", { name: "View details" }));
    const drawer = screen.getByRole("dialog", { name: product.name });
    expect(within(drawer).getByText(/The full description ends with installation instructions/)).toBeVisible();
    expect(within(drawer).getByText("Etch N Shine")).toBeVisible();
    expect(within(drawer).getByText("SIGN-B-S")).toBeVisible();
    expect(within(drawer).getByText("8 in stock")).toBeVisible();
    expect(within(drawer).getByText("Stock not tracked")).toBeVisible();
    expect(within(drawer).getByText("£39.00")).toBeVisible();
    if (phone) expect(within(drawer).queryByRole("button", { name: "Edit product" })).not.toBeInTheDocument();
    await user.type(within(drawer).getByRole("searchbox", { name: "Find a variant" }), "SIGN-W");
    expect(within(drawer).queryByText("SIGN-B-S")).not.toBeInTheDocument();
    expect(within(drawer).getByText("SIGN-W-L")).toBeVisible();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "View details" })).toHaveFocus();
  });

  it("opens product details from a category on a phone", async () => {
    const user = userEvent.setup();
    render(catalogue(true));
    await user.click(screen.getByRole("button", { name: /By category/ }));
    await user.click(screen.getByRole("button", { name: /Business signs/ }));
    await user.click(screen.getByRole("button", { name: product.name }));
    expect(screen.getByRole("dialog", { name: product.name })).toBeVisible();
    expect(screen.getByText("SIGN-W-L")).toBeVisible();
  });

  it("explains how to load missing variant data instead of implying there are none", async () => {
    const user = userEvent.setup();
    render(catalogue(true, { ...product, shopify_details: null }));
    await user.click(screen.getByRole("button", { name: "View details" }));
    expect(screen.getByText(/Sync from Shopify on your PC/)).toBeVisible();
    expect(screen.getByText(/The full description ends with installation instructions/)).toBeVisible();
  });
});
