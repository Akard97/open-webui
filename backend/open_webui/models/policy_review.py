import re
import time
import uuid
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, Text, JSON, select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.internal.db import Base, get_async_db_context


def _now() -> int:
    return int(time.time_ns())


def _next_label(label: str) -> str:
    # Mirror checklist.ts nextLabel: v2.0 -> v2.1
    m = re.match(r'^v(\d+)\.(\d+)$', label or '')
    if not m:
        return f'{label}.1'
    return f'v{m.group(1)}.{int(m.group(2)) + 1}'


# ──────────────────────────── Tables ────────────────────────────


class PolicyChecklistVersion(Base):
    __tablename__ = 'policy_checklist_version'

    id = Column(Text, primary_key=True, unique=True)
    label = Column(Text)
    status = Column(Text)  # active | draft | archived
    data = Column(JSON, nullable=True)
    published_at = Column(BigInteger, nullable=True)
    published_by_id = Column(Text, nullable=True)
    published_by_name = Column(Text, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class PolicyReview(Base):
    __tablename__ = 'policy_review'

    id = Column(Text, primary_key=True, unique=True)
    policy_meta = Column(JSON, nullable=True)
    checklist_version_id = Column(Text)
    checklist_snapshot = Column(JSON, nullable=True)
    results = Column(JSON, nullable=True)
    status = Column(Text)  # draft | pending | approved | rejected
    approval = Column(JSON, nullable=True)
    strengths = Column(JSON, nullable=True)
    created_by_id = Column(Text, nullable=True)
    created_by_name = Column(Text)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class PolicyLibraryEntry(Base):
    __tablename__ = 'policy_library'

    id = Column(Text, primary_key=True, unique=True)
    code = Column(Text, unique=True)
    data = Column(JSON, nullable=True)
    source_review_id = Column(Text, nullable=True)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


class PolicyAuditEntry(Base):
    __tablename__ = 'policy_audit'

    id = Column(Text, primary_key=True, unique=True)
    entity_type = Column(Text)
    entity_id = Column(Text)
    action = Column(Text)
    actor_id = Column(Text, nullable=True)
    actor_name = Column(Text)
    detail = Column(JSON, nullable=True)
    created_at = Column(BigInteger)


class PolicyDocument(Base):
    __tablename__ = 'policy_document'

    id = Column(Text, primary_key=True, unique=True)
    owner_type = Column(Text)  # 'review' | 'library'
    owner_id = Column(Text)    # policy_review.id  OR  policy_library.code
    filename = Column(Text)
    content_type = Column(Text, nullable=True)
    size = Column(BigInteger, nullable=True)
    storage_path = Column(Text)
    text = Column(Text, nullable=True)  # extracted plain text (Phase 3 input)
    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


# ──────────────────────────── Pydantic ────────────────────────────


class ChecklistVersionModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    label: str
    status: str
    data: Optional[dict] = None
    published_at: Optional[int] = None
    published_by_id: Optional[str] = None
    published_by_name: Optional[str] = None
    created_at: int
    updated_at: int


class ReviewModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    policy_meta: Optional[dict] = None
    checklist_version_id: str
    checklist_snapshot: Optional[dict] = None
    results: Optional[dict] = None
    status: str
    approval: Optional[dict] = None
    strengths: Optional[list] = None
    created_by_id: Optional[str] = None
    created_by_name: str
    created_at: int
    updated_at: int


class LibraryEntryModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    data: Optional[dict] = None
    source_review_id: Optional[str] = None
    created_at: int
    updated_at: int


class AuditEntryModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entity_type: str
    entity_id: str
    action: str
    actor_id: Optional[str] = None
    actor_name: str
    detail: Optional[dict] = None
    created_at: int


class PolicyDocumentModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    owner_type: str
    owner_id: str
    filename: str
    content_type: Optional[str] = None
    size: Optional[int] = None
    storage_path: str
    text: Optional[str] = None
    created_at: int
    updated_at: int


# ──────────────────────────── DAO: checklist versions ────────────────────────────


class PolicyChecklistVersionTable:
    async def get_active(self, db: Optional[AsyncSession] = None) -> Optional[ChecklistVersionModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyChecklistVersion).filter_by(status='active'))
            row = res.scalars().first()
            return ChecklistVersionModel.model_validate(row) if row else None

    async def get_draft(self, db: Optional[AsyncSession] = None) -> Optional[ChecklistVersionModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyChecklistVersion).filter_by(status='draft'))
            row = res.scalars().first()
            return ChecklistVersionModel.model_validate(row) if row else None

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[ChecklistVersionModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyChecklistVersion).filter_by(id=id))
            row = res.scalars().first()
            return ChecklistVersionModel.model_validate(row) if row else None

    async def list_versions(self, db: Optional[AsyncSession] = None) -> list[ChecklistVersionModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyChecklistVersion).order_by(PolicyChecklistVersion.created_at.desc()))
            return [ChecklistVersionModel.model_validate(r) for r in res.scalars().all()]

    async def insert_version(
        self,
        label: str,
        status: str,
        data: dict,
        published_by_id: Optional[str],
        published_by_name: Optional[str],
        published_at: Optional[int] = None,
        db: Optional[AsyncSession] = None,
    ) -> ChecklistVersionModel:
        async with get_async_db_context(db) as db:
            row = PolicyChecklistVersion(
                id=str(uuid.uuid4()),
                label=label,
                status=status,
                data=data,
                published_at=published_at if published_at is not None else (_now() if status == 'active' else None),
                published_by_id=published_by_id,
                published_by_name=published_by_name,
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return ChecklistVersionModel.model_validate(row)

    async def start_draft(self, db: Optional[AsyncSession] = None) -> Optional[ChecklistVersionModel]:
        # Clone the active version's data into a new draft (mirrors checklist.ts cloneAsDraft).
        async with get_async_db_context(db) as db:
            existing = await self.get_draft(db=db)
            if existing:
                return existing
            res = await db.execute(select(PolicyChecklistVersion).filter_by(status='active'))
            active = res.scalars().first()
            if not active:
                return None
            row = PolicyChecklistVersion(
                id=str(uuid.uuid4()),
                label=active.label,
                status='draft',
                data=dict(active.data or {}),
                published_at=None,
                published_by_id=None,
                published_by_name=None,
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return ChecklistVersionModel.model_validate(row)

    async def save_draft(self, data: dict, db: Optional[AsyncSession] = None) -> Optional[ChecklistVersionModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyChecklistVersion).filter_by(status='draft'))
            row = res.scalars().first()
            if not row:
                return None
            row.data = data
            row.updated_at = _now()
            await db.commit()
            await db.refresh(row)
            return ChecklistVersionModel.model_validate(row)

    async def discard_draft(self, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            await db.execute(delete(PolicyChecklistVersion).filter_by(status='draft'))
            await db.commit()
            return True

    async def publish_draft(self, by_id: Optional[str], by_name: str, db: Optional[AsyncSession] = None) -> Optional[ChecklistVersionModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyChecklistVersion).filter_by(status='draft'))
            draft = res.scalars().first()
            if not draft:
                return None
            res2 = await db.execute(select(PolicyChecklistVersion).filter_by(status='active'))
            active = res2.scalars().first()
            new_label = _next_label(active.label if active else draft.label)
            if active:
                active.status = 'archived'
                active.updated_at = _now()
            draft.status = 'active'
            draft.label = new_label
            draft.published_at = _now()
            draft.published_by_id = by_id
            draft.published_by_name = by_name
            draft.updated_at = _now()
            await db.commit()
            await db.refresh(draft)
            return ChecklistVersionModel.model_validate(draft)

    async def activate_version(self, id: str, by_id: Optional[str], by_name: str, db: Optional[AsyncSession] = None):
        # Audit-safe revert: re-activate an ARCHIVED version (archives the current active,
        # promotes the target). The target keeps its label; nothing is deleted; in-flight
        # review snapshots are untouched. Returns: None=not found, False=not archived, model=ok.
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyChecklistVersion).filter_by(id=id))
            target = res.scalars().first()
            if not target:
                return None
            if target.status != 'archived':
                return False
            res2 = await db.execute(select(PolicyChecklistVersion).filter_by(status='active'))
            current = res2.scalars().first()
            if current and current.id != target.id:
                current.status = 'archived'
                current.updated_at = _now()
            target.status = 'active'
            target.published_at = _now()
            target.published_by_id = by_id
            target.published_by_name = by_name
            target.updated_at = _now()  # label intentionally left unchanged
            await db.commit()
            await db.refresh(target)
            return ChecklistVersionModel.model_validate(target)


