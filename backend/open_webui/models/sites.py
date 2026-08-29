import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, Index, JSON, Text, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from open_webui.internal.db import Base, get_async_db_context


def _now() -> int:
    return int(time.time() * 1000)


class Site(Base):
    __tablename__ = 'site'

    id = Column(Text, primary_key=True)
    user_id = Column(Text, nullable=False, index=True)
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False, unique=True, index=True)
    public = Column(Boolean, nullable=False, default=False)
    files = Column(JSON, nullable=False)  # [{"name","size","content_type"}]
    entry_file = Column(Text, nullable=False)
    created_at = Column(BigInteger, nullable=False)
    updated_at = Column(BigInteger, nullable=False)


class SiteView(Base):
    __tablename__ = 'site_view'

    id = Column(Text, primary_key=True)
    site_id = Column(Text, nullable=False)
    path = Column(Text, nullable=False)
    # Daily-rotating HMAC of IP + User-Agent. Not reversible to an IP, and not
    # linkable to the same visitor on another day or another site.
    visitor_key = Column(Text, nullable=False)
    is_owner = Column(Boolean, nullable=False, default=False)
    created_at = Column(BigInteger, nullable=False)

    __table_args__ = (Index('ix_site_view_site_created', 'site_id', 'created_at'),)


class SiteModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    name: str
    slug: str
    public: bool
    files: list
    entry_file: str
    created_at: int
    updated_at: int


class SiteViewModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    site_id: str
    path: str
    visitor_key: str
    is_owner: bool
    created_at: int


