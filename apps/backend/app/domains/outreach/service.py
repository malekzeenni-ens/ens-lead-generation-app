from __future__ import annotations

import hashlib
import re
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.models import (
    Communication,
    Lead,
    OutreachBatch,
    OutreachDraft,
    OutreachDraftRevision,
    Product,
    Template,
)
from app.domains.audit.repository import AuditRepository
from app.domains.audit.service import record_audit_event
from app.domains.campaigns.repository import CampaignRepository
from app.domains.catalogue.repository import CatalogueRepository
from app.domains.leads.identity import valid_public_email
from app.domains.leads.repository import LeadRepository
from app.domains.outreach.repository import OutreachRepository
from app.domains.outreach.schemas import (
    OutreachBatchCreate,
    OutreachBatchRead,
    OutreachDraftApproveMany,
    OutreachDraftEdit,
    OutreachDraftRead,
    OutreachDraftReject,
    OutreachDraftRevisionRead,
    OutreachLeadOptionRead,
    OutreachZohoHandoffRead,
    OutreachZohoOpenFailure,
)
from app.domains.outreach.state import refresh_batch_status
from app.domains.templates.repository import TemplateRepository

_ELIGIBLE_STAGES = {
    "qualified",
    "recommended_this_week",
    "ready_to_contact",
    "follow_up_due",
}
_TOKEN_PATTERN = re.compile(r"\{\{\s*(\w+)\s*\}\}")


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _content_hash(subject: str, body: str) -> str:
    return hashlib.sha256(f"{subject}\0{body}".encode()).hexdigest()