# ──────────────────────────── DAO: reviews ────────────────────────────


class PolicyReviewTable:
    async def insert_review(
        self,
        created_by_id: Optional[str],
        created_by_name: str,
        policy_meta: dict,
        active_version: ChecklistVersionModel,
        results: Optional[dict] = None,
        status: str = 'draft',
        approval: Optional[dict] = None,
        strengths: Optional[list] = None,
        db: Optional[AsyncSession] = None,
    ) -> ReviewModel:
        async with get_async_db_context(db) as db:
            row = PolicyReview(
                id=str(uuid.uuid4()),
                policy_meta=policy_meta,
                checklist_version_id=active_version.id,
                checklist_snapshot=dict(active_version.data or {}),
                results=results or {},
                status=status,
                approval=approval or {'status': 'idle', 'sentAt': None, 'decidedAt': None, 'decidedBy': None, 'note': ''},
                strengths=strengths or [],
                created_by_id=created_by_id,
                created_by_name=created_by_name,
                created_at=_now(),
                updated_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return ReviewModel.model_validate(row)

    async def get_by_id(self, id: str, db: Optional[AsyncSession] = None) -> Optional[ReviewModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyReview).filter_by(id=id))
            row = res.scalars().first()
            return ReviewModel.model_validate(row) if row else None

    async def list_by_creator(self, user_id: str, db: Optional[AsyncSession] = None) -> list[ReviewModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyReview).filter_by(created_by_id=user_id).order_by(PolicyReview.created_at.desc()))
            return [ReviewModel.model_validate(r) for r in res.scalars().all()]

    async def list_by_status(self, status: str, db: Optional[AsyncSession] = None) -> list[ReviewModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyReview).filter_by(status=status).order_by(PolicyReview.created_at.desc()))
            return [ReviewModel.model_validate(r) for r in res.scalars().all()]

    async def update_fields(self, id: str, fields: dict, db: Optional[AsyncSession] = None) -> Optional[ReviewModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyReview).filter_by(id=id))
            row = res.scalars().first()
            if not row:
                return None
            for key, value in fields.items():
                setattr(row, key, value)
            row.updated_at = _now()
            await db.commit()
            await db.refresh(row)
            return ReviewModel.model_validate(row)

    async def delete(self, id: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyReview).filter_by(id=id))
            if not res.scalars().first():
                return False
            await db.execute(delete(PolicyReview).filter_by(id=id))
            await db.commit()
            return True


