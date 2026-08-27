import time
import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Boolean, Column, JSON, Text, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

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
            await db.refresh(site)
            return SiteModel.model_validate(site)

    async def delete_site_by_id(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            result = await db.execute(delete(Site).where(Site.id == id))
            await db.commit()
            return result.rowcount > 0


Sites = SitesTable()
