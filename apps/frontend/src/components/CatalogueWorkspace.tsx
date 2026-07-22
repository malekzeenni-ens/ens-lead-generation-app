import {
  FileSpreadsheet,
  Layers,
  PackagePlus,
  Save,
  Search,
  SlidersHorizontal,
  Upload,
} from "lucide-react";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import type { ProductInput } from "../api";
import { humanize } from "../domain";
import { usePagination } from "../pagination";
import type {
  Product,
  ProductFamily,
  ScoringProfile,
  ScoringWeights,
  ShopifyImportResult,
} from "../types";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import {
  DangerConfirm,
  EmptyState,
  LoadingState,
  PageHeader,
  Pagination,
  SectionHeading,
  TaskPanel,
  TaskTabs,
} from "./DesignSystem";

interface CatalogueWorkspaceProps {
  products: Product[];
  scoringProfile: ScoringProfile | null;
  productFamilies: ProductFamily[];
}

interface ProductPickerFieldsProps {
  products: Product[];
  selectedIds: Set<string>;
}

/**
 * Shared searchable checkbox list used by both the create and edit
 * product-family forms. Every product's checkbox stays mounted at all times
 * — the search only toggles visibility — so switching search terms never
 * drops a previously-checked product that no longer matches the new query.
 */
function ProductPickerFields({ products, selectedIds }: ProductPickerFieldsProps) {
  const [query, setQuery] = useState("");
  const search = query.toLocaleLowerCase();
  const matches = (product: Product) =>
    [product.name, product.category].join(" ").toLocaleLowerCase().includes(search);
  const visibleCount = products.filter(matches).length;

  return (
    <label>
      Products
      <input
        type="text"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search products to add"
      />
      <div className="product-picker">
        {visibleCount === 0 ? (
          <p className="supporting-copy">No products match this search.</p>
        ) : null}
        {products.map((product) => (
          <label key={product.id} className="checkbox-row" hidden={!matches(product)}>
            <input
              type="checkbox"
              name="product_ids"
              value={product.id}
              defaultChecked={selectedIds.has(product.id)}
            />
            <span>
              {product.name}
              <small>{product.category}</small>
            </span>
          </label>
        ))}
      </div>
    </label>
  );
}

const WEIGHT_KEYS: Array<keyof ScoringWeights> = [
  "business_relevance",
  "activity",
  "product_fit",
  "local_relevance",
  "commercial_potential",
  "reach_credibility",
  "contactability",
];

function value(form: FormData, name: string): string {
  const result = form.get(name);
  return typeof result === "string" ? result.trim() : "";
}

function list(valueToSplit: string): string[] {
  return valueToSplit
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function productFromForm(form: FormData): ProductInput {
  return {
    name: value(form, "name"),
    category: value(form, "category"),
    description: value(form, "description"),
    target_segments: list(value(form, "segments")),
    example_use_cases: list(value(form, "use-cases")),
    image_reference: value(form, "image-reference") || null,
    pricing_guidance: value(form, "pricing-guidance") || null,
    active: form.get("active") === "on",
    sample_eligible: form.get("sample-eligible") === "on",
  };
}

function productFamilyFromForm(form: FormData): {
  name: string;
  description: string | null;
  product_ids: string[];
} {
  return {
    name: value(form, "family-name"),
    description: value(form, "family-description") || null,
    product_ids: form.getAll("product_ids").map(String),
  };
}

function readFileText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.addEventListener("load", () => {
      if (typeof reader.result === "string") resolve(reader.result);
      else reject(new Error("The selected CSV could not be read as text."));
    });
    reader.addEventListener("error", () => reject(new Error("The selected CSV could not be read.")));
    reader.readAsText(file);
  });
}

