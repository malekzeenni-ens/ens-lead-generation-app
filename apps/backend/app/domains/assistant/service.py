from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import DomainError
from app.db.models import AssistantAttachment, AssistantConversation, AssistantMessage
from app.domains.assistant.context import build_app_context
from app.domains.assistant.files import AssistantFileStore
from app.domains.assistant.prompt import build_general_messages
from app.domains.assistant.repository import AssistantRepository
from app.domains.assistant.schemas import (
    AssistantAttachmentRead,
    AssistantConversationRead,
    AssistantMessageCreate,
    AssistantMessageRead,
)
from app.domains.audit.service import record_audit_event
from app.domains.campaign_assistant.manager import CampaignAssistantManager


class AssistantService:
    def __init__(
        self,
        manager: CampaignAssistantManager,
        settings: Settings,
        *,
        repository: AssistantRepository | None = None,
        file_store: AssistantFileStore | None = None,
    ) -> None:
        self.manager = manager
        self.settings = settings
        self.repository = repository or AssistantRepository()
        self.file_store = file_store or AssistantFileStore(settings)

    def create(self, session: Session, title: str | None = None) -> AssistantConversationRead:
        conversation = AssistantConversation(title=title or "New conversation")
        self.repository.add_conversation(session, conversation)
        session.commit()
        return self.get(session, conversation.id)

    def list(self, session: Session) -> list[AssistantConversationRead]:
        return [self._read(item) for item in self.repository.list_conversations(session)]

    def get(self, session: Session, conversation_id: str) -> AssistantConversationRead:
        conversation = self._require_conversation(session, conversation_id)
        return self._read(conversation)

    def send(
        self,
        session: Session,
        *,
        conversation_id: str,
        data: AssistantMessageCreate,
        protect_resources: bool,
        instagram_connected: bool,
        correlation_id: str,
    ) -> AssistantConversationRead:
        conversation = self._require_conversation(session, conversation_id)
        app_context = build_app_context(
            session,
            user_request=data.content,
            runtime_settings=self.settings,
            instagram_connected=instagram_connected,
            selection=data.context,
        )
        user_message = AssistantMessage(
            conversation_id=conversation.id,
            role="user",
            content=data.content,
        )
        self.repository.add_message(session, user_message)
        session.flush()
        for upload in data.attachments:
            attachment = self.file_store.uploaded(
                upload,
                conversation_id=conversation.id,
                message_id=user_message.id,
            )
            self.repository.add_attachment(session, attachment)
        if not conversation.messages:
            conversation.title = self._title(data.content)
        conversation.updated_at = datetime.now(UTC)
        session.commit()

        conversation = self._require_conversation(session, conversation_id)
        artifact_format = self._artifact_format(data.content)
        messages = build_general_messages(
            sorted(conversation.messages, key=lambda item: item.created_at),
            app_context=app_context,
            attachment_context_chars=self.settings.assistant_attachment_context_chars,
            artifact_format=artifact_format,
        )
        result, profile = self.manager.chat(
            messages,
            protect_resources=protect_resources,
            artifact_format=artifact_format,
        )
        assistant_message = AssistantMessage(
            conversation_id=conversation.id,
            role="assistant",
            content=result.content,
            model_name=result.metrics.model,
            resource_profile=profile.value,
            generation_duration_ms=result.metrics.total_duration_ms,
            campaign_draft_suggested=self._suggest_campaign(data.content),
        )
        self.repository.add_message(session, assistant_message)
        session.flush()
        if artifact_format is not None and result.artifact_content is not None:
            artifact = self.file_store.generated(
                conversation_id=conversation.id,
                message_id=assistant_message.id,
                requested_format=artifact_format,
                suggested_filename=result.artifact_filename or "assistant-file",
                content=result.artifact_content,
            )
            self.repository.add_attachment(session, artifact)
        conversation.updated_at = datetime.now(UTC)
        record_audit_event(
            session,
            action="assistant.message.generated",
            entity_type="assistant_conversation",
            entity_id=conversation.id,
            correlation_id=correlation_id,
            summary={
                "model": result.metrics.model,
                "resource_profile": profile.value,
                "attachments_received": len(data.attachments),
                "artifact_format": artifact_format,
            },
        )
        session.commit()
        return self.get(session, conversation.id)

    def attachment(
        self, session: Session, conversation_id: str, attachment_id: str
    ) -> tuple[AssistantAttachment, Path]:
        attachment = self.repository.get_attachment(session, attachment_id)
        if attachment is None or attachment.conversation_id != conversation_id:
            raise DomainError(
                "ASSISTANT_ATTACHMENT_NOT_FOUND",
                "The local attachment was not found.",
                status_code=404,
            )
        return attachment, self.file_store.path(attachment)

    def campaign_brief(self, session: Session, conversation_id: str) -> str:
        conversation = self._require_conversation(session, conversation_id)
        lines: list[str] = []
        for message in sorted(conversation.messages, key=lambda item: item.created_at)[-10:]:
            lines.append(f"{message.role.title()}: {message.content}")
            for attachment in message.attachments:
                if attachment.extracted_text:
                    lines.append(
                        f"Attachment {attachment.filename}: {attachment.extracted_text[:4_000]}"
                    )
        transcript = "\n".join(lines)
        prefix = (
            "Create a campaign draft from this app-copilot conversation. Apply the built-in "
            "campaign playbook and workspace defaults; any custom playbook in the conversation "
            "is optional supporting context:\n"
        )
        return prefix + transcript[-(2_000 - len(prefix)) :]

    def _require_conversation(
        self, session: Session, conversation_id: str
    ) -> AssistantConversation:
        conversation = self.repository.get_conversation(session, conversation_id)
        if conversation is None:
            raise DomainError(
                "ASSISTANT_CONVERSATION_NOT_FOUND",
                "The local assistant conversation was not found.",
                status_code=404,
            )
        return conversation

    @staticmethod
    def _title(content: str) -> str:
        title = re.sub(r"\s+", " ", content).strip()
        return title[:80] + ("…" if len(title) > 80 else "")

    @staticmethod
    def _artifact_format(content: str) -> str | None:
        folded = content.casefold()
        if any(marker in folded for marker in ("word document", "word file", "docx", ".docx")):
            return "docx"
        if any(
            marker in folded
            for marker in ("as a csv", "as csv", "csv file", "spreadsheet", "export to csv")
        ):
            return "csv"
        if any(marker in folded for marker in ("as a txt", "as txt", "text file", ".txt")):
            return "txt"
        if any(marker in folded for marker in ("template", "playbook", "downloadable file")):
            return "txt"
        return None

    @staticmethod
    def _suggest_campaign(content: str) -> bool:
        folded = content.casefold()
        action = any(word in folded for word in ("create", "build", "prepare", "draft"))
        mentions_campaign = "campaign" in folded
        playbook_only = "campaign playbook" in folded and not any(
            phrase in folded for phrase in ("based on", "from this", "use this")
        )
        return action and mentions_campaign and not playbook_only

    @staticmethod
    def _read(conversation: AssistantConversation) -> AssistantConversationRead:
        messages = sorted(conversation.messages, key=lambda item: item.created_at)
        return AssistantConversationRead(
            id=conversation.id,
            title=conversation.title,
            messages=[AssistantService._message_read(item) for item in messages],
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )

    @staticmethod
    def _message_read(message: AssistantMessage) -> AssistantMessageRead:
        attachments = sorted(message.attachments, key=lambda item: item.created_at)
        return AssistantMessageRead(
            id=message.id,
            role=message.role,
            content=message.content,
            model_name=message.model_name,
            resource_profile=message.resource_profile,
            generation_duration_ms=message.generation_duration_ms,
            campaign_draft_suggested=message.campaign_draft_suggested,
            attachments=[
                AssistantAttachmentRead(
                    id=item.id,
                    direction=item.direction,
                    filename=item.filename,
                    media_type=item.media_type,
                    size_bytes=item.size_bytes,
                    processing_status=item.processing_status,
                    download_url=(
                        f"/assistant/conversations/{message.conversation_id}/attachments/{item.id}"
                    ),
                    created_at=item.created_at,
                )
                for item in attachments
            ],
            created_at=message.created_at,
        )
