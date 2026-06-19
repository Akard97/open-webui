# Policy Review Backend Phase 2 — Document Upload & Parsing — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make policy-review document upload real — the reviewer attaches a document when creating a review; the server stores it, extracts its text synchronously, keeps both (downloadable original + extracted text for Phase 3), and exposes downloads in the review workspace and the published Library.

**Architecture:** A self-contained `policy_document` table (keyed by `(owner_type, owner_id)`) holds the binary path + extracted text for both a review's working document and a published policy's immutable copy. Storage uses the app's existing `Storage` provider; parsing uses the app's default document `Loader()` (no chat `Files` coupling, no vector DB, no in-app viewer). `POST /reviews` becomes multipart; new endpoints handle replace + download; approve copies the document into a library-owned row.

**Tech Stack:** Python/FastAPI + async SQLAlchemy (backend), Alembic (migration), pytest/httpx (backend tests), SvelteKit/Svelte 5 runes + TypeScript (frontend), vitest (frontend tests).

**Spec:** `docs/superpowers/specs/2026-06-19-policy-review-backend-phase2-design.md`

**Branch:** `osool` (do NOT create a worktree; Phase 1 is already on `osool`).

**Conventions to follow (from Phase 1):**
- Backend tests live in `backend/open_webui/test/policy_review/` and run with `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/` from the `backend/` directory.
- Frontend tests run with `npx vitest run src/lib/components/policy-review/`.
- Router tests spin up a minimal FastAPI app and **monkeypatch seams on the `pr_router` module** (e.g. `pr_router.has_permission`, `pr_router.AUTOFILL_RESULTS_ON_CREATE`). New document helpers are imported INTO the router namespace so tests can monkeypatch them the same way.
- Commit after every task. Commit prefix: `feat(policy-review):` / `test(policy-review):`.

---

## File Structure

**Backend (create):**
- `backend/open_webui/utils/policy_review/documents.py` — upload validation, storage, text extraction, cleanup, copy helpers (the monkeypatchable seams).
- `backend/open_webui/migrations/versions/b2c3d4e5f6a7_add_policy_document_table.py` — the one new table.
- `backend/open_webui/test/policy_review/test_documents.py` — unit tests for `documents.py`.
- `backend/open_webui/test/policy_review/test_router_documents.py` — router tests for upload/replace/download/copy/cleanup.
- `backend/open_webui/test/policy_review/fixtures/` — (optional, generated in-test) — not committed; tests create temp files.

**Backend (modify):**
- `backend/open_webui/models/policy_review.py` — add `PolicyDocument` table + `PolicyDocumentModel` + `PolicyDocumentTable` + `PolicyDocuments` singleton.
- `backend/open_webui/routers/policy_review.py` — multipart `POST /reviews`; new `PUT/GET /reviews/{id}/document`, `GET /library/{code}/document`; approve-copy; delete/unpublish cleanup; audit additions.
- `backend/open_webui/test/policy_review/test_models.py` — DAO round-trip for `policy_document`.
- `backend/open_webui/test/policy_review/test_router_reviews.py` — convert existing creates to multipart + stub document seams.

**Frontend (modify):**
- `src/lib/components/policy-review/lib/types.ts` — `PolicyDocumentMeta`, `PolicyMeta.document?`, `LibraryPolicy.hasDocument?`/`filename?`.
- `src/lib/components/policy-review/lib/api.ts` — multipart `createReviewApi`, `replaceReviewDocumentApi`, `reviewDocumentUrl`/`libraryDocumentUrl`.
- `src/lib/components/policy-review/lib/uploadValidation.ts` — (create) pure validator shared by the view + unit test.
- `src/lib/components/policy-review/lib/store.ts` — `createReview(meta, file)`, `replaceDocument(reviewId, file)`.
- `src/lib/components/policy-review/views/UploadView.svelte` — real dropzone + states.
- `src/lib/components/policy-review/views/ReviewView.svelte` — source download + replace.
- `src/lib/components/policy-review/views/PolicyPopup.svelte` — Library download (the existing inert footer "Download" wired up; `AllPoliciesView` rows stay as-is — see Task 12).

**Frontend (modify tests):**
- `src/lib/components/policy-review/lib/store.test.ts` — `createReview` passes a file; add `replaceDocument`.
- `src/lib/components/policy-review/lib/uploadValidation.test.ts` — (create) validator unit tests.

---

## Task 1: `policy_document` model + DAO

**Files:**
- Modify: `backend/open_webui/models/policy_review.py`
- Test: `backend/open_webui/test/policy_review/test_models.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/open_webui/test/policy_review/test_models.py`:

```python
import pytest

from open_webui.models.policy_review import PolicyDocuments


@pytest.mark.asyncio
async def test_policy_document_upsert_get_delete_roundtrip():
    created = await PolicyDocuments.upsert(
        'review', 'rev-1', 'a.pdf', 'application/pdf', 1234, 'uploads/a.pdf', 'hello text'
    )
    assert created.owner_type == 'review'
    assert created.owner_id == 'rev-1'
    assert created.text == 'hello text'

    got = await PolicyDocuments.get('review', 'rev-1')
    assert got is not None
    assert got.filename == 'a.pdf'
    assert got.storage_path == 'uploads/a.pdf'

    deleted = await PolicyDocuments.delete('review', 'rev-1')
    assert deleted is not None
    assert deleted.storage_path == 'uploads/a.pdf'
    assert await PolicyDocuments.get('review', 'rev-1') is None


@pytest.mark.asyncio
async def test_policy_document_upsert_overwrites_same_owner():
    await PolicyDocuments.upsert('review', 'rev-2', 'old.pdf', 'application/pdf', 1, 'uploads/old.pdf', 'old')
    await PolicyDocuments.upsert('review', 'rev-2', 'new.pdf', 'application/pdf', 2, 'uploads/new.pdf', 'new')

    rows = await PolicyDocuments.list_all_for_test()
    same_owner = [r for r in rows if r.owner_type == 'review' and r.owner_id == 'rev-2']
    assert len(same_owner) == 1  # UNIQUE(owner_type, owner_id) — replace, not duplicate
    assert same_owner[0].filename == 'new.pdf'
    assert same_owner[0].text == 'new'
```

