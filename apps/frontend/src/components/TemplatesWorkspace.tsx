import { FileText, Save } from "lucide-react";
import { type FormEvent, useMemo, useState } from "react";

import type { TemplateInput } from "../api";
import { usePagination } from "../pagination";
import type { ProductFamily, Template } from "../types";
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

interface TemplatesWorkspaceProps {
  templates: Template[];
  productFamilies: ProductFamily[];
}

interface FamilyPickerFieldsProps {
  productFamilies: ProductFamily[];
  selectedIds: Set<string>;
}

/**
 * Searchable checkbox list of product families for a template. Every
 * family's checkbox stays mounted at all times — the search only toggles
 * visibility via `hidden` — so switching search terms never drops a
 * previously-checked family (the same fix applied to the catalogue's
 * product picker).
 */
function FamilyPickerFields({ productFamilies, selectedIds }: FamilyPickerFieldsProps) {
  const [query, setQuery] = useState("");
  const search = query.toLocaleLowerCase();
  const matches = (family: ProductFamily) => family.name.toLocaleLowerCase().includes(search);
  const visibleCount = productFamilies.filter(matches).length;

  if (productFamilies.length === 0) {
    return (
      <label>
        Product families <span className="optional-label">Optional</span>
        <p className="form-hint">
          No product families yet — add one in Catalogue → Product families to fill{" "}
          <code>{"{{products}}"}</code> with its products automatically.
        </p>
      </label>
    );
  }

  return (
    <label>
      Product families <span className="optional-label">Optional</span>
      <input
        type="text"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Search product families to include"
      />
      <div className="product-picker">
        {visibleCount === 0 ? (
          <p className="supporting-copy">No product families match this search.</p>
        ) : null}
        {productFamilies.map((family) => (
          <label key={family.id} className="checkbox-row" hidden={!matches(family)}>
            <input
              type="checkbox"
              name="product_family_ids"
              value={family.id}
              defaultChecked={selectedIds.has(family.id)}
            />
            <span>
              {family.name}
              <small>{family.products.length} product{family.products.length === 1 ? "" : "s"}</small>
            </span>
          </label>
        ))}
      </div>
      <small className="field-hint">
        Use <code>{"{{products}}"}</code> in the body to insert every product from the selected
        families as a list.
      </small>
    </label>
  );
}

function value(form: FormData, name: string): string {
  const result = form.get(name);
  return typeof result === "string" ? result.trim() : "";
}

function templateFromForm(form: FormData): TemplateInput {
  return {
    topic: value(form, "topic"),
    subject: value(form, "subject"),
    body: value(form, "body"),
    product_family_ids: form.getAll("product_family_ids").map(String),
  };
}

