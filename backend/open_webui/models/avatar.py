# Daily quota bookkeeping for AI avatar generation. One row per (user, UTC day).
from typing import Optional

from sqlalchemy import BigInteger, Column, Text, select, update
from sqlalchemy.exc import IntegrityError
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
        # Insert-first, then fall back to an atomic server-side UPDATE on PK
        # conflict. Portable (SQLite + Postgres) and multi-worker-safe: the
        # `count = count + 1` expression runs in the database, so concurrent
        # increments cannot lose updates, and the composite-PK conflict is
        # handled instead of racing a read-then-write.
        async with get_async_db_context(db) as db:
            try:
                db.add(AvatarGeneration(user_id=user_id, date=date, count=1))
                await db.commit()
                return 1
            except IntegrityError:
                await db.rollback()
                await db.execute(
                    update(AvatarGeneration)
                    .where(
                        AvatarGeneration.user_id == user_id,
                        AvatarGeneration.date == date,
                    )
                    .values(count=AvatarGeneration.count + 1)
                )
                await db.commit()
                res = await db.execute(
                    select(AvatarGeneration).filter_by(user_id=user_id, date=date)
                )
                return res.scalars().first().count


AvatarGenerations = AvatarGenerationTable()