> Note: `list_all_for_test()` is a tiny helper added in Step 3 purely so this test can assert single-row replacement.

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/test_models.py -k policy_document -v`
Expected: FAIL — `ImportError: cannot import name 'PolicyDocuments'`.

- [ ] **Step 3: Add the model, Pydantic schema, DAO, and singleton**

In `backend/open_webui/models/policy_review.py`, add the table class after `class PolicyAuditEntry(Base):` (after line ~80):

```python
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
```

Add the Pydantic model after `class AuditEntryModel(BaseModel):` (after line ~134):

```python
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
```

Add the DAO class after `class PolicyAuditTable:` block (before the singletons at the bottom):

```python
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
```

Add to the singletons block at the bottom (after `PolicyAudits = PolicyAuditTable()`):

```python
PolicyDocuments = PolicyDocumentTable()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/test_models.py -k policy_document -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/models/policy_review.py backend/open_webui/test/policy_review/test_models.py
git commit -m "feat(policy-review): add policy_document model + DAO"
```

---

## Task 2: Alembic migration for `policy_document`

**Files:**
- Create: `backend/open_webui/migrations/versions/b2c3d4e5f6a7_add_policy_document_table.py`

> Tests use `Base.metadata.create_all`, so the table already exists in tests after Task 1. This migration is the **real-deployment** path (the Docker backend runs migrations on start). Mirror the Phase 1 migration exactly.

- [ ] **Step 1: Create the migration file**

Create `backend/open_webui/migrations/versions/b2c3d4e5f6a7_add_policy_document_table.py`:

```python
"""add policy document table

Revision ID: b2c3d4e5f6a7
Revises: 4f7f6e821be6
Create Date: 2026-06-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import open_webui.internal.db


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = '4f7f6e821be6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'policy_document',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('owner_type', sa.Text(), nullable=True),
        sa.Column('owner_id', sa.Text(), nullable=True),
        sa.Column('filename', sa.Text(), nullable=True),
        sa.Column('content_type', sa.Text(), nullable=True),
        sa.Column('size', sa.BigInteger(), nullable=True),
        sa.Column('storage_path', sa.Text(), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('owner_type', 'owner_id', name='uq_policy_document_owner'),
    )
    op.create_index('ix_policy_document_owner', 'policy_document', ['owner_type', 'owner_id'])


def downgrade() -> None:
    op.drop_index('ix_policy_document_owner', table_name='policy_document')
    op.drop_table('policy_document')
```

> The `revision` string may be any unique hex; if you regenerate it, keep `down_revision = '4f7f6e821be6'` (the Phase 1 migration). Confirm it is the current head first: `.venv/Scripts/python.exe -m alembic -c open_webui/alembic.ini heads` should list `4f7f6e821be6`.

- [ ] **Step 2: Verify the migration applies and reverses**

Authoritative check is the real runtime (Docker backend bind-mounts `backend/open_webui` and runs migrations on start). Restart it and confirm the table is created with no errors:

```bash
docker restart osool-ai-open-webui-1
docker logs --since 2m osool-ai-open-webui-1 2>&1 | grep -i "b2c3d4e5f6a7\|policy_document\|error" | head
```

Expected: a log line showing the revision applied (`Running upgrade 4f7f6e821be6 -> b2c3d4e5f6a7`), no errors.

If running locally instead, from `backend/`:
```bash
.venv/Scripts/python.exe -m alembic -c open_webui/alembic.ini upgrade head
.venv/Scripts/python.exe -m alembic -c open_webui/alembic.ini downgrade -1
.venv/Scripts/python.exe -m alembic -c open_webui/alembic.ini upgrade head
```
Expected: each command exits 0; the down/up cycle proves `downgrade()` is correct.

- [ ] **Step 3: Commit**

```bash
git add backend/open_webui/migrations/versions/b2c3d4e5f6a7_add_policy_document_table.py
git commit -m "feat(policy-review): migration for policy_document table"
```

---

## Task 3: `documents.py` helpers (validation, storage, extraction)

**Files:**
- Create: `backend/open_webui/utils/policy_review/documents.py`
- Test: `backend/open_webui/test/policy_review/test_documents.py`

> `backend/open_webui/utils/policy_review/` already exists (it holds `scoring.py` from Phase 1), so no `__init__.py` work is needed.

- [ ] **Step 1: Write the failing tests**

Create `backend/open_webui/test/policy_review/test_documents.py`:

```python
import os
import tempfile

import pytest

from open_webui.utils.policy_review import documents as docs


def test_validate_upload_accepts_allowed_types():
    docs.validate_upload('policy.pdf', 1000)
    docs.validate_upload('policy.DOCX', 1000)  # case-insensitive
    docs.validate_upload('notes.md', 1000)
    docs.validate_upload('plain.txt', 1000)


def test_validate_upload_rejects_unknown_type():
    with pytest.raises(ValueError):
        docs.validate_upload('image.png', 1000)


def test_validate_upload_rejects_empty():
    with pytest.raises(ValueError):
        docs.validate_upload('policy.pdf', 0)


def test_validate_upload_rejects_oversize():
    with pytest.raises(ValueError):
        docs.validate_upload('policy.pdf', docs.MAX_UPLOAD_BYTES + 1)


@pytest.mark.asyncio
async def test_extract_text_reads_txt(tmp_path, monkeypatch):
    # Storage.get_file on the local provider returns the path as-is.
    monkeypatch.setattr(docs.Storage, 'get_file', staticmethod(lambda p: p))
    f = tmp_path / 'doc.txt'
    f.write_text('Hello policy world.', encoding='utf-8')
    text = await docs.extract_text('doc.txt', 'text/plain', str(f))
    assert 'Hello policy world.' in text


@pytest.mark.asyncio
async def test_extract_text_reads_md(tmp_path, monkeypatch):
    monkeypatch.setattr(docs.Storage, 'get_file', staticmethod(lambda p: p))
    f = tmp_path / 'doc.md'
    f.write_text('# Title\n\nBody paragraph.', encoding='utf-8')
    text = await docs.extract_text('doc.md', 'text/markdown', str(f))
    assert 'Body paragraph.' in text


@pytest.mark.asyncio
async def test_extract_text_reads_docx(tmp_path, monkeypatch):
    pytest.importorskip('docx')  # python-docx generates the fixture
    from docx import Document as Docx

    monkeypatch.setattr(docs.Storage, 'get_file', staticmethod(lambda p: p))
    f = tmp_path / 'doc.docx'
    d = Docx()
    d.add_paragraph('Confidentiality clause text.')
    d.save(str(f))
    text = await docs.extract_text(
        'doc.docx',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        str(f),
    )
    assert 'Confidentiality clause text.' in text


@pytest.mark.asyncio
async def test_extract_text_empty_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(docs.Storage, 'get_file', staticmethod(lambda p: p))
    f = tmp_path / 'empty.txt'
    f.write_text('   \n  ', encoding='utf-8')  # whitespace only
    with pytest.raises(ValueError):
        await docs.extract_text('empty.txt', 'text/plain', str(f))


def test_store_get_delete_roundtrip_local(tmp_path, monkeypatch):
    # Point the local storage provider's UPLOAD_DIR at a temp dir.
    import open_webui.storage.provider as provider
    monkeypatch.setattr(provider, 'UPLOAD_DIR', str(tmp_path))

    path = docs.store_upload(b'binary-bytes', 'orig.pdf')
    assert os.path.isfile(docs.Storage.get_file(path))
    assert docs.read_stored(path) == b'binary-bytes'

    copy_path = docs.copy_stored(path, 'orig.pdf')
    assert copy_path != path
    assert docs.read_stored(copy_path) == b'binary-bytes'

    docs.delete_stored(path)
    assert not os.path.isfile(os.path.join(str(tmp_path), os.path.basename(path)))
```

- [ ] **Step 2: Run tests to verify they fail**

Run (from `backend/`): `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/test_documents.py -v`
Expected: FAIL — `ModuleNotFoundError: open_webui.utils.policy_review.documents`.

- [ ] **Step 3: Implement `documents.py`**

Create `backend/open_webui/utils/policy_review/documents.py`:

```python
"""Phase 2 document helpers for Policy Review: validation, storage, and text
extraction. These are the monkeypatchable seams the router imports — router
tests stub `store_upload` / `extract_text` / `delete_stored` / `copy_stored`
so they never touch the filesystem or a real parser.
"""
import io
import os
import uuid
from typing import Optional

from open_webui.storage.provider import Storage
from open_webui.retrieval.loaders.main import Loader

MAX_UPLOAD_MB = int(os.getenv('POLICY_REVIEW_MAX_UPLOAD_MB', '25'))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'md', 'txt'}


def _ext(filename: str) -> str:
    return (os.path.splitext(filename or '')[1][1:] or '').lower()


def validate_upload(filename: str, size: int) -> None:
    """Raise ValueError (→ HTTP 400 in the router) for a disallowed or bad upload."""
    ext = _ext(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f'File type .{ext or "?"} is not supported. Upload a PDF, DOCX, MD, or TXT file.'
        )
    if size <= 0:
        raise ValueError('The file is empty.')
    if size > MAX_UPLOAD_BYTES:
        raise ValueError(f'File exceeds the {MAX_UPLOAD_MB} MB limit.')


def store_upload(contents: bytes, filename: str) -> str:
    """Persist bytes via the configured Storage provider; return the storage path."""
    unique = f'policy_{uuid.uuid4()}_{os.path.basename(filename)}'
    _, path = Storage.upload_file(io.BytesIO(contents), unique, {'OpenWebUI-Policy': 'document'})
    return path


def read_stored(storage_path: str) -> bytes:
    """Read the stored binary back (used by downloads and copy)."""
    with open(Storage.get_file(storage_path), 'rb') as f:
        return f.read()


def copy_stored(storage_path: str, filename: str) -> str:
    """Duplicate a stored binary to a fresh path (used to give the Library its own copy)."""
    return store_upload(read_stored(storage_path), filename)


def delete_stored(storage_path: Optional[str]) -> None:
    """Best-effort delete of a stored binary; never raises."""
    if not storage_path:
        return
    try:
        Storage.delete_file(storage_path)
    except Exception:
        pass


async def extract_text(filename: str, content_type: Optional[str], storage_path: str) -> str:
    """Extract plain text from a stored document using the app's default Loader.

    The default loaders cover pdf/docx/md/txt with no external services, so this
    needs no request/config. Raises ValueError if no text could be extracted.
    """
    local_path = Storage.get_file(storage_path)
    documents = await Loader().aload(filename, content_type or '', local_path)
    text = '\n\n'.join((d.page_content or '') for d in documents).strip()
    if not text:
        raise ValueError('Could not extract any text from this document.')
    return text
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/test_documents.py -v`
Expected: PASS (the docx test may show `SKIPPED` if `python-docx` is not installed; all others PASS).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/utils/policy_review/documents.py backend/open_webui/test/policy_review/test_documents.py
git commit -m "feat(policy-review): document upload/parse helpers"
```

---

## Task 4: Multipart `POST /reviews` + convert existing review tests

**Files:**
- Modify: `backend/open_webui/routers/policy_review.py`
- Test: `backend/open_webui/test/policy_review/test_router_documents.py` (new)
- Modify: `backend/open_webui/test/policy_review/test_router_reviews.py`

- [ ] **Step 1: Write the failing test for create-with-file**

Create `backend/open_webui/test/policy_review/test_router_documents.py`:

```python
import json
from types import SimpleNamespace

import pytest
import pytest_asyncio
import httpx
from httpx import ASGITransport
from fastapi import FastAPI

import open_webui.routers.policy_review as pr_router
from open_webui.utils.auth import get_verified_user
from open_webui.models.policy_review import PolicyChecklistVersions, PolicyDocuments

ACTIVE_DATA = {
    'changeSummary': 'init',
    'themes': [{'id': 'T1', 'name': 'T1', 'weight': 100, 'gate': True, 'threshold': 85}],
    'sections': [{'id': 'S1', 'theme': 'T1', 'items': [{'id': 'S1-1', 'assessment': 'auto'}]}],
    'verdictBands': {'approved': 85, 'conditional': 70},
    'standards': [],
}
META = {'name': 'Test Policy', 'code': 'C-TEST', 'version': 'v1', 'owner': 'O',
        'reviewer': 'R', 'reviewDate': 'd', 'pages': 1, 'filename': ''}


class _AsyncReturn:
    def __init__(self, value):
        self.value = value

    async def __call__(self, *args, **kwargs):
        return self.value


def _make_app(user):
    app = FastAPI()
    app.state.config = SimpleNamespace(USER_PERMISSIONS={})
    app.include_router(pr_router.router, prefix='/api/v1/policy')
    app.dependency_overrides[get_verified_user] = lambda: user
    return app


def _client_keys(monkeypatch, *, user, keys=()):
    granted = set(keys)

    async def _hp(user_id, key, permissions, db=None):
        return key.split('.')[-1] in granted

    monkeypatch.setattr(pr_router, 'has_permission', _hp)
    return httpx.AsyncClient(transport=ASGITransport(app=_make_app(user)), base_url='http://test')


@pytest_asyncio.fixture(autouse=True)
async def _seed_active():
    await PolicyChecklistVersions.insert_version('v2.0', 'active', ACTIVE_DATA, None, 'OE')


class FakeStorage:
    """In-memory storage stand-in: store/read/delete bytes by a fake path."""
    def __init__(self):
        self.blobs = {}
        self._n = 0

    def store(self, contents, filename):
        self._n += 1
        path = f'fake://{self._n}-{filename}'
        self.blobs[path] = contents
        return path

    def read(self, path):
        return self.blobs[path]

    def delete(self, path):
        self.blobs.pop(path, None)


@pytest.fixture
def fake_docs(monkeypatch):
    """Wire the router's document seams to an in-memory FakeStorage + canned parse."""
    fs = FakeStorage()
    monkeypatch.setattr(pr_router, 'validate_upload', lambda filename, size: None)
    monkeypatch.setattr(pr_router, 'store_upload', lambda contents, filename: fs.store(contents, filename))
    monkeypatch.setattr(pr_router, 'read_stored', lambda path: fs.read(path))
    monkeypatch.setattr(pr_router, 'copy_stored', lambda path, filename: fs.store(fs.read(path), filename))
    monkeypatch.setattr(pr_router, 'delete_stored', lambda path: fs.delete(path))

    async def _extract(filename, content_type, path):
        return f'extracted::{filename}'

    monkeypatch.setattr(pr_router, 'extract_text', _extract)
    return fs


