import { ArrowRightLeft, CalendarClock, ShieldOff } from "lucide-react";
import { type DragEvent, type FormEvent, useState } from "react";

import { PIPELINE_GROUPS, formatDate, humanize } from "../domain";
import { useRememberedState } from "../remembered";
import type { Lead, ScoreRun } from "../types";
import { useWorkspaceActions } from "../WorkspaceActionsContext";
import { Drawer, StatusPill } from "./DesignSystem";

interface PipelineBoardProps {
  leads: Lead[];
  scores: ScoreRun[];
  onOpen: (leadId: string) => void;
  /** Phone: one stage group at a time, chosen from chips, and no dragging on touch. */
  stacked?: boolean;
}

/** Suppression is set from the lead's Privacy tab, never by moving a card. */
const MOVABLE_STAGES = PIPELINE_GROUPS.flatMap((group) =>
  group.stages.filter((stage) => stage !== "do_not_contact"),
);

function leadValue(lead: Lead): number | null {
  return lead.won_value ?? lead.quote_value ?? lead.estimated_order_value;
}

const money = new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });

function nextFollowUp(lead: Lead): string | null {
  const open = lead.follow_ups
    .filter((item) => item.status === "open")
    .map((item) => item.due_date)
    .sort();
  return open[0] ?? null;
}

interface PendingMove {
  lead: Lead;
  /** Stages offered: the dropped column's, or every stage from "Move to…". */
  stages: string[];
}

