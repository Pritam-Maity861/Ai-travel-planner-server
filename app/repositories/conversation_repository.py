import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation


class ConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_query: str,
        user_id: uuid.UUID | None = None,
        title: str | None = None,
        destination: str | None = None,
    ) -> Conversation:
        conv = Conversation(
            user_query=user_query,
            user_id=user_id,
            title=title,
            destination=destination,
            status="running",
        )
        self.session.add(conv)
        await self.session.commit()
        await self.session.refresh(conv)
        return conv

    async def get(self, conv_id: uuid.UUID) -> Conversation | None:
        return await self.session.scalar(select(Conversation).where(Conversation.id == conv_id))

    async def list_by_user(self, user_id: uuid.UUID) -> list[Conversation]:
        result = await self.session.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.created_at.desc())
        )
        return list(result.scalars().all())

    async def update(self, conv: Conversation, **fields) -> Conversation:
        for k, v in fields.items():
            setattr(conv, k, v)
        await self.session.commit()
        await self.session.refresh(conv)
        return conv

    async def update_status(self, conv_id: uuid.UUID, **fields) -> Conversation | None:
        conv = await self.get(conv_id)
        if not conv:
            return None
        valid_cols = {
            "status",
            "title",
            "destination",
            "final_response",
            "blocked_reason",
            "user_query",
        }
        for k, v in fields.items():
            if k in valid_cols:
                setattr(conv, k, v)
        await self.session.commit()
        await self.session.refresh(conv)
        return conv

    async def delete(self, conv_id: uuid.UUID, user_id: uuid.UUID | None = None) -> bool:
        conv = await self.get(conv_id)
        if not conv:
            return False
        if user_id and conv.user_id != user_id:
            return False
        await self.session.delete(conv)
        await self.session.commit()
        return True

    async def save_pdf(
        self,
        conv_id: uuid.UUID,
        pdf_bytes: bytes,
        filename: str,
    ) -> Conversation | None:
        conv = await self.get(conv_id)
        if conv:
            conv.pdf_data = pdf_bytes
            conv.pdf_filename = filename
            conv.pdf_created_at = datetime.now(UTC)
            await self.session.commit()
            await self.session.refresh(conv)
        return conv
