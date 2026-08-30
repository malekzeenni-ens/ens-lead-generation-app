import {
  Download,
  FileText,
  Image as ImageIcon,
  Paperclip,
  Plus,
  Send,
  ShieldAlert,
  Sparkles,
  WandSparkles,
  X,
} from "lucide-react";
import { type ChangeEvent, type FormEvent, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "../api";
import type {
  AssistantAttachment,
  AssistantAttachmentInput,
  AssistantContextSelection,
  AssistantConversation,
  Campaign,
  CampaignDraft,
  Lead,
  OutreachBatch,
  Shortlist,
} from "../types";

interface GeneralAssistantPanelProps {
  ready: boolean;
  working: boolean;
  setWorking: (value: boolean) => void;
  onCampaignDraft: (draft: CampaignDraft) => void;
  campaigns: Campaign[];
  leads: Lead[];
  batches: OutreachBatch[];
  shortlists: Shortlist[];
  initialContext: AssistantContextSelection;
}

interface ContextOption extends AssistantContextSelection {
  label: string;
}

function contextValue(context: AssistantContextSelection): string {
  return `${context.kind}:${context.id ?? ""}`;
}

function contextSelection(value: string): AssistantContextSelection {
  const [kind, id] = value.split(":", 2);
  return {
    kind: kind as AssistantContextSelection["kind"],
    id: id || null,
  };
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.details.message;
  return error instanceof Error ? error.message : "The local assistant could not answer.";
}

async function fileInput(file: File): Promise<AssistantAttachmentInput> {
  const contentBase64 = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`Could not read ${file.name}.`));
    reader.onload = () => {
      const result = typeof reader.result === "string" ? reader.result : "";
      resolve(result.slice(result.indexOf(",") + 1));
    };
    reader.readAsDataURL(file);
  });
  return {
    filename: file.name,
    media_type: file.type || "application/octet-stream",
    content_base64: contentBase64,
  };
}

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function GeneralAssistantPanel({
  ready,
  working,
  setWorking,
  onCampaignDraft,
  campaigns,
  leads,
  batches,
  shortlists,
  initialContext,
}: GeneralAssistantPanelProps) {
  const initialContextKind = initialContext.kind;
  const initialContextId = initialContext.id;
  const [conversation, setConversation] = useState<AssistantConversation | null>(null);
  const [instruction, setInstruction] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [context, setContext] = useState<AssistantContextSelection>(initialContext);
  const contextOptions = useMemo<ContextOption[]>(
    () => [
      { kind: "workspace", id: null, label: "Whole workspace" },
      ...campaigns.map((campaign) => ({
        kind: "campaign" as const,
        id: campaign.id,
        label: `Campaign · ${campaign.name}`,
      })),
      ...leads.map((lead) => ({
        kind: "lead" as const,
        id: lead.id,
        label: `Lead · ${lead.business_name}`,
      })),
      ...batches.map((batch) => ({
        kind: "outreach_batch" as const,
        id: batch.id,
        label: `Email batch · ${batch.template_topic ?? batch.id.slice(0, 8)}`,
      })),
      ...shortlists.map((shortlist) => ({
        kind: "shortlist" as const,
        id: shortlist.id,
        label: `Shortlist · ${shortlist.campaign_name} · ${shortlist.week_start}`,
      })),
    ],
    [batches, campaigns, leads, shortlists],
  );
  const selectedContextLabel =
    contextOptions.find((option) => contextValue(option) === contextValue(context))?.label ??
    "Whole workspace";

  useEffect(() => {
    setContext({ kind: initialContextKind, id: initialContextId });
  }, [initialContextId, initialContextKind]);

  useEffect(() => {
    let active = true;
    void api
      .assistantConversations()
      .then((items) => {
        if (active) setConversation(items[0] ?? null);
      })
      .catch((caught: unknown) => {
        if (active) setError(errorMessage(caught));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  function chooseFiles(event: ChangeEvent<HTMLInputElement>): void {
    const selected = Array.from(event.target.files ?? []);
    event.target.value = "";
    const combined = [...files, ...selected].slice(0, 4);
    if (selected.some((file) => file.size > 5 * 1024 * 1024)) {
      setError("Each local attachment must be 5 MB or smaller.");
      return;
    }
    setFiles(combined);
    setError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    const content = instruction.trim();
    if (!content || working || !ready) return;
    setWorking(true);
    setError(null);
    try {
      const current = conversation ?? (await api.createAssistantConversation());
      const attachments = await Promise.all(files.map(fileInput));
      setConversation(await api.sendAssistantMessage(current.id, content, attachments, context));
      setInstruction("");
      setFiles([]);
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setWorking(false);
    }
  }

  async function prepareCampaign(): Promise<void> {
    if (!conversation || working || !ready) return;
    setWorking(true);
    setError(null);
    try {
      onCampaignDraft(await api.createCampaignDraftFromConversation(conversation.id));
    } catch (caught) {
      setError(errorMessage(caught));
    } finally {
      setWorking(false);
    }
  }

  async function download(attachment: AssistantAttachment): Promise<void> {
    try {
      const result = await api.downloadAssistantAttachment(attachment.download_url);
      const url = URL.createObjectURL(result.blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = result.filename;
      link.click();
      URL.revokeObjectURL(url);
    } catch (caught) {
      setError(errorMessage(caught));
    }
  }

  return (
    <section className="records-panel assistant-chat" aria-label="General local AI conversation">
      <div className="subsection-heading">
        <div>
          <h3>Ask about this app</h3>
          <p>Uses live local context from your campaigns, leads, catalogue and workflow.</p>
        </div>
        <div className="assistant-heading-actions">
          {conversation?.messages.length ? (
            <button
              className="tertiary-action"
              type="button"
              disabled={working}
              onClick={() => void prepareCampaign()}
            >
              <WandSparkles size={16} /> Prepare campaign
            </button>
          ) : null}
          <button
            className="tertiary-action"
            type="button"
            disabled={working}
            onClick={() => {
              setConversation(null);
              setFiles([]);
              setError(null);
            }}
          >
            <Plus size={16} /> New
          </button>
        </div>
      </div>

      {error ? (
        <div className="alert alert--error" role="alert">
          <ShieldAlert size={18} /> {error}
        </div>
      ) : null}

      <div className="assistant-context-bar">
        <label htmlFor="assistant-context">
          Context for the next answer
          <select
            id="assistant-context"
            value={contextValue(context)}
            disabled={working}
            onChange={(event) => setContext(contextSelection(event.target.value))}
          >
            <option value="workspace:">Whole workspace</option>
            {campaigns.length ? (
              <optgroup label="Campaigns">
                {campaigns.map((campaign) => (
                  <option key={campaign.id} value={`campaign:${campaign.id}`}>
                    {campaign.name}
                  </option>
                ))}
              </optgroup>
            ) : null}
            {leads.length ? (
              <optgroup label="Leads">
                {leads.map((lead) => (
                  <option key={lead.id} value={`lead:${lead.id}`}>
                    {lead.business_name}
                  </option>
                ))}
              </optgroup>
            ) : null}
            {batches.length ? (
              <optgroup label="Email draft batches">
                {batches.map((batch) => (
                  <option key={batch.id} value={`outreach_batch:${batch.id}`}>
                    {batch.template_topic ?? "Deleted template"} · {batch.drafts.length} drafts
                  </option>
                ))}
              </optgroup>
            ) : null}
            {shortlists.length ? (
              <optgroup label="Weekly shortlists">
                {shortlists.map((shortlist) => (
                  <option key={shortlist.id} value={`shortlist:${shortlist.id}`}>
                    {shortlist.campaign_name} · {shortlist.week_start}
                  </option>
                ))}
              </optgroup>
            ) : null}
          </select>
        </label>
        <p>
          <strong>{selectedContextLabel}</strong>
          {context.kind === "workspace"
            ? " — searches the bounded live workspace snapshot."
            : " — this exact record is primary; related workspace data is supporting context."}
        </p>
      </div>

      <div className="assistant-thread" aria-live="polite">
        {loading ? (
          <div className="assistant-thinking"><span /> Loading local conversation…</div>
        ) : !conversation?.messages.length ? (
          <div className="assistant-empty">
            <Sparkles size={22} aria-hidden="true" />
            <p>Ask about this workspace, request an app template, or plan your next lead action.</p>
            <div className="assistant-starter-prompts" aria-label="Suggested app questions">
              {[
                "What needs my attention today?",
                "What is the best next action?",
                "Summarise this context and flag missing information.",
              ].map((prompt) => (
                <button
                  key={prompt}
                  className="tertiary-action"
                  type="button"
                  onClick={() => setInstruction(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        ) : (
          conversation.messages.map((message) => (
            <div
              className={`assistant-message assistant-message--${message.role === "user" ? "user" : "model"}`}
              key={message.id}
            >
              <span>{message.role === "user" ? "You" : "Local assistant"}</span>
              <p className="assistant-message-content">{message.content}</p>
              {message.attachments.length ? (
                <div className="assistant-attachments">
                  {message.attachments.map((attachment) => (
                    <button
                      className="assistant-attachment"
                      type="button"
                      key={attachment.id}
                      onClick={() => void download(attachment)}
                    >
                      {attachment.media_type.startsWith("image/") ? (
                        <ImageIcon size={15} />
                      ) : (
                        <FileText size={15} />
                      )}
                      <span>{attachment.filename}</span>
                      <small>{formatSize(attachment.size_bytes)}</small>
                      <Download size={14} />
                    </button>
                  ))}
                </div>
              ) : null}
              {message.campaign_draft_suggested ? (
                <button
                  className="secondary-action assistant-inline-action"
                  type="button"
                  disabled={working}
                  onClick={() => void prepareCampaign()}
                >
                  <WandSparkles size={16} /> Prepare reviewable campaign draft
                </button>
              ) : null}
            </div>
          ))
        )}
        {working ? <div className="assistant-thinking"><span /> Working locally…</div> : null}
      </div>

      <form className="assistant-composer" onSubmit={(event) => void submit(event)}>
        {files.length ? (
          <div className="assistant-selected-files">
            {files.map((file, index) => (
              <span key={`${file.name}-${file.lastModified}`}>
                {file.name}
                <button
                  type="button"
                  aria-label={`Remove ${file.name}`}
                  onClick={() => setFiles(files.filter((_, itemIndex) => itemIndex !== index))}
                >
                  <X size={13} />
                </button>
              </span>
            ))}
          </div>
        ) : null}
        <label htmlFor="general-assistant-instruction" className="visually-hidden">
          Ask the local assistant
        </label>
        <textarea
          id="general-assistant-instruction"
          value={instruction}
          onChange={(event) => setInstruction(event.target.value)}
          rows={3}
          maxLength={8000}
          disabled={!ready || working}
          placeholder="Ask about your campaigns, leads, catalogue, drafts or next actions…"
        />
        <div className="assistant-composer-actions">
          <label className="tertiary-action assistant-file-picker">
            <Paperclip size={16} /> Attach
            <input
              type="file"
              multiple
              accept=".txt,.csv,.docx,.png,.jpg,.jpeg,text/plain,text/csv,image/png,image/jpeg"
              onChange={chooseFiles}
              disabled={!ready || working || files.length >= 4}
            />
          </label>
          <button
            className="primary-action"
            type="submit"
            disabled={!instruction.trim() || !ready || working}
          >
            <Send size={17} /> Send
          </button>
        </div>
        <small className="assistant-file-note">
          TXT, CSV and DOCX are readable locally. JPEG/PNG are stored, but Llama 3.2 3B cannot see images.
        </small>
      </form>
    </section>
  );
}
