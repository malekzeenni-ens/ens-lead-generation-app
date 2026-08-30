from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import AssistantAttachment, AssistantConversation, AssistantMessage


class AssistantRepository:
    def add_conversation(self, session: Session, conversation: AssistantConversation) -> None:
        session.add(conversation)

    def get_conversation(
        self, session: Session, conversation_id: str
    ) -> AssistantConversation | None:
        return session.scalar(
            select(AssistantConversation)
            .where(AssistantConversation.id == conversation_id)
            .options(
                selectinload(AssistantConversation.messages).selectinload(
                    AssistantMessage.attachments
                )
            )
            .execution_options(populate_existing=True)
        )

    def list_conversations(self, session: Session) -> list[AssistantConversation]:
        return list(
            session.scalars(
                select(AssistantConversation)
                .options(
                    selectinload(AssistantConversation.messages).selectinload(
                        AssistantMessage.attachments
                    )
                )
                .order_by(AssistantConversation.updated_at.desc())
            )
        )

    def add_message(self, session: Session, message: AssistantMessage) -> None:
        session.add(message)

    def add_attachment(self, session: Session, attachment: AssistantAttachment) -> None:
        session.add(attachment)

    def get_attachment(self, session: Session, attachment_id: str) -> AssistantAttachment | None:
        return session.get(AssistantAttachment, attachment_id)