class OutreachService:
    def __init__(
        self,
        repository: OutreachRepository | None = None,
        lead_repository: LeadRepository | None = None,
        template_repository: TemplateRepository | None = None,
        catalogue_repository: CatalogueRepository | None = None,
        campaign_repository: CampaignRepository | None = None,
        audit_repository: AuditRepository | None = None,
    ) -> None:
        self.repository = repository or OutreachRepository()
        self.lead_repository = lead_repository or LeadRepository()
        self.template_repository = template_repository or TemplateRepository()
        self.catalogue_repository = catalogue_repository or CatalogueRepository()
        self.campaign_repository = campaign_repository or CampaignRepository()
        self.audit_repository = audit_repository or AuditRepository()

    @staticmethod
    def _hold_active(lead: Lead, today: date) -> bool:
        if not lead.outreach_hold_reason:
            return False
        return lead.outreach_hold_until is None or lead.outreach_hold_until >= today

    @staticmethod
    def _recipient_email(lead: Lead) -> str | None:
        if valid_public_email(lead.contact_email):
            return lead.contact_email
        if valid_public_email(lead.public_email):
            return lead.public_email
        return None

    def _eligibility(
        self,
        session: Session,
        lead: Lead,
        *,
        exclude_draft_id: str | None = None,
    ) -> OutreachLeadOptionRead:
        blockers: list[str] = []
        warnings: list[str] = []
        today = datetime.now(UTC).date()
        if lead.suppressed:
            blockers.append("Lead is suppressed and cannot be contacted.")
        if lead.pipeline_stage not in _ELIGIBLE_STAGES:
            blockers.append("Move the lead to a contact-ready pipeline stage first.")
        if self._recipient_email(lead) is None:
            blockers.append("A valid direct contact or public business email address is required.")
        if lead.contact_classification == "unknown":
            blockers.append("Contact classification requires review.")
        elif lead.contact_classification != "corporate_subscriber":
            warnings.append(
                "This is not classified as a corporate contact; review the approved outreach "
                "basis before any future external use."
            )
        if self._hold_active(lead, today):
            hold_detail = (
                f" until {lead.outreach_hold_until.isoformat()}" if lead.outreach_hold_until else ""
            )
            blockers.append(f"Lead is on outreach hold{hold_detail}.")
        elif lead.outreach_hold_reason and lead.outreach_hold_until:
            warnings.append("The previous outreach hold has expired; review its reason.")
        active_draft = self.repository.active_draft_for_lead(
            session, lead.id, exclude_draft_id=exclude_draft_id
        )
        if active_draft is not None:
            blockers.append("This lead already has an active draft awaiting a decision.")

        recent_cutoff = datetime.now(UTC) - timedelta(days=28)
        if any(
            communication.channel == "email"
            and communication.sent_status == "sent"
            and _aware(communication.sent_at or communication.created_at) >= recent_cutoff
            for communication in lead.communications
        ):
            warnings.append("An email was recorded as sent within the last 28 days.")
        if any(
            communication.sent_status == "received" or communication.response_status == "replied"
            for communication in lead.communications
        ):
            warnings.append(
                "A reply or received communication is recorded; review before outreach."
            )

        notes = sorted(lead.notes, key=lambda item: item.created_at, reverse=True)
        return OutreachLeadOptionRead(
            id=lead.id,
            business_name=lead.business_name,
            location=lead.location,
            pipeline_stage=lead.pipeline_stage,
            public_email=lead.public_email,
            contact_classification=lead.contact_classification,
            current_score=lead.current_score,
            outreach_hold_until=lead.outreach_hold_until,
            outreach_hold_reason=lead.outreach_hold_reason,
            ready=not blockers,
            blockers=blockers,
            warnings=warnings,
            latest_notes=[note.content for note in notes[:3]],
        )

    def lead_options(
        self, session: Session, *, campaign_id: str | None = None
    ) -> list[OutreachLeadOptionRead]:
        if campaign_id is not None and self.campaign_repository.get(session, campaign_id) is None:
            raise DomainError("CAMPAIGN_NOT_FOUND", "Campaign not found.", status_code=404)
        leads = self.lead_repository.list(session, campaign_id=campaign_id)
        return [self._eligibility(session, lead) for lead in leads]

    def _template_products(self, session: Session, template: Template) -> list[Product]:
        products: dict[str, Product] = {}
        for family_id in template.product_family_ids:
            family = self.catalogue_repository.get_family(session, family_id)
            if family is None:
                continue
            for product in self.catalogue_repository.by_ids(session, family.product_ids):
                if product.active:
                    products[product.id] = product
        return list(products.values())

    @staticmethod
    def _template_values(lead: Lead, products: list[Product]) -> dict[str, str]:
        product_lines = "\n".join(
            f"{product.name} — {product.pricing_guidance}"
            if product.pricing_guidance
            else product.name
            for product in products
        )
        contact_full_name = " ".join(
            part for part in (lead.contact_first_name, lead.contact_last_name) if part
        )
        return {
            "business_name": lead.business_name,
            "location": lead.location,
            "segment": lead.segment,
            "phone_number": lead.phone_number or "",
            "public_email": lead.public_email or "",
            "website": lead.website or "",
            "products": product_lines,
            "greeting_name": lead.contact_first_name or lead.business_name,
            "contact_first_name": lead.contact_first_name or "",
            "contact_last_name": lead.contact_last_name or "",
            "contact_full_name": contact_full_name,
            "contact_role": lead.contact_role or "",
            "personalisation_observation": lead.personalisation_observation or "",
            "relevance_opportunity": lead.relevance_opportunity or "",
            "offer_angle": lead.offer_angle or "",
            "desired_next_step": lead.desired_next_step or "",
        }

    @classmethod
    def _render(cls, text: str, lead: Lead, products: list[Product]) -> str:
        values = cls._template_values(lead, products)
        return _TOKEN_PATTERN.sub(lambda match: values.get(match.group(1), match.group(0)), text)

    def template_blockers(
        self,
        session: Session,
        lead: Lead,
        template: Template,
    ) -> list[str]:
        products = self._template_products(session, template)
        values = self._template_values(lead, products)
        tokens = set(_TOKEN_PATTERN.findall(f"{template.subject}\n{template.body}"))
        unsupported = sorted(tokens - values.keys())
        blockers = [f"Template field {{{{{token}}}}} is not supported." for token in unsupported]
        labels = {
            "contact_first_name": "contact first name",
            "contact_last_name": "contact last name",
            "contact_full_name": "contact name",
            "contact_role": "contact role",
            "personalisation_observation": "personalisation observation",
            "relevance_opportunity": "relevance opportunity",
            "offer_angle": "offer angle",
            "desired_next_step": "desired next step",
            "phone_number": "phone number",
            "public_email": "public business email",
            "website": "website",
            "products": "template product family",
        }
        missing = sorted(token for token in tokens if token in values and not values[token].strip())
        blockers.extend(
            f"Complete the lead's {labels.get(token, token.replace('_', ' '))} before creating "
            "this draft."
            for token in missing
        )
        return blockers

    def create_batch(
        self,
        session: Session,
        data: OutreachBatchCreate,
        correlation_id: str,
    ) -> OutreachBatchRead:
        template = self.template_repository.get(session, data.template_id)
        if template is None:
            raise DomainError("TEMPLATE_NOT_FOUND", "Template not found.", status_code=404)
        if (
            data.campaign_id is not None
            and self.campaign_repository.get(session, data.campaign_id) is None
        ):
            raise DomainError("CAMPAIGN_NOT_FOUND", "Campaign not found.", status_code=404)

        leads: list[Lead] = []
        blocked: list[dict[str, object]] = []
        for lead_id in data.lead_ids:
            lead = self.lead_repository.get(session, lead_id)
            if lead is None:
                raise DomainError("LEAD_NOT_FOUND", "Lead not found.", status_code=404)
            if data.campaign_id is not None and not any(
                link.campaign_id == data.campaign_id for link in lead.campaigns
            ):
                blocked.append(
                    {
                        "lead_id": lead.id,
                        "business_name": lead.business_name,
                        "reasons": ["Lead is not part of the selected campaign."],
                    }
                )
                continue
            eligibility = self._eligibility(session, lead)
            template_reasons = self.template_blockers(session, lead, template)
            if not eligibility.ready or template_reasons:
                blocked.append(
                    {
                        "lead_id": lead.id,
                        "business_name": lead.business_name,
                        "reasons": [*eligibility.blockers, *template_reasons],
                    }
                )
            leads.append(lead)
        if blocked:
            raise DomainError(
                "OUTREACH_LEADS_NOT_READY",
                "One or more selected leads require attention before drafts can be created.",
                status_code=409,
                details={"blocked_leads": blocked},
            )

        products = self._template_products(session, template)
        batch = OutreachBatch(
            campaign_id=data.campaign_id,
            template_id=template.id,
            status="review",
        )
        session.add(batch)
        session.flush()
        for lead in leads:
            recipient_email = self._recipient_email(lead)
            if recipient_email is None:
                raise RuntimeError("An eligible outreach lead is missing a recipient email")
            subject = self._render(template.subject or template.topic, lead, products).strip()
            body = self._render(template.body, lead, products).strip()
            draft = OutreachDraft(
                batch_id=batch.id,
                lead_id=lead.id,
                template_id=template.id,
                recipient_email=recipient_email,
                review_status="pending_review",
                sync_status="local_only",
                current_version=1,
            )
            session.add(draft)
            session.flush()
            revision = OutreachDraftRevision(
                draft_id=draft.id,
                version=1,
                subject=subject,
                body=body,
                content_hash=_content_hash(subject, body),
                editor="template",
            )
            session.add(revision)
            record_audit_event(
                session,
                action="outreach.draft_generated",
                entity_type="outreach_draft",
                entity_id=draft.id,
                correlation_id=correlation_id,
                summary={"lead_id": lead.id, "batch_id": batch.id, "version": 1},
            )
        record_audit_event(
            session,
            action="outreach.batch_created",
            entity_type="outreach_batch",
            entity_id=batch.id,
            correlation_id=correlation_id,
            summary={"draft_count": len(leads), "template_id": template.id},
        )
        session.commit()
        return self.get_batch(session, batch.id)

    @staticmethod
    def _current_revision(draft: OutreachDraft) -> OutreachDraftRevision:
        revision = next(
            (item for item in draft.revisions if item.version == draft.current_version), None
        )
        if revision is None:
            raise RuntimeError("The current outreach draft revision is missing")
        return revision

    def _draft_to_read(self, draft: OutreachDraft) -> OutreachDraftRead:
        revision = self._current_revision(draft)
        notes = sorted(draft.lead.notes, key=lambda item: item.created_at, reverse=True)
        return OutreachDraftRead(
            id=draft.id,
            batch_id=draft.batch_id,
            lead_id=draft.lead_id,
            business_name=draft.lead.business_name,
            location=draft.lead.location,
            pipeline_stage=draft.lead.pipeline_stage,
            recipient_email=draft.recipient_email,
            contact_classification=draft.lead.contact_classification,
            current_score=draft.lead.current_score,
            outreach_hold_until=draft.lead.outreach_hold_until,
            outreach_hold_reason=draft.lead.outreach_hold_reason,
            latest_notes=[note.content for note in notes[:3]],
            template_id=draft.template_id,
            review_status=draft.review_status,
            sync_status=draft.sync_status,
            current_version=draft.current_version,
            approved_version=draft.approved_version,
            approved_at=draft.approved_at,
            rejected_at=draft.rejected_at,
            rejection_reason=draft.rejection_reason,
            blocked_reason=draft.blocked_reason,
            current_revision=OutreachDraftRevisionRead.model_validate(revision),
            revision_count=len(draft.revisions),
            created_at=draft.created_at,
            updated_at=draft.updated_at,
        )

    def _batch_to_read(self, session: Session, batch: OutreachBatch) -> OutreachBatchRead:
        drafts = sorted(batch.drafts, key=lambda item: item.created_at)
        template = (
            self.template_repository.get(session, batch.template_id) if batch.template_id else None
        )
        return OutreachBatchRead(
            id=batch.id,
            campaign_id=batch.campaign_id,
            template_id=batch.template_id,
            template_topic=template.topic if template else None,
            status=batch.status,
            pending_count=sum(item.review_status == "pending_review" for item in drafts),
            approved_count=sum(
                item.review_status == "approved" and item.sync_status != "user_confirmed_sent"
                for item in drafts
            ),
            rejected_count=sum(item.review_status == "rejected" for item in drafts),
            sent_count=sum(item.sync_status == "user_confirmed_sent" for item in drafts),
            drafts=[self._draft_to_read(draft) for draft in drafts],
            created_at=batch.created_at,
            updated_at=batch.updated_at,
        )

    def get_batch(self, session: Session, batch_id: str) -> OutreachBatchRead:
        batch = self.repository.get_batch(session, batch_id)
        if batch is None:
            raise DomainError("OUTREACH_BATCH_NOT_FOUND", "Draft batch not found.", status_code=404)
        return self._batch_to_read(session, batch)

    def list_batches(self, session: Session) -> list[OutreachBatchRead]:
        return [
            self._batch_to_read(session, batch) for batch in self.repository.list_batches(session)
        ]

    def edit_draft(
        self,
        session: Session,
        draft_id: str,
        data: OutreachDraftEdit,
        correlation_id: str,
    ) -> OutreachDraftRead:
        draft = self.repository.get_draft(session, draft_id)
        if draft is None:
            raise DomainError("OUTREACH_DRAFT_NOT_FOUND", "Draft not found.", status_code=404)
        if draft.sync_status not in {"local_only", "blocked", "opened_in_zoho"}:
            raise DomainError(
                "OUTREACH_DRAFT_LOCKED",
                "This draft can no longer be edited locally.",
                status_code=409,
            )
        current = self._current_revision(draft)
        if current.subject == data.subject and current.body == data.body:
            raise DomainError(
                "OUTREACH_DRAFT_UNCHANGED",
                "The draft content has not changed.",
                status_code=409,
            )
        version = draft.current_version + 1
        revision = OutreachDraftRevision(
            draft_id=draft.id,
            version=version,
            subject=data.subject,
            body=data.body,
            content_hash=_content_hash(data.subject, data.body),
            editor="local_user",
        )
        draft.revisions.append(revision)
        draft.current_version = version
        draft.review_status = "pending_review"
        draft.sync_status = "local_only"
        draft.approved_version = None
        draft.approved_content_hash = None
        draft.approved_at = None
        draft.rejected_at = None
        draft.rejection_reason = None
        draft.blocked_reason = None
        refresh_batch_status(session, draft.batch_id)
        record_audit_event(
            session,
            action="outreach.draft_edited",
            entity_type="outreach_draft",
            entity_id=draft.id,
            correlation_id=correlation_id,
            summary={"lead_id": draft.lead_id, "version": version},
        )
        session.commit()
        return self.get_draft(session, draft.id)

    def _approve_model(self, session: Session, draft: OutreachDraft, correlation_id: str) -> None:
        if draft.sync_status == "user_confirmed_sent":
            raise DomainError(
                "OUTREACH_DRAFT_ALREADY_SENT",
                "A draft already confirmed as sent cannot be approved again.",
                status_code=409,
            )
        eligibility = self._eligibility(session, draft.lead, exclude_draft_id=draft.id)
        if not eligibility.ready:
            raise DomainError(
                "OUTREACH_DRAFT_NOT_READY",
                "The lead requires attention before this draft can be approved.",
                status_code=409,
                details={"reasons": eligibility.blockers},
            )
        revision = self._current_revision(draft)
        recipient_email = self._recipient_email(draft.lead)
        if recipient_email is None:
            raise RuntimeError("An eligible outreach lead is missing a recipient email")
        draft.recipient_email = recipient_email
        draft.review_status = "approved"
        draft.sync_status = "local_only"
        draft.approved_version = revision.version
        draft.approved_content_hash = revision.content_hash
        draft.approved_at = datetime.now(UTC)
        draft.rejected_at = None
        draft.rejection_reason = None
        draft.blocked_reason = None
        record_audit_event(
            session,
            action="outreach.draft_approved",
            entity_type="outreach_draft",
            entity_id=draft.id,
            correlation_id=correlation_id,
            summary={
                "lead_id": draft.lead_id,
                "version": revision.version,
                "content_hash": revision.content_hash,
            },
        )

    def approve_draft(
        self, session: Session, draft_id: str, correlation_id: str
    ) -> OutreachDraftRead:
        draft = self.repository.get_draft(session, draft_id)
        if draft is None:
            raise DomainError("OUTREACH_DRAFT_NOT_FOUND", "Draft not found.", status_code=404)
        self._approve_model(session, draft, correlation_id)
        refresh_batch_status(session, draft.batch_id)
        session.commit()
        return self.get_draft(session, draft.id)

    def approve_many(
        self,
        session: Session,
        data: OutreachDraftApproveMany,
        correlation_id: str,
    ) -> list[OutreachDraftRead]:
        drafts: list[OutreachDraft] = []
        for draft_id in data.draft_ids:
            draft = self.repository.get_draft(session, draft_id)
            if draft is None:
                raise DomainError("OUTREACH_DRAFT_NOT_FOUND", "Draft not found.", status_code=404)
            self._approve_model(session, draft, correlation_id)
            drafts.append(draft)
        for batch_id in {draft.batch_id for draft in drafts}:
            refresh_batch_status(session, batch_id)
        session.commit()
        return [self.get_draft(session, draft.id) for draft in drafts]

    def reject_draft(
        self,
        session: Session,
        draft_id: str,
        data: OutreachDraftReject,
        correlation_id: str,
    ) -> OutreachDraftRead:
        draft = self.repository.get_draft(session, draft_id)
        if draft is None:
            raise DomainError("OUTREACH_DRAFT_NOT_FOUND", "Draft not found.", status_code=404)
        if draft.sync_status not in {"local_only", "blocked", "opened_in_zoho"}:
            raise DomainError(
                "OUTREACH_DRAFT_LOCKED",
                "A draft already transferred externally cannot be rejected locally.",
                status_code=409,
            )
        draft.review_status = "rejected"
        draft.sync_status = "local_only"
        draft.approved_version = None
        draft.approved_content_hash = None
        draft.approved_at = None
        draft.rejected_at = datetime.now(UTC)
        draft.rejection_reason = data.reason
        draft.blocked_reason = None
        refresh_batch_status(session, draft.batch_id)
        record_audit_event(
            session,
            action="outreach.draft_rejected",
            entity_type="outreach_draft",
            entity_id=draft.id,
            correlation_id=correlation_id,
            summary={"lead_id": draft.lead_id, "reason": data.reason},
        )
        session.commit()
        return self.get_draft(session, draft.id)

    def prepare_zoho_handoff(
        self, session: Session, draft_id: str, correlation_id: str
    ) -> OutreachZohoHandoffRead:
        draft = self.repository.get_draft(session, draft_id)
        if draft is None:
            raise DomainError("OUTREACH_DRAFT_NOT_FOUND", "Draft not found.", status_code=404)
        if draft.review_status != "approved" or draft.sync_status not in {
            "local_only",
            "opened_in_zoho",
        }:
            raise DomainError(
                "OUTREACH_DRAFT_NOT_APPROVED",
                "Only a currently approved, unsent draft can be opened in Zoho.",
                status_code=409,
            )

        eligibility = self._eligibility(session, draft.lead, exclude_draft_id=draft.id)
        if not eligibility.ready:
            raise DomainError(
                "OUTREACH_DRAFT_NOT_READY",
                "The lead requires attention before this draft can be opened in Zoho.",
                status_code=409,
                details={"reasons": eligibility.blockers},
            )
        revision = self._current_revision(draft)
        if (
            draft.approved_version != revision.version
            or draft.approved_content_hash != revision.content_hash
        ):
            raise DomainError(
                "OUTREACH_DRAFT_APPROVAL_STALE",
                "The current draft version must be approved again before it can be opened in Zoho.",
                status_code=409,
            )

        opened_at = datetime.now(UTC)
        recipient_email = self._recipient_email(draft.lead)
        if recipient_email is None:
            raise RuntimeError("An eligible outreach lead is missing a recipient email")
        draft.recipient_email = recipient_email
        draft.sync_status = "opened_in_zoho"
        record_audit_event(
            session,
            action="outreach.zoho_open_clicked",
            entity_type="outreach_draft",
            entity_id=draft.id,
            correlation_id=correlation_id,
            summary={
                "lead_id": draft.lead_id,
                "version": revision.version,
                "recipient_email": draft.recipient_email,
                "sending_confirmed": False,
            },
        )
        session.commit()
        return OutreachZohoHandoffRead(
            draft_id=draft.id,
            lead_id=draft.lead_id,
            recipient_email=draft.recipient_email,
            subject=revision.subject,
            body=revision.body,
            version=revision.version,
            opened_at=opened_at,
        )

    def record_zoho_open_failure(
        self,
        session: Session,
        draft_id: str,
        data: OutreachZohoOpenFailure,
        correlation_id: str,
    ) -> OutreachDraftRead:
        draft = self.repository.get_draft(session, draft_id)
        if draft is None:
            raise DomainError("OUTREACH_DRAFT_NOT_FOUND", "Draft not found.", status_code=404)
        if draft.review_status != "approved" or draft.sync_status != "opened_in_zoho":
            raise DomainError(
                "OUTREACH_ZOHO_OPEN_NOT_PENDING",
                "There is no current Zoho handoff to mark as failed.",
                status_code=409,
            )
        revision = self._current_revision(draft)
        draft.sync_status = "local_only"
        record_audit_event(
            session,
            action="outreach.zoho_open_failed",
            entity_type="outreach_draft",
            entity_id=draft.id,
            correlation_id=correlation_id,
            summary={
                "lead_id": draft.lead_id,
                "version": revision.version,
                "recipient_email": draft.recipient_email,
                "reason": data.reason,
                "sending_confirmed": False,
            },
        )
        session.commit()
        return self.get_draft(session, draft.id)

    def confirm_sent(
        self, session: Session, draft_id: str, correlation_id: str
    ) -> OutreachDraftRead:
        draft = self.repository.get_draft(session, draft_id)
        if draft is None:
            raise DomainError("OUTREACH_DRAFT_NOT_FOUND", "Draft not found.", status_code=404)
        if draft.review_status != "approved" or draft.sync_status != "opened_in_zoho":
            raise DomainError(
                "OUTREACH_DRAFT_NOT_CONFIRMABLE",
                "Only an approved draft currently opened in Zoho can be marked sent.",
                status_code=409,
            )
        if not self.audit_repository.has_event(
            session,
            entity_type="outreach_draft",
            entity_id=draft.id,
            action="outreach.zoho_open_clicked",
        ):
            raise DomainError(
                "OUTREACH_ZOHO_NOT_OPENED",
                "Open the approved draft in Zoho before marking it as sent.",
                status_code=409,
            )
        revision = self._current_revision(draft)
        if (
            draft.approved_version != revision.version
            or draft.approved_content_hash != revision.content_hash
        ):
            raise DomainError(
                "OUTREACH_DRAFT_APPROVAL_STALE",
                "The current draft version no longer matches the approved version.",
                status_code=409,
            )

        communication = Communication(
            lead_id=draft.lead_id,
            channel="email",
            subject=revision.subject,
            content=revision.body,
            draft_status="sent_from_approved_draft",
            approval_status="manual_confirmed",
            sent_status="sent",
            sent_at=datetime.now(UTC),
            user_confirmed=True,
            response_status="none",
        )
        session.add(communication)
        session.flush()
        draft.sync_status = "user_confirmed_sent"
        record_audit_event(
            session,
            action="outreach.draft_sent_confirmed",
            entity_type="outreach_draft",
            entity_id=draft.id,
            correlation_id=correlation_id,
            summary={
                "lead_id": draft.lead_id,
                "version": revision.version,
                "communication_id": communication.id,
                "user_confirmed": True,
            },
        )
        refresh_batch_status(session, draft.batch_id)
        session.commit()
        return self.get_draft(session, draft.id)

    def reopen_draft(
        self, session: Session, draft_id: str, correlation_id: str
    ) -> OutreachDraftRead:
        draft = self.repository.get_draft(session, draft_id)
        if draft is None:
            raise DomainError("OUTREACH_DRAFT_NOT_FOUND", "Draft not found.", status_code=404)
        if draft.review_status != "rejected":
            raise DomainError(
                "OUTREACH_DRAFT_NOT_REJECTED",
                "Only a rejected draft can be reopened.",
                status_code=409,
            )
        draft.review_status = "pending_review"
        draft.sync_status = "local_only"
        draft.rejected_at = None
        draft.rejection_reason = None
        draft.blocked_reason = None
        refresh_batch_status(session, draft.batch_id)
        record_audit_event(
            session,
            action="outreach.draft_reopened",
            entity_type="outreach_draft",
            entity_id=draft.id,
            correlation_id=correlation_id,
            summary={"lead_id": draft.lead_id},
        )
        session.commit()
        return self.get_draft(session, draft.id)

    def get_draft(self, session: Session, draft_id: str) -> OutreachDraftRead:
        draft = self.repository.get_draft(session, draft_id)
        if draft is None:
            raise DomainError("OUTREACH_DRAFT_NOT_FOUND", "Draft not found.", status_code=404)
        return self._draft_to_read(draft)