def _upload(meta=META):
    return {
        'files': {'file': ('policy.pdf', b'%PDF-1.4 dummy', 'application/pdf')},
        'data': {'meta': json.dumps(meta)},
    }


@pytest.mark.asyncio
async def test_create_with_file_stores_document(monkeypatch, fake_docs):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        res = await c.post('/api/v1/policy/reviews', **_upload())
        assert res.status_code == 200
        body = res.json()
        rid = body['id']
        # Light descriptor on the review.
        assert body['policy_meta']['document']['filename'] == 'policy.pdf'
        assert body['policy_meta']['filename'] == 'policy.pdf'

    doc = await PolicyDocuments.get('review', rid)
    assert doc is not None
    assert doc.text == 'extracted::policy.pdf'
    assert doc.storage_path in fake_docs.blobs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/test_router_documents.py -k create_with_file -v`
Expected: FAIL — the current `POST /reviews` expects JSON (`ReviewCreateForm`), so a multipart post returns `422`, and `pr_router.store_upload` does not exist to monkeypatch (AttributeError).

- [ ] **Step 3: Wire the document seams into the router and rewrite `POST /reviews`**

In `backend/open_webui/routers/policy_review.py`:

Add to the imports at the top (after the existing `from fastapi import ...` line, change it to include the new names, and add the responses + helpers imports):

```python
import json
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import Response

from open_webui.utils.policy_review.documents import (
    validate_upload,
    store_upload,
    read_stored,
    copy_stored,
    delete_stored,
    extract_text,
)
from open_webui.models.policy_review import (
    PolicyChecklistVersions,
    PolicyReviews,
    PolicyLibrary,
    PolicyAudits,
    PolicyDocuments,
)
```

> Keep the existing `import os`, `import time`, `from typing import Optional`, etc. Just ensure `json`, the FastAPI `File`/`Form`/`UploadFile`, `Response`, the `documents` helpers, and `PolicyDocuments` are all imported. Remove the now-unused `ReviewCreateForm` only after Step 3 (it is replaced).

Replace the existing `create_review` handler (currently `@router.post('/reviews')` taking `ReviewCreateForm`) with:

```python
@router.post('/reviews')
async def create_review(
    request: Request,
    file: UploadFile = File(...),
    meta: str = Form(...),
    strengths: Optional[str] = Form(None),
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require(request, user, 'policy_checker', db)

    try:
        policy_meta = json.loads(meta)
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid metadata.')
    strengths_list: list = []
    if strengths:
        try:
            strengths_list = json.loads(strengths)
        except json.JSONDecodeError:
            strengths_list = []

    active = await PolicyChecklistVersions.get_active(db=db)
    if not active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='No active checklist version.')

    contents = await file.read()
    try:
        validate_upload(file.filename, len(contents))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    storage_path = store_upload(contents, file.filename)
    try:
        text = await extract_text(file.filename, file.content_type, storage_path)
    except Exception:
        delete_stored(storage_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Could not extract text from this document.',
        )

    policy_meta['document'] = {
        'filename': file.filename,
        'contentType': file.content_type,
        'size': len(contents),
    }
    policy_meta['filename'] = file.filename

    review = await PolicyReviews.insert_review(
        created_by_id=user.id,
        created_by_name=user.name,
        policy_meta=policy_meta,
        active_version=active,
        results=_autofilled_results(active.data) if AUTOFILL_RESULTS_ON_CREATE else None,
        strengths=strengths_list,
        db=db,
    )
    try:
        await PolicyDocuments.upsert(
            'review', review.id, file.filename, file.content_type, len(contents), storage_path, text, db=db
        )
    except Exception:
        await PolicyReviews.delete(review.id, db=db)
        delete_stored(storage_path)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='Failed to store document.')

    await PolicyAudits.insert('review', review.id, 'created', user.id, user.name, None, db=db)
    await PolicyAudits.insert('review', review.id, 'document_uploaded', user.id, user.name, {'filename': file.filename}, db=db)
    return review
```

Delete the now-unused `class ReviewCreateForm(BaseModel):` definition.

- [ ] **Step 4: Run the new create test to verify it passes**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/test_router_documents.py -k create_with_file -v`
Expected: PASS.

- [ ] **Step 5: Convert existing review tests to multipart**

The signature change breaks every create in `test_router_reviews.py`. Make these edits:

Add to the imports at the top of `backend/open_webui/test/policy_review/test_router_reviews.py`:

```python
import json
```

Add a module-level autouse fixture that stubs the document seams (so lifecycle tests never touch the filesystem) — place it right after the `_seed_active` fixture:

```python
@pytest_asyncio.fixture(autouse=True)
async def _stub_document_io(monkeypatch):
    monkeypatch.setattr(pr_router, 'validate_upload', lambda filename, size: None)
    monkeypatch.setattr(pr_router, 'store_upload', lambda contents, filename: f'fake://{filename}')
    monkeypatch.setattr(pr_router, 'read_stored', lambda path: b'bytes')
    monkeypatch.setattr(pr_router, 'copy_stored', lambda path, filename: f'fake-copy://{filename}')
    monkeypatch.setattr(pr_router, 'delete_stored', lambda path: None)

    async def _extract(filename, content_type, path):
        return 'stub text'

    monkeypatch.setattr(pr_router, 'extract_text', _extract)
```

