from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import ConversationMessage, LongTermMemory


class MemoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_messages(self, session_id: str, limit: int = 20) -> Sequence[ConversationMessage]:
        result = await self.session.execute(
            select(ConversationMessage).where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at.desc()).limit(limit)
        )
        return list(reversed(result.scalars().all()))

    async def list_long_term(self, user_id: str, limit: int = 20) -> Sequence[LongTermMemory]:
        result = await self.session.execute(
            select(LongTermMemory).where(LongTermMemory.user_id == user_id)
            .order_by(LongTermMemory.importance.desc(), LongTermMemory.updated_at.desc()).limit(limit)
        )
        return result.scalars().all()

    async def add_message(self, **values) -> ConversationMessage:
        item = ConversationMessage(**values)
        self.session.add(item)
        await self.session.commit()
        return item

    async def add_long_term(self, **values) -> LongTermMemory:
        item = LongTermMemory(**values)
        self.session.add(item)
        await self.session.commit()
        return item

    async def save_turn(self, *, user_id: str, session_id: str, query: str, intent: str, response: str) -> None:
        self.session.add(ConversationMessage(
            user_id=user_id, session_id=session_id, role="user", content=query, intent=intent
        ))
        self.session.add(ConversationMessage(
            user_id=user_id, session_id=session_id, role="assistant", content=response, intent=intent
        ))
        await self.session.commit()

    async def remember_preference(self, *, user_id: str, content: str, memory_type: str = "preference") -> None:
        await self.add_long_term(
            user_id=user_id, memory_type=memory_type, content=content,
            source="conversation", confidence=0.8, importance=0.7,
        )