export function CatalogueWorkspace({
  products,
  scoringProfile,
  productFamilies,
}: CatalogueWorkspaceProps) {
  const {
    loading,
    busy,
    importShopifyCsv: onImport,
    createProduct: onCreate,
    updateProduct: onUpdate,
    updateScoringProfile: onUpdateProfile,
    createProductFamily: onCreateFamily,
    updateProductFamily: onUpdateFamily,
    deleteProductFamily: onDeleteFamily,
  } = useWorkspaceActions();
  const [activeTask, setActiveTask] = useState("products");
  const [query, setQuery] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<ShopifyImportResult | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const weightFormRef = useRef<HTMLFormElement>(null);
  const [weightTotal, setWeightTotal] = useState(0);

  useEffect(() => {
    setWeightTotal(
      WEIGHT_KEYS.reduce((sum, key) => sum + (scoringProfile?.weights[key] ?? 0), 0),
    );
  }, [scoringProfile]);

  function recomputeWeightTotal(): void {
    if (!weightFormRef.current) return;
    const form = new FormData(weightFormRef.current);
    setWeightTotal(WEIGHT_KEYS.reduce((sum, key) => sum + (Number(value(form, key)) || 0), 0));
  }
  const filtered = useMemo(() => {
    const search = query.toLocaleLowerCase();
    return products.filter((product) =>
      [product.name, product.category, product.shopify_handle ?? ""]
        .join(" ")
        .toLocaleLowerCase()
        .includes(search),
    );
  }, [products, query]);
  const productPages = usePagination(filtered, 8, query);
  const issuePages = usePagination(
    importResult?.issues ?? [],
    5,
    importResult
      ? `${importResult.filename}-${importResult.products_created}-${importResult.products_updated}`
      : "",
  );

  async function submitImport(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!selectedFile) return;
    if (selectedFile.size > 5_000_000) {
      setFileError("Choose a Shopify CSV smaller than 5 MB.");
      return;
    }
    setFileError(null);
    try {
      const result = await onImport(selectedFile.name, await readFileText(selectedFile));
      if (result) setImportResult(result);
    } catch (error) {
      setFileError(error instanceof Error ? error.message : "The selected CSV could not be read.");
    }
  }

  async function submitProduct(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const formElement = event.currentTarget;
    if (await onCreate(productFromForm(new FormData(formElement)))) {
      formElement.reset();
      setActiveTask("products");
    }
  }

  async function submitProfile(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const weights = Object.fromEntries(
      WEIGHT_KEYS.map((key) => [key, Number(value(form, key))]),
    ) as unknown as ScoringWeights;
    await onUpdateProfile(value(form, "profile-name"), weights);
  }

  async function submitFamily(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const formElement = event.currentTarget;
    if (await onCreateFamily(productFamilyFromForm(new FormData(formElement)))) {
      formElement.reset();
    }
  }

  return (
    <>
      <PageHeader
        eyebrow="Product matching"
        title="Catalogue and scoring"
        description="Import Shopify listings, refine matching metadata and version the transparent bakery scoring model. No Shopify API connection or external sync is used."
      />

      <TaskTabs
        id="catalogue-tasks"
        label="Catalogue tasks"
        activeId={activeTask}
        onChange={setActiveTask}
        items={[
          { id: "products", label: "Products", count: products.length },
          { id: "create", label: "Add product" },
          { id: "import", label: "Import catalogue" },
          { id: "scoring", label: "Scoring model", count: scoringProfile?.version },
          { id: "families", label: "Product families", count: productFamilies.length },
        ]}
      />

      {activeTask === "create" ? (
        <TaskPanel id="catalogue-tasks" tabId="create">
          <section className="workspace-section" aria-labelledby="add-product-heading">
            <SectionHeading
              id="add-product-heading"
              eyebrow="Manual catalogue entry"
              title="Add product"
              description="Create one local product without opening the Shopify import workflow."
              icon={PackagePlus}
            />
            <form
              className="stacked-form form-panel--bounded"
              onSubmit={(event) => void submitProduct(event)}
            >
              <div className="field-pair">
                <label>Product name<input name="name" required /></label>
                <label>Category<input name="category" required /></label>
              </div>
              <label>Description <span className="optional-label">Optional</span><textarea name="description" /></label>
              <div className="field-pair">
                <label>Target segments <span className="optional-label">Optional</span><input name="segments" placeholder="Comma separated" /></label>
                <label>Use cases <span className="optional-label">Optional</span><input name="use-cases" placeholder="Comma separated" /></label>
              </div>
              <div className="field-pair">
                <label>Image reference <span className="optional-label">Optional</span><input name="image-reference" /></label>
                <label>Pricing guidance <span className="optional-label">Optional</span><input name="pricing-guidance" /></label>
              </div>
              <label className="checkbox-row"><input name="active" type="checkbox" defaultChecked /> Active</label>
              <label className="checkbox-row"><input name="sample-eligible" type="checkbox" /> Sample eligible</label>
              <button className="primary-action" type="submit" disabled={busy}>
                <PackagePlus size={17} aria-hidden="true" /> Add product
              </button>
            </form>
          </section>
        </TaskPanel>
      ) : null}

      {activeTask === "import" ? (
        <TaskPanel id="catalogue-tasks" tabId="import">
        <section className="workspace-section" aria-labelledby="shopify-import-heading">
          <SectionHeading
            id="shopify-import-heading"
            eyebrow="Local CSV ingress"
            title="Upload Shopify listing CSV"
            description="Products are grouped by Handle and upserted into the editable local catalogue."
            icon={FileSpreadsheet}
          />
          <form className="stacked-form" onSubmit={(event) => void submitImport(event)}>
            <label>
              Shopify product export
              <input
                type="file"
                accept=".csv,text/csv"
                required
                onChange={(event) => {
                  setSelectedFile(event.target.files?.[0] ?? null);
                  setFileError(null);
                  setImportResult(null);
                }}
              />
            </label>
            {selectedFile ? (
              <p className="form-hint" role="status">
                Ready: {selectedFile.name} ({Math.max(1, Math.round(selectedFile.size / 1024))} KB)
              </p>
            ) : null}
            <p className="form-hint">
              Maximum 5 MB / 10,000 rows. Standard Handle and Title columns are required. Optional
              tags: <code>segment:</code>, <code>use-case:</code> and <code>sample-eligible</code>.
            </p>
            {fileError ? <p className="field-error" role="alert">{fileError}</p> : null}
            <button className="primary-action" type="submit" disabled={busy || !selectedFile}>
              <Upload size={17} aria-hidden="true" />
              {busy ? "Importing catalogue…" : "Import locally"}
            </button>
          </form>
          {importResult ? (
            <div className="import-summary" role="status">
              <strong>Shopify CSV processed</strong>
              <p>
                {importResult.rows_read} rows · {importResult.products_created} created ·{" "}
                {importResult.products_updated} updated · {importResult.products_skipped} skipped
              </p>
              {issuePages.items.map((issue) => (
                <small key={`${issue.handle}-${issue.message}`}>
                  {issue.handle ?? "Unknown handle"}: {issue.message}
                </small>
              ))}
              <Pagination
                page={issuePages.page}
                pageCount={issuePages.pageCount}
                pageSize={issuePages.pageSize}
                totalItems={issuePages.totalItems}
                itemLabel="import issues"
                onPageChange={issuePages.setPage}
                compact
              />
            </div>
          ) : null}
        </section>
        </TaskPanel>
      ) : null}

      {activeTask === "scoring" ? (
        <TaskPanel id="catalogue-tasks" tabId="scoring">
        <section className="workspace-section" aria-labelledby="scoring-profile-heading">
          <SectionHeading
            id="scoring-profile-heading"
            eyebrow="Deterministic model"
            title="Bakery scoring weights"
            description="Saving creates a new immutable version; weights must total 100."
            icon={SlidersHorizontal}
            count={scoringProfile?.version}
          />
          {scoringProfile ? (
            <form
              ref={weightFormRef}
              className="stacked-form"
              onSubmit={(event) => void submitProfile(event)}
            >
              <label>
                Profile name
                <input name="profile-name" required defaultValue={scoringProfile.name} />
              </label>
              <div className="weight-grid">
                {WEIGHT_KEYS.map((key) => (
                  <label key={key}>
                    {humanize(key)}
                    <input
                      name={key}
                      type="number"
                      min="0"
                      max="100"
                      required
                      defaultValue={scoringProfile.weights[key]}
                      onChange={recomputeWeightTotal}
                    />
                  </label>
                ))}
              </div>
              <p
                className={weightTotal === 100 ? "form-hint" : "field-error"}
                role="status"
              >
                Current total: {weightTotal}/100
                {weightTotal === 100 ? "" : " — weights must total exactly 100 to save"}
              </p>
              <button className="secondary-action" type="submit" disabled={busy || weightTotal !== 100}>
                <Save size={17} aria-hidden="true" /> Save new scoring version
              </button>
            </form>
          ) : <LoadingState label="Loading scoring model" />}
        </section>
        </TaskPanel>
      ) : null}

      {activeTask === "families" ? (
        <TaskPanel id="catalogue-tasks" tabId="families">
        <section className="workspace-section" aria-labelledby="product-families-heading">
          <SectionHeading
            id="product-families-heading"
            eyebrow="Curated matching"
            title="Product families"
            description="Group specific products under a topic, then assign that family to a campaign so its leads are matched to exactly those products — no automatic guessing."
            icon={Layers}
            count={productFamilies.length}
          />
          <div className="form-panel form-panel--bounded">
            <div className="subsection-heading">
              <div>
                <h3>New product family</h3>
                <p>Pick the products this family should always match to.</p>
              </div>
              <span className="step-badge">01</span>
            </div>
            <form className="stacked-form" onSubmit={(event) => void submitFamily(event)}>
              <label>Family name<input name="family-name" required maxLength={200} placeholder="Gym signage range" /></label>
              <label>Description <span className="optional-label">Optional</span><textarea name="family-description" maxLength={2000} /></label>
              <ProductPickerFields products={products} selectedIds={new Set()} />
              <button className="primary-action" type="submit" disabled={busy}>
                <Layers size={17} aria-hidden="true" /> Create product family
              </button>
            </form>
          </div>

          {loading ? (
            <LoadingState label="Loading product families" />
          ) : productFamilies.length === 0 ? (
            <EmptyState
              title="No product families yet"
              description="Create one above, then select it from a campaign to replace automatic product matching for that campaign's leads."
            />
          ) : (
            <div className="catalogue-grid">
              {productFamilies.map((family) => (
                <article className="catalogue-card" key={family.id}>
                  <div className="records-heading">
                    <div>
                      <h3>{family.name}</h3>
                      <p>{family.products.length} product{family.products.length === 1 ? "" : "s"}</p>
                    </div>
                  </div>
                  <p>{family.description || "No description supplied."}</p>
                  <div className="lead-source-list">
                    {family.products.map((product) => (
                      <span className="status-badge" key={product.id}>{product.name}</span>
                    ))}
                  </div>
                  <details>
                    <summary>Edit family</summary>
                    <form
                      className="stacked-form compact-form"
                      onSubmit={(event) => {
                        event.preventDefault();
                        void onUpdateFamily(
                          family.id,
                          productFamilyFromForm(new FormData(event.currentTarget)),
                        );
                      }}
                    >
                      <label>Name<input name="family-name" required defaultValue={family.name} /></label>
                      <label>Description<textarea name="family-description" defaultValue={family.description ?? ""} /></label>
                      <ProductPickerFields
                        products={products}
                        selectedIds={new Set(family.products.map((product) => product.id))}
                      />
                      <button className="secondary-action" type="submit" disabled={busy}>
                        <Save size={16} aria-hidden="true" /> Save family
                      </button>
                    </form>
                  </details>
                  <DangerConfirm
                    intensity="two-step"
                    label="Delete"
                    disabled={busy}
                    onConfirm={() => void onDeleteFamily(family.id)}
                  />
                </article>
              ))}
            </div>
          )}
        </section>
        </TaskPanel>
      ) : null}

      {activeTask === "products" ? (
      <TaskPanel id="catalogue-tasks" tabId="products">
      <section className="workspace-section" aria-labelledby="catalogue-heading">
        <SectionHeading
          id="catalogue-heading"
          eyebrow="Local catalogue"
          title="Products and matching metadata"
          description="Shopify fields remain editable after import. Inactive products never match leads."
          icon={PackagePlus}
          count={products.length}
        />
        <div className="filter-bar">
          <label className="search-control">
            <Search size={16} aria-hidden="true" />
            <span className="visually-hidden">Search catalogue</span>
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search products or categories"
            />
          </label>
        </div>
        {loading ? (
          <LoadingState label="Loading product catalogue" />
        ) : filtered.length === 0 ? (
          <EmptyState
            title="No catalogue products"
            description="Upload a Shopify product export or add the first product manually."
          />
        ) : (
          <>
            <div className="catalogue-grid">
            {productPages.items.map((product) => (
              <article className="catalogue-card" key={product.id}>
                <div className="records-heading">
                  <div>
                    <h3>{product.name}</h3>
                    <p>{product.category} · {product.source === "shopify_csv" ? "Shopify CSV" : "Manual"}</p>
                  </div>
                  <span className={`status-badge${product.active ? " status-badge--success" : ""}`}>
                    {product.active ? "Active" : "Inactive"}
                  </span>
                </div>
                <p>{product.description || "No description supplied."}</p>
                <dl className="record-details">
                  <div><dt>Pricing</dt><dd>{product.pricing_guidance ?? "Not set"}</dd></div>
                  <div><dt>Variants</dt><dd>{product.variant_count}</dd></div>
                  <div><dt>Segments</dt><dd>{product.target_segments.join(", ") || "Not set"}</dd></div>
                  <div><dt>Sample</dt><dd>{product.sample_eligible ? "Eligible" : "Not eligible"}</dd></div>
                </dl>
                <details>
                  <summary>Edit product</summary>
                  <form
                    className="stacked-form compact-form"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void onUpdate(product.id, productFromForm(new FormData(event.currentTarget)));
                    }}
                  >
                    <label>Name<input name="name" required defaultValue={product.name} /></label>
                    <label>Category<input name="category" required defaultValue={product.category} /></label>
                    <label>Description<textarea name="description" defaultValue={product.description} /></label>
                    <label>Target segments<input name="segments" defaultValue={product.target_segments.join(", ")} /></label>
                    <label>Use cases<input name="use-cases" defaultValue={product.example_use_cases.join(", ")} /></label>
                    <label>Image reference<input name="image-reference" defaultValue={product.image_reference ?? ""} /></label>
                    <label>Pricing guidance<input name="pricing-guidance" defaultValue={product.pricing_guidance ?? ""} /></label>
                    <label className="checkbox-row"><input name="active" type="checkbox" defaultChecked={product.active} /> Active</label>
                    <label className="checkbox-row"><input name="sample-eligible" type="checkbox" defaultChecked={product.sample_eligible} /> Sample eligible</label>
                    <button className="secondary-action" type="submit" disabled={busy}>
                      <Save size={16} aria-hidden="true" /> Save product
                    </button>
                  </form>
                </details>
              </article>
            ))}
            </div>
            <Pagination
              page={productPages.page}
              pageCount={productPages.pageCount}
              pageSize={productPages.pageSize}
              totalItems={productPages.totalItems}
              itemLabel="products"
              onPageChange={productPages.setPage}
            />
          </>
        )}
      </section>
      </TaskPanel>
      ) : null}
    </>
  );
}