export function TemplatesWorkspace({ templates, productFamilies }: TemplatesWorkspaceProps) {
  const {
    loading,
    busy,
    createTemplate: onCreate,
    updateTemplate: onUpdate,
    deleteTemplate: onDelete,
  } = useWorkspaceActions();
  const [activeTask, setActiveTask] = useState("templates");
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const search = query.toLocaleLowerCase();
    return templates.filter((template) =>
      [template.topic, template.subject, template.body]
        .join(" ")
        .toLocaleLowerCase()
        .includes(search),
    );
  }, [templates, query]);
  const templatePages = usePagination(filtered, 8, query);

  async function submitTemplate(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const formElement = event.currentTarget;
    const saved = await onCreate(templateFromForm(new FormData(formElement)));
    if (saved) {
      formElement.reset();
      setActiveTask("templates");
    }
  }

  async function submitEdit(
    event: FormEvent<HTMLFormElement>,
    templateId: string,
  ): Promise<void> {
    event.preventDefault();
    await onUpdate(templateId, templateFromForm(new FormData(event.currentTarget)));
  }


  return (
    <>
      <PageHeader
        eyebrow="Outreach messaging"
        title="Message templates"
        description="Reusable topic, subject and body text for WhatsApp, email and Instagram messages. Templates never send anything automatically — a lead's Contact tab opens the message in the chosen app for you to review and send."
      />

      <TaskTabs
        id="template-tasks"
        label="Template tasks"
        activeId={activeTask}
        onChange={setActiveTask}
        items={[
          { id: "templates", label: "Templates", count: templates.length },
          { id: "create", label: "Add template" },
        ]}
      />

      {activeTask === "create" ? (
        <TaskPanel id="template-tasks" tabId="create">
          <section className="workspace-section" aria-labelledby="add-template-heading">
            <SectionHeading
              id="add-template-heading"
              eyebrow="New template"
              title="Add template"
              description="Use {{business_name}}, {{location}}, {{segment}}, {{phone_number}}, {{public_email}}, {{website}} or {{products}} as placeholders — they are filled in from the selected lead and its assigned product families."
              icon={FileText}
            />
            <form
              className="inline-editor form-panel--bounded"
              onSubmit={(event) => void submitTemplate(event)}
            >
              <label>Topic<input name="topic" required maxLength={200} placeholder="Follow-up" /></label>
              <label>
                Subject <span className="optional-label">(used for email)</span>
                <input name="subject" maxLength={300} placeholder="Following up, {{business_name}}" />
              </label>
              <label>
                Body
                <textarea
                  name="body"
                  required
                  maxLength={20_000}
                  rows={6}
                  placeholder="Hi {{business_name}}, checking in about your order."
                />
              </label>
              <FamilyPickerFields productFamilies={productFamilies} selectedIds={new Set()} />
              <button className="primary-action" type="submit" disabled={busy}>
                <FileText size={17} aria-hidden="true" /> Add template
              </button>
            </form>
          </section>
        </TaskPanel>
      ) : null}

      {activeTask === "templates" ? (
        <TaskPanel id="template-tasks" tabId="templates">
          <section className="workspace-section" aria-labelledby="templates-heading">
            <SectionHeading
              id="templates-heading"
              eyebrow="Local templates"
              title="Topic, subject and body"
              description="Edit or remove a template; changes apply the next time it is selected for a lead."
              icon={FileText}
              count={templates.length}
            />
            <div className="filter-bar">
              <label className="search-control">
                <span className="visually-hidden">Search templates</span>
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search templates"
                />
              </label>
            </div>
            {loading ? (
              <LoadingState label="Loading templates" />
            ) : filtered.length === 0 ? (
              <EmptyState
                title="No message templates"
                description="Add the first template to reuse it from a lead's Contact tab."
              />
            ) : (
              <>
                <div className="catalogue-grid">
                  {templatePages.items.map((template) => (
                    <article className="catalogue-card" key={template.id}>
                      <div className="records-heading">
                        <div>
                          <h3>{template.topic}</h3>
                          <p>{template.subject || "No subject set"}</p>
                        </div>
                      </div>
                      <p>{template.body}</p>
                      {template.product_family_ids.length > 0 ? (
                        <div className="lead-source-list">
                          {template.product_family_ids.map((familyId) => {
                            const family = productFamilies.find((item) => item.id === familyId);
                            return (
                              <span className="status-badge" key={familyId}>
                                {family?.name ?? "Family no longer exists"}
                              </span>
                            );
                          })}
                        </div>
                      ) : null}
                      <details>
                        <summary>Edit template</summary>
                        <form
                          className="stacked-form compact-form"
                          onSubmit={(event) => void submitEdit(event, template.id)}
                        >
                          <label>Topic<input name="topic" required defaultValue={template.topic} /></label>
                          <label>Subject<input name="subject" defaultValue={template.subject} /></label>
                          <label>Body<textarea name="body" required rows={5} defaultValue={template.body} /></label>
                          <FamilyPickerFields
                            productFamilies={productFamilies}
                            selectedIds={new Set(template.product_family_ids)}
                          />
                          <button className="secondary-action" type="submit" disabled={busy}>
                            <Save size={16} aria-hidden="true" /> Save template
                          </button>
                        </form>
                      </details>
                      <DangerConfirm
                        intensity="two-step"
                        label="Delete"
                        disabled={busy}
                        onConfirm={() => void onDelete(template.id)}
                      />
                    </article>
                  ))}
                </div>
                <Pagination
                  page={templatePages.page}
                  pageCount={templatePages.pageCount}
                  pageSize={templatePages.pageSize}
                  totalItems={templatePages.totalItems}
                  itemLabel="templates"
                  onPageChange={templatePages.setPage}
                />
              </>
            )}
          </section>
        </TaskPanel>
      ) : null}
    </>
  );
}