Replace the existing `_create` helper with a multipart version:

```python
async def _create(c, **meta_over):
    meta = {**META, **meta_over}
    res = await c.post(
        '/api/v1/policy/reviews',
        files={'file': ('policy.pdf', b'%PDF-1.4 dummy', 'application/pdf')},
        data={'meta': json.dumps(meta)},
    )
    return res.json()['id']
```

Replace every inline create that uses the JSON body. Run this exact replacement across the file (`replace_all`):

- Find: `(await c.post('/api/v1/policy/reviews', json={'policy_meta': META})).json()['id']`
- Replace: `await _create(c)`

Then fix the two special cases that keep the response object:

In `test_full_lifecycle_create_submit_approve_publishes`, replace:
```python
        created = await c.post('/api/v1/policy/reviews', json={'policy_meta': META})
```
with:
```python
        created = await c.post(
            '/api/v1/policy/reviews',
            files={'file': ('policy.pdf', b'%PDF-1.4 dummy', 'application/pdf')},
            data={'meta': json.dumps(META)},
        )
```

In `test_non_reviewer_cannot_create`, replace:
```python
        res = await c.post('/api/v1/policy/reviews', json={'policy_meta': META})
```
with:
```python
        res = await c.post(
            '/api/v1/policy/reviews',
            files={'file': ('policy.pdf', b'%PDF-1.4 dummy', 'application/pdf')},
            data={'meta': json.dumps(META)},
        )
```

> `test_non_reviewer_cannot_create` still asserts `401`: `_require` runs before any file handling, so a permission failure short-circuits even though a file is attached.

- [ ] **Step 6: Run the full reviews + documents suites**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/test_router_reviews.py open_webui/test/policy_review/test_router_documents.py -v`
Expected: PASS (all existing review tests green under multipart + the new create test).

- [ ] **Step 7: Commit**

```bash
git add backend/open_webui/routers/policy_review.py backend/open_webui/test/policy_review/test_router_reviews.py backend/open_webui/test/policy_review/test_router_documents.py
git commit -m "feat(policy-review): multipart create with document upload + parse"
```

---

## Task 5: Replace-document endpoint

**Files:**
- Modify: `backend/open_webui/routers/policy_review.py`
- Test: `backend/open_webui/test/policy_review/test_router_documents.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_router_documents.py`:

```python
@pytest.mark.asyncio
async def test_replace_document_swaps_binary(monkeypatch, fake_docs):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = (await c.post('/api/v1/policy/reviews', **_upload())).json()['id']
        old = await PolicyDocuments.get('review', rid)

        res = await c.put(
            f'/api/v1/policy/reviews/{rid}/document',
            files={'file': ('v2.pdf', b'%PDF-1.4 second', 'application/pdf')},
            data={},
        )
        assert res.status_code == 200

    new = await PolicyDocuments.get('review', rid)
    assert new.filename == 'v2.pdf'
    assert new.storage_path != old.storage_path
    assert old.storage_path not in fake_docs.blobs  # old binary deleted


@pytest.mark.asyncio
async def test_replace_document_reopens_rejected(monkeypatch, fake_docs):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = (await c.post('/api/v1/policy/reviews', **_upload())).json()['id']
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        await c.post(f'/api/v1/policy/reviews/{rid}/submit')
    async with _client_keys(monkeypatch, user=approver, keys={'policy_approver'}) as c:
        await c.post(f'/api/v1/policy/reviews/{rid}/reject', json={'note': 'fix it'})
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        res = await c.put(
            f'/api/v1/policy/reviews/{rid}/document',
            files={'file': ('fixed.pdf', b'%PDF-1.4 fixed', 'application/pdf')},
            data={},
        )
        assert res.status_code == 200
        assert res.json()['status'] == 'draft'  # editing a returned review reopens it