class SitesTable:
    async def insert_new_site(
        self,
        user_id: str,
        *,
        name: str,
        slug: str,
        public: bool,
        files: list[dict],
        entry_file: str,
        db: Optional[AsyncSession] = None,
    ) -> Optional[SiteModel]:
        async with get_async_db_context(db) as db:
            now = _now()
            site = Site(
                id=str(uuid.uuid4()),
                user_id=user_id,
                name=name,
                slug=slug,
                public=public,
                files=files,
                entry_file=entry_file,
                created_at=now,
                updated_at=now,
            )
            db.add(site)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                return None
            await db.refresh(site)
            return SiteModel.model_validate(site)

    async def get_site_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[SiteModel]:
        async with get_async_db_context(db) as db:
            site = (await db.execute(select(Site).where(Site.id == id))).scalars().first()
            return SiteModel.model_validate(site) if site else None

    async def get_site_by_slug(self, slug: str, db: Optional[AsyncSession] = None) -> Optional[SiteModel]:
        async with get_async_db_context(db) as db:
            site = (await db.execute(select(Site).where(Site.slug == slug))).scalars().first()
            return SiteModel.model_validate(site) if site else None

    async def get_sites_by_user_id(self, user_id: str, db: Optional[AsyncSession] = None) -> list[SiteModel]:
        async with get_async_db_context(db) as db:
            result = await db.execute(
                select(Site).where(Site.user_id == user_id).order_by(Site.updated_at.desc())
            )
            return [SiteModel.model_validate(s) for s in result.scalars().all()]

    async def get_all_sites(self, db: Optional[AsyncSession] = None) -> list[SiteModel]:
        async with get_async_db_context(db) as db:
            result = await db.execute(select(Site).order_by(Site.updated_at.desc()))
            return [SiteModel.model_validate(s) for s in result.scalars().all()]

    async def update_site_by_id(
        self, id: str, updates: dict, db: Optional[AsyncSession] = None
    ) -> Optional[SiteModel]:
        async with get_async_db_context(db) as db:
            site = (await db.execute(select(Site).where(Site.id == id))).scalars().first()
            if not site:
                return None
            for key in ('name', 'slug', 'public', 'files', 'entry_file'):
                if key in updates:
                    setattr(site, key, updates[key])
            site.updated_at = _now()
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                return None
            await db.refresh(site)
            return SiteModel.model_validate(site)

    async def update_site_access(
        self,
        id: str,
        *,
        public: bool,
        access_grants: Optional[list],
        db: Optional[AsyncSession] = None,
    ) -> Optional[SiteModel]:
        """Replace a site's grants and set its public flag in ONE transaction.

        Grants and visibility must never partially commit: a failure after
        writing new grants but before flipping `public` could leave a private
        site readable by newly granted principals. Model helpers each commit
        their own session (session sharing is off by default), so the only way
        to make this atomic is to do both writes here under a single commit.
        """
        from open_webui.models.access_grants import AccessGrant, normalize_access_grants

        async with get_async_db_context(db) as db:
            site = (await db.execute(select(Site).where(Site.id == id))).scalars().first()
            if not site:
                return None
            await db.execute(
                delete(AccessGrant).where(
                    AccessGrant.resource_type == 'site',
                    AccessGrant.resource_id == id,
                )
            )
            for grant in normalize_access_grants(access_grants):
                db.add(
                    AccessGrant(
                        id=str(uuid.uuid4()),
                        resource_type='site',
                        resource_id=id,
                        principal_type=grant['principal_type'],
                        principal_id=grant['principal_id'],
                        permission=grant['permission'],
                        created_at=int(time.time()),
                    )
                )
            site.public = public
            site.updated_at = _now()
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                return None
            except StaleDataError:
                # The site row vanished between our SELECT and the commit
                # (concurrent delete). The whole transaction — including the
                # new grant rows — rolls back, so nothing orphans; report the
                # site as gone.
                await db.rollback()
                return None
            await db.refresh(site)
            return SiteModel.model_validate(site)

    async def delete_site_by_id(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        """Delete a site and its access grants in ONE transaction.

        A crash between the two deletes must not leave grant rows behind for
        a dead site id (inert, but clutter that never expires).
        """
        from open_webui.models.access_grants import AccessGrant

        async with get_async_db_context(db) as db:
            result = await db.execute(delete(Site).where(Site.id == id))
            await db.execute(
                delete(AccessGrant).where(
                    AccessGrant.resource_type == 'site',
                    AccessGrant.resource_id == id,
                )
            )
            await db.commit()
            return result.rowcount > 0


Sites = SitesTable()


class SiteViewsTable:
    async def record_view(
        self,
        site_id: str,
        path: str,
        visitor_key: str,
        is_owner: bool,
        db: Optional[AsyncSession] = None,
    ) -> None:
        async with get_async_db_context(db) as db:
            db.add(
                SiteView(
                    id=str(uuid.uuid4()),
                    site_id=site_id,
                    path=path,
                    visitor_key=visitor_key,
                    is_owner=is_owner,
                    created_at=_now(),
                )
            )
            await db.commit()

    async def list_views(
        self, site_id: str, db: Optional[AsyncSession] = None
    ) -> list[SiteViewModel]:
        """Test/debug helper: every recorded view for a site, oldest first."""
        async with get_async_db_context(db) as db:
            result = await db.execute(
                select(SiteView)
                .where(SiteView.site_id == site_id)
                .order_by(SiteView.created_at.asc())
            )
            return [SiteViewModel.model_validate(v) for v in result.scalars().all()]

    async def get_analytics(
        self,
        site_id: str,
        days: int,
        now_ms: Optional[int] = None,
        db: Optional[AsyncSession] = None,
    ) -> dict:
        """Totals, a zero-filled daily series, and top pages for a time window.

        Owner visits are excluded from every visitor-facing number and reported
        on their own as `owner_views`.

        Day bucketing is integer division on the millisecond timestamp rather
        than a SQL date function, so the identical query runs on SQLite and
        Postgres.
        """
        now_ms = _now() if now_ms is None else now_ms
        day_ms = 86_400_000
        today_idx = now_ms // day_ms
        first_idx = today_idx - (days - 1)
        window_start = first_idx * day_ms

        async with get_async_db_context(db) as db:
            in_window = (SiteView.site_id == site_id, SiteView.created_at >= window_start)
            visitors = (*in_window, SiteView.is_owner.is_(False))

            totals_row = (
                await db.execute(
                    select(
                        func.count(SiteView.id),
                        func.count(func.distinct(SiteView.visitor_key)),
                    ).where(*visitors)
                )
            ).one()
            owner_views = (
                await db.execute(
                    select(func.count(SiteView.id)).where(*in_window, SiteView.is_owner.is_(True))
                )
            ).scalar_one()

            day_idx = (SiteView.created_at / day_ms).label('day_idx')
            rows = (
                await db.execute(
                    select(day_idx, func.count(SiteView.id)).where(*visitors).group_by(day_idx)
                )
            ).all()
            counts = {int(idx): int(n) for idx, n in rows}

            pages = (
                await db.execute(
                    select(SiteView.path, func.count(SiteView.id).label('n'))
                    .where(*visitors)
                    .group_by(SiteView.path)
                    .order_by(func.count(SiteView.id).desc(), SiteView.path.asc())
                    .limit(5)
                )
            ).all()

        series = [
            {
                'day': datetime.fromtimestamp(idx * day_ms / 1000, tz=timezone.utc).strftime('%Y-%m-%d'),
                'views': counts.get(idx, 0),
            }
            for idx in range(first_idx, today_idx + 1)
        ]

        return {
            'days': days,
            'totals': {
                'views': int(totals_row[0]),
                'unique_visitors': int(totals_row[1]),
                'owner_views': int(owner_views),
            },
            'series': series,
            'top_pages': [{'path': p, 'views': int(n)} for p, n in pages],
        }


SiteViews = SiteViewsTable()