# ──────────────────────────── DAO: library ────────────────────────────


class PolicyLibraryTable:
    async def list_all(self, db: Optional[AsyncSession] = None) -> list[LibraryEntryModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyLibraryEntry).order_by(PolicyLibraryEntry.updated_at.desc()))
            return [LibraryEntryModel.model_validate(r) for r in res.scalars().all()]

    async def get_by_code(self, code: str, db: Optional[AsyncSession] = None) -> Optional[LibraryEntryModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyLibraryEntry).filter_by(code=code))
            row = res.scalars().first()
            return LibraryEntryModel.model_validate(row) if row else None

    async def upsert(self, code: str, data: dict, source_review_id: Optional[str], db: Optional[AsyncSession] = None) -> LibraryEntryModel:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyLibraryEntry).filter_by(code=code))
            row = res.scalars().first()
            if row:
                row.data = data
                row.source_review_id = source_review_id
                row.updated_at = _now()
            else:
                row = PolicyLibraryEntry(
                    id=str(uuid.uuid4()),
                    code=code,
                    data=data,
                    source_review_id=source_review_id,
                    created_at=_now(),
                    updated_at=_now(),
                )
                db.add(row)
            await db.commit()
            await db.refresh(row)
            return LibraryEntryModel.model_validate(row)

    async def delete_by_code(self, code: str, db: Optional[AsyncSession] = None) -> bool:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyLibraryEntry).filter_by(code=code))
            if not res.scalars().first():
                return False
            await db.execute(delete(PolicyLibraryEntry).filter_by(code=code))
            await db.commit()
            return True