@pytest.mark.asyncio
async def test_replace_document_forbidden_when_pending(monkeypatch, fake_docs):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = (await c.post('/api/v1/policy/reviews', **_upload())).json()['id']
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        await c.post(f'/api/v1/policy/reviews/{rid}/submit')  # now pending
        res = await c.put(
            f'/api/v1/policy/reviews/{rid}/document',
            files={'file': ('x.pdf', b'%PDF-1.4 x', 'application/pdf')},
            data={},
        )
    assert res.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/test_router_documents.py -k replace -v`
Expected: FAIL — `405 Method Not Allowed` (no `PUT /reviews/{id}/document` route yet).

- [ ] **Step 3: Add the replace endpoint**

In `backend/open_webui/routers/policy_review.py`, add after the `update_review_results` handler:

```python
@router.put('/reviews/{review_id}/document')
async def replace_review_document(
    request: Request,
    review_id: str,
    file: UploadFile = File(...),
    user=Depends(get_verified_user),
    db: AsyncSession = Depends(get_async_session),
):
    await _require(request, user, 'policy_checker', db)
    review = await _load_owned_or_403(review_id, user, db)
    if review.status not in ('draft', 'rejected'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Review is locked.')

    contents = await file.read()
    try:
        validate_upload(file.filename, len(contents))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    storage_path = store_upload(contents, file.filename)
    try:
        text = await extract_text(file.filename, file.content_type, storage_path)
    except Exception:
        delete_stored(storage_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Could not extract text from this document.',
        )

    old = await PolicyDocuments.get('review', review_id, db=db)
    await PolicyDocuments.upsert(
        'review', review_id, file.filename, file.content_type, len(contents), storage_path, text, db=db
    )
    if old and old.storage_path != storage_path:
        delete_stored(old.storage_path)

    meta = {**(review.policy_meta or {})}
    meta['document'] = {'filename': file.filename, 'contentType': file.content_type, 'size': len(contents)}
    meta['filename'] = file.filename
    fields = {'policy_meta': meta}
    if review.status == 'rejected':
        fields['status'] = 'draft'  # editing a returned review reopens it
        await PolicyAudits.insert('review', review_id, 'reopened', user.id, user.name, None, db=db)

    updated = await PolicyReviews.update_fields(review_id, fields, db=db)
    await PolicyAudits.insert('review', review_id, 'document_replaced', user.id, user.name, {'filename': file.filename}, db=db)
    return updated
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/test_router_documents.py -k replace -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/policy_review.py backend/open_webui/test/policy_review/test_router_documents.py
git commit -m "feat(policy-review): replace-document endpoint"
```

---

## Task 6: Download endpoints (review-scoped + library)

**Files:**
- Modify: `backend/open_webui/routers/policy_review.py`
- Test: `backend/open_webui/test/policy_review/test_router_documents.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_router_documents.py`:

```python
@pytest.mark.asyncio
async def test_download_review_document_access_matrix(monkeypatch, fake_docs):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')
    admin = SimpleNamespace(id='ad1', role='admin', name='Admin', email='ad@x.io')
    stranger = SimpleNamespace(id='str1', role='user', name='Stranger', email='s@x.io')

    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = (await c.post('/api/v1/policy/reviews', **_upload())).json()['id']
        owner_dl = await c.get(f'/api/v1/policy/reviews/{rid}/document')
        assert owner_dl.status_code == 200
        assert owner_dl.content == b'%PDF-1.4 dummy'
        assert 'attachment' in owner_dl.headers['content-disposition']

    async with _client_keys(monkeypatch, user=approver, keys={'policy_approver'}) as c:
        assert (await c.get(f'/api/v1/policy/reviews/{rid}/document')).status_code == 200
    async with _client_keys(monkeypatch, user=admin, keys=set()) as c:
        assert (await c.get(f'/api/v1/policy/reviews/{rid}/document')).status_code == 200
    async with _client_keys(monkeypatch, user=stranger, keys=set()) as c:
        assert (await c.get(f'/api/v1/policy/reviews/{rid}/document')).status_code == 403


@pytest.mark.asyncio
async def test_download_review_document_404_when_absent(monkeypatch, fake_docs):
    admin = SimpleNamespace(id='ad1', role='admin', name='Admin', email='ad@x.io')
    # Seed a review row with no document (insert directly via the reviews DAO).
    from open_webui.models.policy_review import PolicyReviews
    active = await PolicyChecklistVersions.get_active()
    review = await PolicyReviews.insert_review(
        created_by_id='ad1', created_by_name='Admin', policy_meta=META, active_version=active
    )
    async with _client_keys(monkeypatch, user=admin, keys=set()) as c:
        res = await c.get(f'/api/v1/policy/reviews/{review.id}/document')
    assert res.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/test_router_documents.py -k download -v`
Expected: FAIL — `404`/`405` (no download routes yet).

- [ ] **Step 3: Add the download endpoints + a shared response helper**

In `backend/open_webui/routers/policy_review.py`, add a helper near the top (after `_audit_now`):

```python
def _document_response(doc) -> Response:
    data = read_stored(doc.storage_path)
    return Response(
        content=data,
        media_type=doc.content_type or 'application/octet-stream',
        headers={'Content-Disposition': f'attachment; filename="{doc.filename}"'},
    )
```

Add the review-scoped download after the `get_review` handler:

```python
@router.get('/reviews/{review_id}/document')
async def download_review_document(
    request: Request, review_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    is_approver = user.role == 'admin' or await has_permission(
        user.id, 'features.policy_approver', request.app.state.config.USER_PERMISSIONS, db=db
    )
    await _load_owned_or_403(review_id, user, db, approver_ok=is_approver)
    doc = await PolicyDocuments.get('review', review_id, db=db)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return _document_response(doc)
```

Add the library download in the library section (after `get_library_entry`):

```python
@router.get('/library/{code}/document')
async def download_library_document(
    request: Request, code: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    doc = await PolicyDocuments.get('library', code, db=db)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return _document_response(doc)
```

> Route ordering: define `GET /reviews/{review_id}/document` after `GET /reviews/{review_id}` — FastAPI matches the more specific static suffix correctly, but keep the document route grouped with the other `/reviews/{id}/...` routes. Likewise `GET /library/{code}/document` after `GET /library/{code}`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/test_router_documents.py -k download -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/policy_review.py backend/open_webui/test/policy_review/test_router_documents.py
git commit -m "feat(policy-review): review + library document download endpoints"
```

---

## Task 7: Approve copies document to Library + delete/unpublish cleanup

**Files:**
- Modify: `backend/open_webui/routers/policy_review.py`
- Test: `backend/open_webui/test/policy_review/test_router_documents.py`

- [ ] **Step 1: Write the failing tests**

Append to `test_router_documents.py`:

```python
async def _approve_flow(monkeypatch, fake_docs):
    """Create -> resolve -> submit -> approve; returns the review id."""
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')
    async with _client_keys(monkeypatch, user=reviewer, keys={'policy_checker'}) as c:
        rid = (await c.post('/api/v1/policy/reviews', **_upload())).json()['id']
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        await c.post(f'/api/v1/policy/reviews/{rid}/submit')
    async with _client_keys(monkeypatch, user=approver, keys={'policy_approver'}) as c:
        await c.post(f'/api/v1/policy/reviews/{rid}/approve', json={'note': 'ok'})
    return rid


@pytest.mark.asyncio
async def test_approve_copies_document_to_library(monkeypatch, fake_docs):
    await _approve_flow(monkeypatch, fake_docs)
    lib_doc = await PolicyDocuments.get('library', 'C-TEST')
    assert lib_doc is not None
    assert lib_doc.filename == 'policy.pdf'

    entry = await PolicyLibrary.get_by_code('C-TEST')
    assert entry.data['hasDocument'] is True
    assert entry.data['filename'] == 'policy.pdf'

    # Library download works for any verified user (open access).
    anyone = SimpleNamespace(id='u9', role='user', name='Anyone', email='u9@x.io')
    async with _client_keys(monkeypatch, user=anyone, keys=set()) as c:
        dl = await c.get('/api/v1/policy/library/C-TEST/document')
        assert dl.status_code == 200
        assert dl.content == b'%PDF-1.4 dummy'


@pytest.mark.asyncio
async def test_library_download_survives_review_deletion(monkeypatch, fake_docs):
    rid = await _approve_flow(monkeypatch, fake_docs)
    review_doc = await PolicyDocuments.get('review', rid)

    admin = SimpleNamespace(id='ad1', role='admin', name='Admin', email='ad@x.io')
    async with _client_keys(monkeypatch, user=admin, keys=set()) as c:
        assert (await c.delete(f'/api/v1/policy/reviews/{rid}')).status_code == 200

    # The review document + its binary are gone, but the library copy remains.
    assert await PolicyDocuments.get('review', rid) is None
    assert review_doc.storage_path not in fake_docs.blobs
    assert await PolicyDocuments.get('library', 'C-TEST') is not None
    async with _client_keys(monkeypatch, user=admin, keys=set()) as c:
        assert (await c.get('/api/v1/policy/library/C-TEST/document')).status_code == 200


@pytest.mark.asyncio
async def test_unpublish_removes_library_document(monkeypatch, fake_docs):
    await _approve_flow(monkeypatch, fake_docs)
    lib_doc = await PolicyDocuments.get('library', 'C-TEST')
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')
    async with _client_keys(monkeypatch, user=approver, keys={'policy_approver'}) as c:
        assert (await c.delete('/api/v1/policy/library/C-TEST')).status_code == 200
    assert await PolicyDocuments.get('library', 'C-TEST') is None
    assert lib_doc.storage_path not in fake_docs.blobs
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/test_router_documents.py -k "approve_copies or survives or unpublish_removes" -v`
Expected: FAIL — the library copy is never created; `PolicyDocuments.get('library', ...)` is `None`.

- [ ] **Step 3: Wire copy-on-approve + cleanup on delete/unpublish**

In `approve_review`, after the `await PolicyLibrary.upsert(...)` line and before the audit inserts, add the document copy. First build the `library_data` dict as today, then insert this block right before `await PolicyLibrary.upsert(...)` is called so `hasDocument`/`filename` are part of the upserted data:

Replace the existing tail of `approve_review` (from the `library_data = {...}` assignment through the `PolicyLibrary.upsert` + audits) with:

```python
    meta = review.policy_meta or {}
    fn = (meta.get('code', '').split('-')[1] if '-' in meta.get('code', '') else 'GOV')
    library_data = {
        'code': meta.get('code'),
        'title': meta.get('name'),
        'fn': fn,
        'owner': meta.get('owner'),
        'version': str(meta.get('version', '')).lstrip('v'),
        'status': 'approved',
        'score': score['overall'],
        'pages': meta.get('pages'),
        'nextReview': '—',
        'updatedDays': 0,
    }

    # Copy the review's source document into a library-owned, immutable copy so the
    # Library download survives later deletion of the review.
    src_doc = await PolicyDocuments.get('review', review_id, db=db)
    if src_doc:
        new_path = copy_stored(src_doc.storage_path, src_doc.filename)
        await PolicyDocuments.upsert(
            'library', meta.get('code'), src_doc.filename, src_doc.content_type, src_doc.size, new_path, src_doc.text, db=db
        )
        library_data['hasDocument'] = True
        library_data['filename'] = src_doc.filename

    await PolicyLibrary.upsert(code=meta.get('code'), data=library_data, source_review_id=review_id, db=db)
    await PolicyAudits.insert('review', review_id, 'approved', user.id, user.name, {'score': score['overall']}, db=db)
    await PolicyAudits.insert('review', review_id, 'published', user.id, user.name, {'code': meta.get('code')}, db=db)
    return updated
```

In `delete_review`, before `await PolicyReviews.delete(review_id, db=db)`, add document cleanup:

```python
    doc = await PolicyDocuments.delete('review', review_id, db=db)
    if doc:
        delete_stored(doc.storage_path)
    await PolicyReviews.delete(review_id, db=db)
```

In `delete_library_entry`, before `await PolicyLibrary.delete_by_code(code, db=db)`, add:

```python
    doc = await PolicyDocuments.delete('library', code, db=db)
    if doc:
        delete_stored(doc.storage_path)
    await PolicyLibrary.delete_by_code(code, db=db)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/test_router_documents.py -v`
Expected: PASS (all document router tests).

- [ ] **Step 5: Run the entire backend policy suite**

Run: `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/ -v`
Expected: PASS (Phase-1 tests + all new tests; docx test may SKIP without python-docx).

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/routers/policy_review.py backend/open_webui/test/policy_review/test_router_documents.py
git commit -m "feat(policy-review): copy document to library on approve; cleanup on delete/unpublish"
```

---

## Task 8: Frontend types + API client

**Files:**
- Modify: `src/lib/components/policy-review/lib/types.ts`
- Modify: `src/lib/components/policy-review/lib/api.ts`

- [ ] **Step 1: Extend the types**

In `src/lib/components/policy-review/lib/types.ts`, add the document descriptor type and extend `PolicyMeta`. Replace the `PolicyMeta` interface with:

```typescript
export interface PolicyDocumentMeta {
	filename: string;
	contentType: string | null;
	size: number;
}

export interface PolicyMeta {
	name: string;
	code: string;
	version: string;
	owner: string;
	reviewer: string;
	reviewDate: string;
	pages: number;
	filename: string;
	document?: PolicyDocumentMeta;
}
```

In the `LibraryPolicy` interface, add two optional fields (after `related?: string[];`):

```typescript
	hasDocument?: boolean;
	filename?: string;
```

- [ ] **Step 2: Add the multipart create + replace + download URL helpers**

In `src/lib/components/policy-review/lib/api.ts`:

Add a multipart helper and rewrite `createReviewApi`. Replace the existing `createReviewApi` line with:

```typescript
// Multipart create: file is required (Phase 2). The shared request() helper forces
// a JSON content-type, so multipart uploads use their own fetch (the browser sets
// the multipart boundary automatically when given a FormData body).
async function upload<T>(token: string, path: string, method: string, form: FormData): Promise<T> {
	let error: unknown = null;
	const res = await fetch(`${BASE}${path}`, {
		method,
		headers: { Accept: 'application/json', authorization: `Bearer ${token}` },
		body: form
	})
		.then(async (r) => {
			if (!r.ok) throw await r.json();
			return r.json();
		})
		.catch((err) => {
			error = err?.detail ?? err;
			console.error(error);
			return null;
		});
	if (error) throw error;
	return res as T;
}

export const createReviewApi = (
	token: string,
	policy_meta: unknown,
	file: File,
	strengths: string[] = []
) => {
	const form = new FormData();
	form.append('file', file);
	form.append('meta', JSON.stringify(policy_meta));
	form.append('strengths', JSON.stringify(strengths));
	return upload<Review>(token, '/reviews', 'POST', form);
};

export const replaceReviewDocumentApi = (token: string, id: string, file: File) => {
	const form = new FormData();
	form.append('file', file);
	return upload<Review>(token, `/reviews/${id}/document`, 'PUT', form);
};

// Download URLs for navigation (window.open). Auth rides the session cookie, as the
// app's existing file-content links do.
export const reviewDocumentUrl = (id: string) => `${BASE}/reviews/${id}/document`;
export const libraryDocumentUrl = (code: string) =>
	`${BASE}/library/${encodeURIComponent(code)}/document`;
```

- [ ] **Step 3: Type-check**

Run (from repo root): `npx svelte-check --tsconfig ./tsconfig.json --threshold error 2>&1 | grep policy-review`
Expected: no new errors referencing `api.ts` or `types.ts`. (`store.ts` and `UploadView.svelte` will still report errors until Tasks 9–10 — that is expected at this point; confirm only that `api.ts`/`types.ts` themselves are clean.)

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/policy-review/lib/types.ts src/lib/components/policy-review/lib/api.ts
git commit -m "feat(policy-review): multipart create + document download api client"
```

---

## Task 9: Frontend store — `createReview(meta, file)` + `replaceDocument`

**Files:**
- Modify: `src/lib/components/policy-review/lib/store.ts`
- Test: `src/lib/components/policy-review/lib/store.test.ts`

- [ ] **Step 1: Update the store test (failing)**

In `src/lib/components/policy-review/lib/store.test.ts`:

Add `replaceReviewDocumentApi` to the `vi.mock('./api', ...)` object (after `createReviewApi`):

```typescript
	replaceReviewDocumentApi: vi.fn(async (_t, id) => backendReview({ id, status: 'draft' })),
```

Update the `createReview` test to pass a file and assert it is forwarded. Replace the body of the `it('createReview calls the api ...')` test's `createReview(...)` call with a version that includes a `File` and an assertion:

```typescript
		const file = new File([new Uint8Array([1, 2, 3])], 'policy.pdf', { type: 'application/pdf' });
		const created = await createReview(
			{
				name: 'Test Policy',
				code: 'POL-1',
				version: 'v1.0',
				owner: 'OE',
				reviewer: 'Rev',
				reviewDate: '2026-01-01',
				pages: 4,
				filename: ''
			},
			file
		);
		expect(api.createReviewApi).toHaveBeenCalledOnce();
		// The selected file must be forwarded to the api (3rd arg).
		expect((api.createReviewApi as unknown as vi.Mock).mock.calls[0][2]).toBe(file);
```

Add a new test for `replaceDocument` inside the `describe('api-backed review mutators', ...)` block:

```typescript
	it('replaceDocument forwards the file and updates the review from the response', async () => {
		reviews.set([
			{
				id: 'rev-1',
				policyMeta: {} as never,
				checklistVersionId: 'v2.0',
				results: {},
				status: 'rejected',
				approval: { status: 'rejected', sentAt: null, decidedAt: null, decidedBy: 'A', note: 'fix' },
				strengths: [],
				createdBy: 'Test Reviewer',
				createdAt: ''
			}
		]);
		const file = new File([new Uint8Array([9])], 'fixed.pdf', { type: 'application/pdf' });
		await replaceDocument('rev-1', file);
		expect(api.replaceReviewDocumentApi).toHaveBeenCalledWith('', 'rev-1', file);
		// Response maps back in (status draft).
		expect(get(reviews).find((r) => r.id === 'rev-1')!.status).toBe('draft');
	});
```

Add `replaceDocument` to the store import list near the top of the test file (in the `import { ... } from './store';` block).

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx vitest run src/lib/components/policy-review/lib/store.test.ts`
Expected: FAIL — `createReview` arity mismatch / `replaceDocument` is not exported.

- [ ] **Step 3: Update the store**

In `src/lib/components/policy-review/lib/store.ts`, replace the `createReview` function with a file-taking version and add `replaceDocument`:

```typescript
export async function createReview(
	policyMeta: Review['policyMeta'],
	file: File,
	strengths: string[] = []
): Promise<Review> {
	const created = mapReview(await api.createReviewApi(token(), policyMeta, file, strengths));
	reviews.update((arr) => [created, ...arr]);
	activeReviewId.set(created.id);
	stage.set('review');
	return created;
}

export async function replaceDocument(reviewId: string, file: File): Promise<void> {
	const updated = mapReview(await api.replaceReviewDocumentApi(token(), reviewId, file));
	reviews.update((arr) => arr.map((r) => (r.id === reviewId ? updated : r)));
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npx vitest run src/lib/components/policy-review/lib/store.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/policy-review/lib/store.ts src/lib/components/policy-review/lib/store.test.ts
git commit -m "feat(policy-review): store createReview(file) + replaceDocument"
```

---

## Task 10: UploadView — real dropzone + states

**Files:**
- Create: `src/lib/components/policy-review/lib/uploadValidation.ts`
- Test: `src/lib/components/policy-review/lib/uploadValidation.test.ts`
- Modify: `src/lib/components/policy-review/views/UploadView.svelte`

- [ ] **Step 1: Write the validator test (failing)**

Create `src/lib/components/policy-review/lib/uploadValidation.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { validateUploadFile, MAX_UPLOAD_MB, ACCEPT_ATTR } from './uploadValidation';

function file(name: string, sizeBytes: number, type = '') {
	const f = new File([new Uint8Array(1)], name, { type });
	Object.defineProperty(f, 'size', { value: sizeBytes });
	return f;
}

describe('validateUploadFile', () => {
	it('accepts pdf/docx/md/txt', () => {
		expect(validateUploadFile(file('a.pdf', 100))).toBeNull();
		expect(validateUploadFile(file('a.DOCX', 100))).toBeNull();
		expect(validateUploadFile(file('a.md', 100))).toBeNull();
		expect(validateUploadFile(file('a.txt', 100))).toBeNull();
	});

	it('rejects unsupported types', () => {
		expect(validateUploadFile(file('a.png', 100))).toMatch(/PDF, DOCX, MD, or TXT/);
	});

	it('rejects empty files', () => {
		expect(validateUploadFile(file('a.pdf', 0))).toMatch(/empty/i);
	});

	it('rejects oversize files', () => {
		expect(validateUploadFile(file('a.pdf', MAX_UPLOAD_MB * 1024 * 1024 + 1))).toMatch(/limit/i);
	});

	it('exposes an accept attribute string', () => {
		expect(ACCEPT_ATTR).toContain('.pdf');
		expect(ACCEPT_ATTR).toContain('.txt');
	});
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx vitest run src/lib/components/policy-review/lib/uploadValidation.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the validator**

Create `src/lib/components/policy-review/lib/uploadValidation.ts`:

```typescript
// Pure client-side upload validation, mirroring the backend allowlist + size cap.
export const MAX_UPLOAD_MB = 25;
const ALLOWED = ['pdf', 'docx', 'md', 'txt'] as const;
export const ACCEPT_ATTR = ALLOWED.map((e) => `.${e}`).join(',');

function ext(name: string): string {
	const i = name.lastIndexOf('.');
	return i >= 0 ? name.slice(i + 1).toLowerCase() : '';
}

/** Returns an error message string, or null if the file is acceptable. */
export function validateUploadFile(file: File): string | null {
	if (!(ALLOWED as readonly string[]).includes(ext(file.name))) {
		return 'Unsupported file type. Upload a PDF, DOCX, MD, or TXT file.';
	}
	if (file.size <= 0) return 'The file is empty.';
	if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `File exceeds the ${MAX_UPLOAD_MB} MB limit.`;
	return null;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npx vitest run src/lib/components/policy-review/lib/uploadValidation.test.ts`
Expected: PASS.

- [ ] **Step 5: Wire the dropzone in UploadView**

In `src/lib/components/policy-review/views/UploadView.svelte`:

Update the `<script>` block — replace the imports + state + submit with:

```typescript
	import Icon from '../ui/Icon.svelte';
	import { activeVersion, createReview } from '../lib/store';
	import { validateUploadFile, ACCEPT_ATTR, MAX_UPLOAD_MB } from '../lib/uploadValidation';
	import type { PolicyMeta } from '../lib/types';

	let dragging = $state(false);
	let submitting = $state(false);
	let phase = $state<'' | 'uploading' | 'parsing'>('');
	let error = $state('');

	// Selected file.
	let file = $state<File | null>(null);
	let fileInput: HTMLInputElement;

	// Metadata form state.
	let name = $state('');
	let code = $state('');
	let version = $state('');
	let owner = $state('');
	let reviewer = $state('');
	let reviewDate = $state('');
	let pages = $state<number>(0);

	let canSubmit = $derived(
		name.trim().length > 0 && code.trim().length > 0 && file !== null && !submitting
	);

	function pickFile(f: File | null) {
		error = '';
		if (!f) {
			file = null;
			return;
		}
		const msg = validateUploadFile(f);
		if (msg) {
			error = msg;
			file = null;
			return;
		}
		file = f;
	}

	function onFileChange(e: Event) {
		const input = e.target as HTMLInputElement;
		pickFile(input.files?.[0] ?? null);
	}

	function clearFile() {
		file = null;
		error = '';
		if (fileInput) fileInput.value = '';
	}

	function fmtSize(bytes: number): string {
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
		return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
	}

	async function submit(e: Event) {
		e.preventDefault();
		if (!canSubmit || !file) return;
		submitting = true;
		error = '';
		phase = 'uploading';
		const meta: PolicyMeta = {
			name: name.trim(),
			code: code.trim(),
			version: version.trim(),
			owner: owner.trim(),
			reviewer: reviewer.trim(),
			reviewDate: reviewDate,
			pages: Number(pages) || 0,
			filename: file.name
		};
		try {
			phase = 'parsing';
			await createReview(meta, file); // navigates to the workspace via stage='review'
		} catch (err) {
			error = err instanceof Error ? err.message : String(err);
			submitting = false;
			phase = '';
		}
	}

	const HUES = [200, 30, 165, 0, 280, 130];
	let themes = $derived(
		($activeVersion?.themes ?? []).map((t, i) => ({
			id: t.id,
			name: t.name,
			count: ($activeVersion?.sections ?? [])
				.filter((s) => s.theme === t.id)
				.reduce((a, s) => a + s.items.length, 0),
			gate: t.gate,
			hue: HUES[i % HUES.length]
		}))
	);
	let total = $derived(themes.reduce((a, t) => a + t.count, 0));

	function onDragOver(e: DragEvent) {
		e.preventDefault();
		dragging = true;
	}
	function onDragLeave() {
		dragging = false;
	}
	function onDrop(e: DragEvent) {
		e.preventDefault();
		dragging = false;
		pickFile(e.dataTransfer?.files?.[0] ?? null);
	}
```

Replace the dropzone markup (the `<div class="dropzone upload-card" ...>` block) with a real one:

```svelte
	<div
		class="dropzone upload-card"
		class:dragging
		class:has-file={file}
		ondragover={onDragOver}
		ondragleave={onDragLeave}
		ondrop={onDrop}
		role="presentation"
	>
		<input
			bind:this={fileInput}
			type="file"
			accept={ACCEPT_ATTR}
			class="dz-input"
			onchange={onFileChange}
		/>
		{#if file}
			<div class="dz-file">
				<Icon name="fileText" size={18} />
				<div class="dz-file-meta">
					<div class="dz-file-name">{file.name}</div>
					<div class="dz-file-size">{fmtSize(file.size)}</div>
				</div>
				<button type="button" class="dz-remove" onclick={clearFile} aria-label="Remove file">
					<Icon name="x" size={14} />
				</button>
			</div>
		{:else}
			<button type="button" class="dz-browse" onclick={() => fileInput?.click()}>
				<div class="dz-doc-badge"><Icon name="upload" size={14} stroke={2.2} /></div>
				<h3>Drag &amp; drop the policy document, or browse</h3>
				<p>Required to start a review.</p>
				<div class="formats">
					<span>.docx</span><i></i><span>.pdf</span><i></i><span>.md</span><i></i><span>.txt</span>
					<i></i><span>max {MAX_UPLOAD_MB}&nbsp;MB</span>
				</div>
			</button>
		{/if}
	</div>
```

Update the submit button to show phases. Replace the existing submit button block (`<button class="btn btn-primary" type="submit" ...>`) with:

```svelte
				<button class="btn btn-primary" type="submit" disabled={!canSubmit}>
					{#if submitting}
						{phase === 'parsing' ? 'Parsing document…' : 'Uploading…'}
					{:else}
						<Icon name="check" size={14} /> Create review
					{/if}
				</button>
```

Add styles to the `<style>` block (after the existing `.btn[disabled]` rule):

```css
	.dropzone {
		position: relative;
	}
	.dz-input {
		display: none;
	}
	.dz-browse {
		display: block;
		width: 100%;
		background: none;
		border: 0;
		cursor: pointer;
		font: inherit;
		color: inherit;
		text-align: center;
	}
	.dz-file {
		display: flex;
		align-items: center;
		gap: 12px;
		text-align: left;
	}
	.dz-file-meta {
		min-width: 0;
		flex: 1;
	}
	.dz-file-name {
		font-weight: 600;
		color: var(--ink-900);
		font-size: 13.5px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
	.dz-file-size {
		font-size: 12px;
		color: var(--ink-500);
	}
	.dz-remove {
		background: none;
		border: 0;
		cursor: pointer;
		color: var(--ink-400);
		padding: 4px;
	}
	.dz-remove:hover {
		color: var(--ink-700);
	}
```

> Verify `Icon.svelte` has an `x` icon name. If it does not, use `name="trash"` (added in Phase 1) for the remove button, or add an `x`/`close` path to `ui/Icon.svelte` following the existing icon pattern.

- [ ] **Step 6: Type-check + verify**

Run: `npx svelte-check --tsconfig ./tsconfig.json --threshold error 2>&1 | grep -i "UploadView\|uploadValidation"`
Expected: no errors.

Then verify the screen renders and gates on a file, using the preview workflow:
1. `preview_start` (or reuse a running dev server).
2. Navigate to the policy-review tool → New review.
3. `preview_snapshot` — confirm the dropzone shows "Drag & drop … or browse" and "Create review" is disabled.
4. `preview_fill` the required Policy name + code; `preview_snapshot` — "Create review" stays disabled (no file yet).
5. Confirm an unsupported type shows the inline error (attach a `.png` via the file input in the browser, observe the red error).

- [ ] **Step 7: Commit**

```bash
git add src/lib/components/policy-review/lib/uploadValidation.ts src/lib/components/policy-review/lib/uploadValidation.test.ts src/lib/components/policy-review/views/UploadView.svelte
git commit -m "feat(policy-review): real document upload dropzone + states"
```

---

## Task 11: ReviewView — source download + replace

**Files:**
- Modify: `src/lib/components/policy-review/views/ReviewView.svelte`

- [ ] **Step 1: Add the source affordance**

In `src/lib/components/policy-review/views/ReviewView.svelte`:

Add imports + a hidden file input to the `<script>` block. After the existing `import { ... } from '../lib/store';` add:

```typescript
	import { reviewDocumentUrl } from '../lib/api';
	import { replaceDocument } from '../lib/store';

	let replaceInput: HTMLInputElement;
	let replacing = $state(false);

	let document_ = $derived($activeReview?.policyMeta?.document ?? null);
	let canReplace = $derived(
		$canUseChecker &&
			$activeReview != null &&
			($activeReview.status === 'draft' || $activeReview.status === 'rejected')
	);

	async function onReplaceChange(e: Event) {
		const f = (e.target as HTMLInputElement).files?.[0];
		if (!f || !$activeReview) return;
		replacing = true;
		try {
			await replaceDocument($activeReview.id, f);
		} finally {
			replacing = false;
			if (replaceInput) replaceInput.value = '';
		}
	}
```

In the policy header markup, add a source row under `.policy-tags`. Insert after the `</div>` that closes `.policy-tags` (still inside the `min-width:0; flex:1` wrapper), before the closing `</div>`:

```svelte
				{#if document_ && $activeReview}
					<div class="policy-source">
						<a
							class="src-link"
							href={reviewDocumentUrl($activeReview.id)}
							target="_blank"
							rel="noopener"
						>
							<Icon name="fileText" size={13} />
							{document_.filename}
							<span class="src-dl">Download</span>
						</a>
						{#if canReplace}
							<button
								type="button"
								class="src-replace"
								onclick={() => replaceInput?.click()}
								disabled={replacing}
							>
								{replacing ? 'Replacing…' : 'Replace'}
							</button>
							<input
								bind:this={replaceInput}
								type="file"
								accept=".pdf,.docx,.md,.txt"
								style="display:none"
								onchange={onReplaceChange}
							/>
						{/if}
					</div>
				{/if}
```

Add styles to the `<style>` block:

```css
	.policy-source {
		display: flex;
		align-items: center;
		gap: 12px;
		margin-top: 8px;
		font-size: 12.5px;
	}
	.src-link {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		color: var(--ink-700);
		text-decoration: none;
	}
	.src-link:hover {
		color: var(--primary);
	}
	.src-dl {
		color: var(--primary);
		font-weight: 600;
	}
	.src-replace {
		background: none;
		border: 0;
		color: var(--primary);
		font-weight: 600;
		cursor: pointer;
		font-size: 12.5px;
		padding: 0;
	}
	.src-replace[disabled] {
		opacity: 0.5;
		cursor: not-allowed;
	}
```

> The approver opens a queued review through this same `ReviewView`, so the **Download** link is automatically visible to approvers/admins; **Replace** is gated to the owner-while-editable via `canReplace`.

- [ ] **Step 2: Type-check + verify**

Run: `npx svelte-check --tsconfig ./tsconfig.json --threshold error 2>&1 | grep -i "ReviewView"`
Expected: no errors.

Verify with the preview workflow: open a review that has a document, `preview_snapshot` to confirm the filename + Download link render in the header, and (as owner on a draft) the Replace control is present.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/policy-review/views/ReviewView.svelte
git commit -m "feat(policy-review): source download + replace in review workspace"
```

---

## Task 12: Library download (PolicyPopup)

**Files:**
- Modify: `src/lib/components/policy-review/views/PolicyPopup.svelte`

> `PolicyPopup` uses a local `policy` (subscribed from `selectedPolicy`) and already has two **inert** footer buttons — "Download" and "Open PDF" ([PolicyPopup.svelte:174-190](src/lib/components/policy-review/views/PolicyPopup.svelte)). Phase 2 makes "Download" real (gated on `policy.hasDocument`) and removes the misleading "Open PDF" (there is no viewer — honesty per the osool rebrand). `AllPoliciesView` rows are `<button>` elements, so a nested `<a>` download would be invalid HTML; the popup is the single correct home for the download.

- [ ] **Step 1: Add the api import**

In `src/lib/components/policy-review/views/PolicyPopup.svelte`, add after the `import type { LibraryPolicy } from '../lib/types';` line:

```typescript
	import { libraryDocumentUrl } from '../lib/api';
```

- [ ] **Step 2: Wire the footer Download, remove Open PDF**

Replace the footer block (currently lines ~174-190, from `<footer class="pl-popup-foot">` through its closing `</footer>`) with:

```svelte
			<footer class="pl-popup-foot">
				{#if policy.hasDocument}
					<a
						class="btn btn-sm btn-ghost"
						href={libraryDocumentUrl(policy.code)}
						target="_blank"
						rel="noopener"
					>Download{policy.filename ? ` (${policy.filename})` : ''}</a>
				{/if}
				{#if $canAdmin || $canApprove}
					<button
						class="btn btn-sm pl-unpublish"
						class:armed={confirmingUnpublish}
						type="button"
						onclick={onUnpublish}
						onmouseleave={() => (confirmingUnpublish = false)}
					>
						{confirmingUnpublish ? 'Confirm unpublish' : 'Unpublish'}
					</button>
				{/if}
				<span class="grow"></span>
				<button class="btn btn-sm" type="button" onclick={closePolicyPopup}>Close</button>
			</footer>
```

- [ ] **Step 3: Make the summary fallback honest (no viewer to "open")**

Replace the summary fallback paragraph text (currently `Summary not yet available — open the PDF to read the policy.`) with:

```svelte
						Summary not yet available{#if policy.hasDocument} — download the source document to read the policy{/if}.
```

- [ ] **Step 4: Type-check + verify**

Run: `npx svelte-check --tsconfig ./tsconfig.json --threshold error 2>&1 | grep -i "PolicyPopup"`
Expected: no errors.

Verify with the preview workflow: approve a review with a document so it lands in the Library, open the policy popup, `preview_snapshot` to confirm "Download" renders and downloads the source; confirm a seeded policy (no document) shows no Download button and no "Open PDF".

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/policy-review/views/PolicyPopup.svelte
git commit -m "feat(policy-review): library document download in policy popup"
```

---

## Task 13: Full gates + end-to-end smoke

**Files:** none (verification only)

- [ ] **Step 1: Backend suite**

Run (from `backend/`): `.venv/Scripts/python.exe -m pytest open_webui/test/policy_review/ -v`
Expected: all PASS (docx test may SKIP without python-docx).

- [ ] **Step 2: Frontend suite**

Run (from repo root): `npx vitest run src/lib/components/policy-review/`
Expected: all PASS.

- [ ] **Step 3: Type check (policy-review clean)**

Run: `npx svelte-check --tsconfig ./tsconfig.json --threshold error 2>&1 | grep -i policy-review`
Expected: no errors (pre-existing a11y warnings on `SubmitApprovalModal`, noted in Phase 1, are acceptable).

- [ ] **Step 4: Build**

Run: `npm run build`
Expected: build succeeds.

- [ ] **Step 5: Manual end-to-end smoke (Docker backend on :8080 + dev UI on :5173)**

Using the three Phase-1 test users (Felwa = checker, PRP Admin = approver, Nouf = admin; see memory `policy-review-backend-phase1`):
1. As **Felwa**: New review → attach a real `.pdf` and `.docx` (separately) → confirm "Create review" is disabled until a file is attached → create → workspace opens → header shows filename + **Download** (downloads the original) → **Replace** with a `.docx` works.
2. Attach an unsupported type (`.png`) and an oversize file → inline error, no review created.
3. Submit → as **PRP Admin**, open the queued review → **Download** the source works (cross-user access) → Approve.
4. In the **Library**, open the approved policy → **Download source** works for any user; delete the original review (as admin) → Library download still works (independent copy).
5. Confirm a seeded library policy (no document) shows no download link.

- [ ] **Step 6: Final commit (if any smoke fixes were needed) + done**

```bash
git add -A
git commit -m "test(policy-review): Phase 2 end-to-end smoke fixes"
```

---

## Self-Review Notes (for the implementer)

- **Spec coverage:** §3 table → Task 1/2; §4 changed `POST /reviews` → Task 4; new endpoints → Tasks 5–6; approve-copy + cleanup → Task 7; §5 parsing → Task 3; §6 access/lifecycle → Tasks 4–7; §7 frontend → Tasks 8–12; §8 testing → distributed across tasks + Task 13.
- **Autofill untouched:** `AUTOFILL_RESULTS_ON_CREATE` is preserved in the new `create_review` exactly as before (Phase 3 retires it).
- **Type consistency:** `createReviewApi(token, policy_meta, file, strengths)` (Task 8) matches `createReview(meta, file, strengths)` (Task 9) and the store test (Task 9). `PolicyDocuments.upsert(owner_type, owner_id, filename, content_type, size, storage_path, text)` is used identically in Tasks 1, 4, 5, 7. Seam names (`validate_upload`, `store_upload`, `read_stored`, `copy_stored`, `delete_stored`, `extract_text`) match between `documents.py` (Task 3), the router imports (Task 4), and the test monkeypatches (Tasks 4–7).
- **Deferred (not in this plan, per spec §1/§10):** in-app viewer, AI scan (Phase 3), multiple docs/history, OCR/image formats, PDF page-count auto-fill.
