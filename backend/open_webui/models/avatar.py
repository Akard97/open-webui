# Daily quota bookkeeping for AI avatar generation. One row per (user, UTC day).
from typing import Optional

from sqlalchemy import BigInteger, Column, Text, select
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import Base, get_async_db_context


class AvatarGeneration(Base):
    __tablename__ = 'avatar_generation'

    user_id = Column(Text, primary_key=True)
    date = Column(Text, primary_key=True)  # UTC day, 'YYYY-MM-DD'
    count = Column(BigInteger, nullable=False, default=0)


class AvatarGenerationTable:
    async def get_count(
        self, user_id: str, date: str, db: Optional[AsyncSession] = None
    ) -> int:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(AvatarGeneration).filter_by(user_id=user_id, date=date)
            )
            row = res.scalars().first()
            return row.count if row else 0

    async def increment(
        self, user_id: str, date: str, db: Optional[AsyncSession] = None
    ) -> int:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(AvatarGeneration).filter_by(user_id=user_id, date=date)
            )
            row = res.scalars().first()
            if row:
                row.count = row.count + 1
            else:
                row = AvatarGeneration(user_id=user_id, date=date, count=1)
                db.add(row)
            await db.commit()
            return row.count


AvatarGenerations = AvatarGenerationTable()