/** The pipeline as columns of cards. Moving a card uses the same stage change and rules as the lead's own form. */
export function PipelineBoard({ leads, scores, onOpen, stacked = false }: PipelineBoardProps) {
  const [chosenGroup, setChosenGroup] = useRememberedState<string>("pipeline:stage-group", "");
  const countFor = (stages: readonly string[]) =>
    leads.filter((lead) => stages.includes(lead.pipeline_stage)).length;
  // Until one is chosen, open on the first group that has leads in it.
  const shownGroup =
    PIPELINE_GROUPS.find((group) => group.label === chosenGroup)?.label ??
    PIPELINE_GROUPS.find((group) => countFor(group.stages) > 0)?.label ??
    PIPELINE_GROUPS[0]?.label;

  const { busy, changeLeadStage } = useWorkspaceActions();
  const [dragLeadId, setDragLeadId] = useState<string | null>(null);
  const [dropGroup, setDropGroup] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingMove | null>(null);
  const scoreByLead = new Map(scores.map((score) => [score.lead_id, score.final_score] as const));

  function handleDrop(event: DragEvent<HTMLElement>, stages: readonly string[]): void {
    event.preventDefault();
    setDropGroup(null);
    const lead = leads.find((item) => item.id === (dragLeadId ?? event.dataTransfer.getData("text/plain")));
    setDragLeadId(null);
    if (!lead || lead.suppressed) return;
    const offered = stages.filter((stage) => stage !== "do_not_contact" && stage !== lead.pipeline_stage);
    if (offered.length === 0) return;
    setPending({ lead, stages: offered });
  }

  async function confirmMove(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!pending) return;
    const form = new FormData(event.currentTarget);
    const stageValue = form.get("board-stage");
    const reasonValue = form.get("board-reason");
    const stage = typeof stageValue === "string" ? stageValue : "";
    const reason = typeof reasonValue === "string" ? reasonValue.trim() : "";
    if (!stage) return;
    const moved = await changeLeadStage(pending.lead.id, stage, reason || undefined);
    if (moved) setPending(null);
  }

  return (
    <>
      {stacked ? (
        <div className="stage-chips" role="group" aria-label="Pipeline stage">
          {PIPELINE_GROUPS.map((group) => (
            <button
              key={group.label}
              type="button"
              className="stage-chip"
              aria-pressed={shownGroup === group.label}
              onClick={() => setChosenGroup(group.label)}
            >
              {group.label}
              <span>{countFor(group.stages)}</span>
            </button>
          ))}
        </div>
      ) : null}
      <div className={`pipeline-board${stacked ? " pipeline-board--stacked" : ""}`} aria-label="Pipeline board">
        {PIPELINE_GROUPS.filter((group) => !stacked || group.label === shownGroup).map((group) => {
          const columnLeads = leads.filter((lead) =>
            (group.stages as readonly string[]).includes(lead.pipeline_stage),
          );
          return (
            <section
              key={group.label}
              className={`board-column${dropGroup === group.label ? " board-column--drop" : ""}`}
              aria-labelledby={`board-${group.label}`}
              onDragOver={(event) => {
                if (!dragLeadId) return;
                event.preventDefault();
                setDropGroup(group.label);
              }}
              onDragLeave={() => setDropGroup((current) => (current === group.label ? null : current))}
              onDrop={(event) => handleDrop(event, group.stages)}
            >
              <header className="board-column__header">
                <h3 id={`board-${group.label}`}>{group.label}</h3>
                <span className="board-column__count">{columnLeads.length}</span>
              </header>
              <div className="board-column__cards">
                {columnLeads.length === 0 ? (
                  <p className="board-column__empty">No leads here</p>
                ) : (
                  columnLeads.map((lead) => {
                    const score = scoreByLead.get(lead.id);
                    const due = nextFollowUp(lead);
                    const value = leadValue(lead);
                    return (
                      <article
                        key={lead.id}
                        className={`board-card${dragLeadId === lead.id ? " board-card--dragging" : ""}`}
                        draggable={!stacked && !lead.suppressed && !busy}
                        onDragStart={(event) => {
                          event.dataTransfer.setData("text/plain", lead.id);
                          event.dataTransfer.effectAllowed = "move";
                          setDragLeadId(lead.id);
                        }}
                        onDragEnd={() => {
                          setDragLeadId(null);
                          setDropGroup(null);
                        }}
                      >
                        <button type="button" className="board-card__open" onClick={() => onOpen(lead.id)}>
                          <strong>{lead.business_name}</strong>
                          <small>{lead.location}</small>
                        </button>
                        <div className="board-card__meta">
                          <StatusPill tone={lead.suppressed ? "warning" : "neutral"}>
                            {lead.suppressed ? "Do not contact" : humanize(lead.pipeline_stage)}
                          </StatusPill>
                          {score !== undefined ? <span className="board-card__score">{score}/100</span> : null}
                        </div>
                        <div className="board-card__footer">
                          <span>
                            <CalendarClock size={14} aria-hidden="true" />
                            {due ? formatDate(due) : "No follow-up"}
                          </span>
                          {value !== null ? <span>{money.format(value)}</span> : null}
                          {lead.suppressed ? (
                            <ShieldOff size={15} aria-label="Lift suppression in Privacy before moving" />
                          ) : (
                            <button
                              type="button"
                              className="icon-button board-card__move"
                              aria-label={`Move ${lead.business_name} to another stage`}
                              title="Move to…"
                              disabled={busy}
                              onClick={() =>
                                setPending({
                                  lead,
                                  stages: MOVABLE_STAGES.filter((stage) => stage !== lead.pipeline_stage),
                                })
                              }
                            >
                              <ArrowRightLeft size={15} aria-hidden="true" />
                            </button>
                          )}
                        </div>
                      </article>
                    );
                  })
                )}
              </div>
            </section>
          );
        })}
      </div>

      <Drawer
        open={pending !== null}
        title={pending ? `Move ${pending.lead.business_name}` : "Move lead"}
        description={pending ? `Now: ${humanize(pending.lead.pipeline_stage)}` : undefined}
        onClose={() => setPending(null)}
        footer={
          <>
            <button type="button" className="secondary-action" onClick={() => setPending(null)}>
              Cancel
            </button>
            <button type="submit" form="board-move-form" className="primary-action" disabled={busy}>
              Move lead
            </button>
          </>
        }
      >
        {pending ? (
          <form id="board-move-form" className="form-grid" onSubmit={(event) => void confirmMove(event)}>
            <label>
              New stage
              <select name="board-stage" defaultValue={pending.stages[0]} required>
                {pending.stages.map((stage) => (
                  <option key={stage} value={stage}>{humanize(stage)}</option>
                ))}
              </select>
            </label>
            <label>
              Reason <span className="optional-label">Optional</span>
              <input name="board-reason" maxLength={2000} />
            </label>
            <p className="supporting-copy">The change is recorded in the lead's history, the same as moving it from its own page.</p>
          </form>
        ) : null}
      </Drawer>
    </>
  );
}