# ──────────────────────────── DAO: audit ────────────────────────────


class PolicyAuditTable:
    async def insert(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: Optional[str],
        actor_name: str,
        detail: Optional[dict],
        db: Optional[AsyncSession] = None,
    ) -> AuditEntryModel:
        async with get_async_db_context(db) as db:
            row = PolicyAuditEntry(
                id=str(uuid.uuid4()),
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                actor_id=actor_id,
                actor_name=actor_name,
                detail=detail,
                created_at=_now(),
            )
            db.add(row)
            await db.commit()
            await db.refresh(row)
            return AuditEntryModel.model_validate(row)

    async def list_for(self, entity_type: str, entity_id: str, db: Optional[AsyncSession] = None) -> list[AuditEntryModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(PolicyAuditEntry)
                .filter_by(entity_type=entity_type, entity_id=entity_id)
                .order_by(PolicyAuditEntry.created_at.asc())
            )
            return [AuditEntryModel.model_validate(r) for r in res.scalars().all()]


# ──────────────────────────── DAO: documents ────────────────────────────


class PolicyDocumentTable:
    async def upsert(
        self,
        owner_type: str,
        owner_id: str,
        filename: str,
        content_type: Optional[str],
        size: Optional[int],
        storage_path: str,
        text: Optional[str],
        db: Optional[AsyncSession] = None,
    ) -> PolicyDocumentModel:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(PolicyDocument).filter_by(owner_type=owner_type, owner_id=owner_id)
            )
            row = res.scalars().first()
            if row:
                row.filename = filename
                row.content_type = content_type
                row.size = size
                row.storage_path = storage_path
                row.text = text
                row.updated_at = _now()
            else:
                row = PolicyDocument(
                    id=str(uuid.uuid4()),
                    owner_type=owner_type,
                    owner_id=owner_id,
                    filename=filename,
                    content_type=content_type,
                    size=size,
                    storage_path=storage_path,
                    text=text,
                    created_at=_now(),
                    updated_at=_now(),
                )
                db.add(row)
            await db.commit()
            await db.refresh(row)
            return PolicyDocumentModel.model_validate(row)

    async def get(
        self, owner_type: str, owner_id: str, db: Optional[AsyncSession] = None
    ) -> Optional[PolicyDocumentModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(PolicyDocument).filter_by(owner_type=owner_type, owner_id=owner_id)
            )
            row = res.scalars().first()
            return PolicyDocumentModel.model_validate(row) if row else None

    async def delete(
        self, owner_type: str, owner_id: str, db: Optional[AsyncSession] = None
    ) -> Optional[PolicyDocumentModel]:
        # Returns the deleted row (so the caller can remove its binary), or None.
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(PolicyDocument).filter_by(owner_type=owner_type, owner_id=owner_id)
            )
            row = res.scalars().first()
            if not row:
                return None
            model = PolicyDocumentModel.model_validate(row)
            await db.execute(
                delete(PolicyDocument).filter_by(owner_type=owner_type, owner_id=owner_id)
            )
            await db.commit()
            return model

    async def list_all_for_test(self, db: Optional[AsyncSession] = None) -> list[PolicyDocumentModel]:
        async with get_async_db_context(db) as db:
            res = await db.execute(select(PolicyDocument))
            return [PolicyDocumentModel.model_validate(r) for r in res.scalars().all()]


PolicyChecklistVersions = PolicyChecklistVersionTable()
PolicyReviews = PolicyReviewTable()
PolicyLibrary = PolicyLibraryTable()
PolicyAudits = PolicyAuditTable()
PolicyDocuments = PolicyDocumentTable()
