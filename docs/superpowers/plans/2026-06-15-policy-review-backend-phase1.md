# Policy Review Backend — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Policy Review maker-checker workflow real and multi-user on a database behind permission-enforced REST endpoints, and rewire the finished frontend off `localStorage` onto those endpoints — with manual verdicts, no file upload, no AI scan.

**Architecture:** Four `policy_`-prefixed SQLAlchemy tables (checklist versions, reviews carrying a frozen checklist snapshot, the published library, an audit log) accessed by async DAO classes; one FastAPI router at `/api/v1/policy` with `policy_checker`/`policy_approver`/`policy_admin` enforcement and admin bypass; a Python port of the frontend scoring used to gate submit and compute the published score; a first-run seeder loading the canonical PRP v2.0 checklist + demo library + demo reviews from a committed JSON exported from the frontend seed; and a thin frontend API client replacing the `localStorage` store with no view changes.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy (async, `aiosqlite`/`psycopg`) / Alembic; SvelteKit / TypeScript; pytest + pytest-asyncio + httpx for backend tests, vitest for the one-off frontend seed export and scoring-parity check.

**Spec:** `docs/superpowers/specs/2026-06-15-policy-review-backend-phase1-design.md`

---

## Conventions & ground rules (read once before starting)

- **Backend style** (from `backend/open_webui/models/notes.py`): tables subclass `Base` from `open_webui.internal.db`; `Text` primary keys set to `str(uuid.uuid4())`; timestamps are `BigInteger` set to `int(time.time_ns())`; `JSON` columns for documents; Pydantic models use `model_config = ConfigDict(from_attributes=True)`; DAO methods are `async` and wrap work in `async with get_async_db_context(db) as db:`; each DAO is exported as a singleton instance at the bottom of the module (e.g. `PolicyReviews = PolicyReviewTable()`).
- **Router style** (from `backend/open_webui/routers/notes.py`): `router = APIRouter()`; endpoints take `request: Request`, `user=Depends(get_verified_user)`, `db: AsyncSession = Depends(get_async_session)`; permission gate is `if user.role != 'admin' and not await has_permission(user.id, 'features.<key>', request.app.state.config.USER_PERMISSIONS, db=db): raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.UNAUTHORIZED)`.
- **Run backend tests:** from `backend/`, `python -m pytest open_webui/test/policy_review/<file>.py -v`.
- **Run a single backend test:** append `::ClassName::test_name` or `::test_name`.
- **Run the frontend seed/parity tests:** from repo root, `npx vitest run <path>`.
- **Commit after every task** (each task ends in a commit step). Work on branch `osool` (already checked out).
- **No placeholders.** Every code block below is the literal content to write.

Create the test package directory once, at the start:

```bash
mkdir -p backend/open_webui/test/policy_review
touch backend/open_webui/test/policy_review/__init__.py
```

---

## Task 1: Scoring port — shared fixtures + `scoring.py` (pure, no DB)

This is the correctness core (gates submit, computes the published score) and the parity contract with the frontend. Do it first; it needs no database.

**Files:**
- Create: `backend/open_webui/test/policy_review/policy_scoring_fixtures.json`
- Create: `backend/open_webui/utils/policy_review/__init__.py`
- Create: `backend/open_webui/utils/policy_review/scoring.py`
- Test: `backend/open_webui/test/policy_review/test_scoring.py`
- Test (frontend parity): `src/lib/components/policy-review/lib/scoring.parity.test.ts`

- [ ] **Step 1: Write the shared fixtures file**

These four cases are exactly computable (no `.5` rounding cases) and cover all verdict branches. Inputs are minimal checklist definitions + results; expected holds the four invariant fields both implementations must agree on.

`backend/open_webui/test/policy_review/policy_scoring_fixtures.json`:

```json
[
  {
    "name": "approved",
    "definition": {
      "themes": [
        {"id": "T1", "name": "T1", "weight": 50, "gate": true, "threshold": 85},
        {"id": "T2", "name": "T2", "weight": 50, "gate": false, "threshold": 85}
      ],
      "sections": [
        {"id": "S1", "theme": "T1", "items": [{"id": "S1-1"}, {"id": "S1-2"}]},
        {"id": "S2", "theme": "T2", "items": [{"id": "S2-1"}, {"id": "S2-2"}]}
      ],
      "verdictBands": {"approved": 85, "conditional": 70}
    },
    "results": {
      "S1-1": {"result": "compliant"}, "S1-2": {"result": "compliant"},
      "S2-1": {"result": "compliant"}, "S2-2": {"result": "compliant"}
    },
    "expected": {"overall": 100, "gatesPass": true, "humanItemsRemain": false, "verdictKey": "approved"}
  },
  {
    "name": "gate-fail-rejected",
    "definition": {
      "themes": [
        {"id": "T1", "name": "T1", "weight": 50, "gate": true, "threshold": 85},
        {"id": "T2", "name": "T2", "weight": 50, "gate": false, "threshold": 85}
      ],
      "sections": [
        {"id": "S1", "theme": "T1", "items": [{"id": "S1-1"}, {"id": "S1-2"}]},
        {"id": "S2", "theme": "T2", "items": [{"id": "S2-1"}, {"id": "S2-2"}]}
      ],
      "verdictBands": {"approved": 85, "conditional": 70}
    },
    "results": {
      "S1-1": {"result": "compliant"}, "S1-2": {"result": "non-compliant"},
      "S2-1": {"result": "compliant"}, "S2-2": {"result": "compliant"}
    },
    "expected": {"overall": 75, "gatesPass": false, "humanItemsRemain": false, "verdictKey": "rejected"}
  },
  {
    "name": "human-remains-draft",
    "definition": {
      "themes": [
        {"id": "T1", "name": "T1", "weight": 50, "gate": true, "threshold": 85},
        {"id": "T2", "name": "T2", "weight": 50, "gate": false, "threshold": 85}
      ],
      "sections": [
        {"id": "S1", "theme": "T1", "items": [{"id": "S1-1"}, {"id": "S1-2"}]},
        {"id": "S2", "theme": "T2", "items": [{"id": "S2-1"}, {"id": "S2-2"}]}
      ],
      "verdictBands": {"approved": 85, "conditional": 70}
    },
    "results": {
      "S1-1": {"result": "compliant"}, "S1-2": {"result": "human"},
      "S2-1": {"result": "compliant"}, "S2-2": {"result": "pending"}
    },
    "expected": {"overall": 100, "gatesPass": true, "humanItemsRemain": true, "verdictKey": "draft"}
  },
  {
    "name": "conditional",
    "definition": {
      "themes": [
        {"id": "T1", "name": "T1", "weight": 50, "gate": true, "threshold": 70},
        {"id": "T2", "name": "T2", "weight": 50, "gate": false, "threshold": 85}
      ],
      "sections": [
        {"id": "S1", "theme": "T1", "items": [{"id": "S1-1"}, {"id": "S1-2"}, {"id": "S1-3"}, {"id": "S1-4"}]},
        {"id": "S2", "theme": "T2", "items": [{"id": "S2-1"}, {"id": "S2-2"}, {"id": "S2-3"}, {"id": "S2-4"}]}
      ],
      "verdictBands": {"approved": 85, "conditional": 70}
    },
    "results": {
      "S1-1": {"result": "compliant"}, "S1-2": {"result": "compliant"}, "S1-3": {"result": "compliant"}, "S1-4": {"result": "non-compliant"},
      "S2-1": {"result": "compliant"}, "S2-2": {"result": "compliant"}, "S2-3": {"result": "compliant"}, "S2-4": {"result": "non-compliant"}
    },
    "expected": {"overall": 75, "gatesPass": true, "humanItemsRemain": false, "verdictKey": "conditional"}
  }
]
```

- [ ] **Step 2: Write the failing Python test**

`backend/open_webui/test/policy_review/test_scoring.py`:

```python
import json
from pathlib import Path

from open_webui.utils.policy_review.scoring import compute_scores

FIXTURES = json.loads((Path(__file__).parent / 'policy_scoring_fixtures.json').read_text())


def test_scoring_fixtures():
    for case in FIXTURES:
        result = compute_scores(case['definition'], case['results'])
        exp = case['expected']
        assert result['overall'] == exp['overall'], case['name']
        assert result['gatesPass'] == exp['gatesPass'], case['name']
        assert result['humanItemsRemain'] == exp['humanItemsRemain'], case['name']
        assert result['verdict']['key'] == exp['verdictKey'], case['name']
```

- [ ] **Step 3: Run it to confirm it fails**

Run: `cd backend && python -m pytest open_webui/test/policy_review/test_scoring.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'open_webui.utils.policy_review'`.

- [ ] **Step 4: Implement the scorer**

Note the `js_round` helper: JavaScript's `Math.round` rounds half **up** (`Math.round(2.5) === 3`), while Python's built-in `round` uses banker's rounding (`round(2.5) == 2`). To stay byte-for-byte identical to [scoring.ts](src/lib/components/policy-review/lib/scoring.ts), we replicate `Math.round` with `math.floor(x + 0.5)`.

`backend/open_webui/utils/policy_review/__init__.py`:

```python
```

(empty file)

`backend/open_webui/utils/policy_review/scoring.py`:

```python
"""Authoritative server-side port of src/lib/components/policy-review/lib/scoring.ts.

Per-theme score = compliant / (compliant + non-compliant). `human` and missing/
`pending` items are held aside (not scored, but they block a final verdict).
Gate themes must clear their threshold. Overall = weight-weighted average of theme
scores. Kept identical to the TypeScript implementation (see scoring.parity.test.ts).
"""

import math
from typing import Any


def _js_round(value: float) -> int:
    # Mirror JavaScript Math.round (half rounds up), not Python banker's rounding.
    return math.floor(value + 0.5)


def compute_scores(version: dict[str, Any], results: dict[str, Any]) -> dict[str, Any]:
    themes = version.get('themes', [])
    sections = version.get('sections', [])
    verdict_bands = version.get('verdictBands', {})

    by_theme: dict[str, dict[str, int]] = {}
    for t in themes:
        by_theme[t['id']] = {'total': 0, 'yes': 0, 'no': 0, 'human': 0, 'pending': 0, 'items': 0}

    for sec in sections:
        bucket = by_theme.get(sec['theme'])
        if bucket is None:
            continue
        for item in sec.get('items', []):
            bucket['items'] += 1
            result = (results.get(item['id']) or {}).get('result', 'pending')
            if result == 'compliant':
                bucket['yes'] += 1
                bucket['total'] += 1
            elif result == 'non-compliant':
                bucket['no'] += 1
                bucket['total'] += 1
            elif result == 'human':
                bucket['human'] += 1
            else:
                bucket['pending'] += 1

    theme_rows = []
    for t in themes:
        s = by_theme[t['id']]
        pct = _js_round((s['yes'] / s['total']) * 100) if s['total'] > 0 else 0
        theme_rows.append({**t, **s, 'pct': pct})

    weighted = 0.0
    weight_total = 0.0
    for t in theme_rows:
        if t['total'] > 0:
            weighted += t['pct'] * t['weight']
            weight_total += t['weight']
    overall = _js_round(weighted / weight_total) if weight_total > 0 else 0

    gate_rows = [t for t in theme_rows if t.get('gate')]
    gates_pass = all(t['pct'] >= t['threshold'] for t in gate_rows)
    human_items_remain = any(t['human'] > 0 or t['pending'] > 0 for t in theme_rows)

    approved_band = verdict_bands.get('approved', 85)
    conditional_band = verdict_bands.get('conditional', 70)

    if human_items_remain:
        verdict = {'key': 'draft', 'label': 'Pending review', 'reason': 'Awaiting unresolved items'}
    elif overall >= approved_band and gates_pass:
        verdict = {'key': 'approved', 'label': 'Approved', 'reason': 'Meets all requirements'}
    elif overall >= conditional_band and gates_pass:
        verdict = {'key': 'conditional', 'label': 'Conditionally Approved', 'reason': 'Minimum threshold met — CAP required'}
    else:
        verdict = {
            'key': 'rejected',
            'label': 'Rejected',
            'reason': 'Below minimum overall threshold' if gates_pass else 'Mandatory gate failed',
        }

    return {
        'themeRows': theme_rows,
        'overall': overall,
        'gatesPass': gates_pass,
        'verdict': verdict,
        'humanItemsRemain': human_items_remain,
    }
```

- [ ] **Step 5: Run the Python test to confirm it passes**

Run: `cd backend && python -m pytest open_webui/test/policy_review/test_scoring.py -v`
Expected: PASS (1 passed).

- [ ] **Step 6: Write the frontend parity test**

`src/lib/components/policy-review/lib/scoring.parity.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { computeScores } from './scoring';
import type { ChecklistVersion } from './types';

const fixtures = JSON.parse(
	readFileSync(
		resolve('backend/open_webui/test/policy_review/policy_scoring_fixtures.json'),
		'utf-8'
	)
) as Array<{
	name: string;
	definition: Partial<ChecklistVersion>;
	results: Record<string, { result: string }>;
	expected: { overall: number; gatesPass: boolean; humanItemsRemain: boolean; verdictKey: string };
}>;

describe('scoring parity with backend fixtures', () => {
	for (const c of fixtures) {
		it(c.name, () => {
			const r = computeScores(c.definition as ChecklistVersion, c.results as never);
			expect(r.overall).toBe(c.expected.overall);
			expect(r.gatesPass).toBe(c.expected.gatesPass);
			expect(r.humanItemsRemain).toBe(c.expected.humanItemsRemain);
			expect(r.verdict.key).toBe(c.expected.verdictKey);
		});
	}
});
```

- [ ] **Step 7: Run the parity test to confirm it passes**

Run: `npx vitest run src/lib/components/policy-review/lib/scoring.parity.test.ts`
Expected: PASS (4 tests). If any fail, the Python port diverged from the TS source — fix `scoring.py` to match.

- [ ] **Step 8: Commit**

```bash
git add backend/open_webui/utils/policy_review backend/open_webui/test/policy_review src/lib/components/policy-review/lib/scoring.parity.test.ts
git commit -m "feat(policy-review): port scoring to Python with frontend parity fixtures"
```

---

## Task 2: Database models + async DAO

**Files:**
- Create: `backend/open_webui/models/policy_review.py`
- Test: `backend/open_webui/test/policy_review/conftest.py`
- Test: `backend/open_webui/test/policy_review/test_models.py`

- [ ] **Step 1: Write the test conftest (isolated async SQLite)**

This points the database at a throwaway SQLite file **before** importing any `open_webui` module, disables the startup migrations (we create our tables directly), and exposes an async session factory bound to that same engine so DAO calls and assertions share one database.

`backend/open_webui/test/policy_review/conftest.py`:

```python
import os
import tempfile

# Must run before importing open_webui.* — these configure the engine at import time.
_DB_FILE = tempfile.mktemp(suffix='.db')
os.environ['DATABASE_URL'] = f'sqlite:///{_DB_FILE}'
os.environ['ENABLE_DB_MIGRATIONS'] = 'false'

import pytest_asyncio
from sqlalchemy import select  # noqa: E402

from open_webui.internal.db import Base, async_engine, get_async_db  # noqa: E402
import open_webui.models.policy_review  # noqa: E402,F401  (register tables on Base)


@pytest_asyncio.fixture(autouse=True)
async def _create_schema():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

- [ ] **Step 2: Write the failing model/DAO test**

`backend/open_webui/test/policy_review/test_models.py`:

```python
import pytest

from open_webui.models.policy_review import (
    PolicyChecklistVersions,
    PolicyReviews,
    PolicyLibrary,
    PolicyAudits,
)

ACTIVE_DATA = {'changeSummary': 'init', 'themes': [], 'sections': [], 'verdictBands': {'approved': 85, 'conditional': 70}, 'standards': []}


@pytest.mark.asyncio
async def test_checklist_active_and_draft_singletons():
    active = await PolicyChecklistVersions.insert_version(label='v2.0', status='active', data=ACTIVE_DATA, published_by_id=None, published_by_name='OE')
    assert (await PolicyChecklistVersions.get_active()).id == active.id

    draft = await PolicyChecklistVersions.start_draft()
    assert draft.status == 'draft'
    assert (await PolicyChecklistVersions.get_draft()).id == draft.id

    published = await PolicyChecklistVersions.publish_draft(by_id='u1', by_name='Admin')
    assert published.status == 'active'
    assert published.label == 'v2.1'
    assert (await PolicyChecklistVersions.get_draft()) is None
    versions = await PolicyChecklistVersions.list_versions()
    statuses = sorted(v.status for v in versions)
    assert statuses == ['active', 'archived']  # old active archived, new active present


@pytest.mark.asyncio
async def test_review_crud_and_snapshot_pinning():
    await PolicyChecklistVersions.insert_version(label='v2.0', status='active', data=ACTIVE_DATA, published_by_id=None, published_by_name='OE')
    active = await PolicyChecklistVersions.get_active()

    review = await PolicyReviews.insert_review(
        created_by_id='u1',
        created_by_name='Reviewer One',
        policy_meta={'name': 'P', 'code': 'C-1', 'version': 'v1', 'owner': 'O', 'reviewer': 'R', 'reviewDate': 'd', 'pages': 1, 'filename': 'f.pdf'},
        active_version=active,
    )
    assert review.status == 'draft'
    assert review.checklist_version_id == active.id
    assert review.checklist_snapshot['changeSummary'] == 'init'

    # Publishing a NEW version must not change the in-flight review's snapshot.
    await PolicyChecklistVersions.start_draft()
    await PolicyChecklistVersions.publish_draft(by_id='u2', by_name='Admin')
    fetched = await PolicyReviews.get_by_id(review.id)
    assert fetched.checklist_version_id == active.id
    assert fetched.checklist_snapshot['changeSummary'] == 'init'

    assert [r.id for r in await PolicyReviews.list_by_creator('u1')] == [review.id]
    assert await PolicyReviews.list_by_status('pending') == []


@pytest.mark.asyncio
async def test_library_upsert_by_code():
    e1 = await PolicyLibrary.upsert(code='C-1', data={'code': 'C-1', 'title': 'First'}, source_review_id=None)
    e2 = await PolicyLibrary.upsert(code='C-1', data={'code': 'C-1', 'title': 'Updated'}, source_review_id='rev1')
    assert e1.id == e2.id  # same row reused
    assert (await PolicyLibrary.get_by_code('C-1')).data['title'] == 'Updated'
    assert len(await PolicyLibrary.list_all()) == 1


@pytest.mark.asyncio
async def test_audit_append():
    await PolicyAudits.insert('review', 'rev1', 'created', 'u1', 'Reviewer One', None)
    rows = await PolicyAudits.list_for('review', 'rev1')
    assert len(rows) == 1
    assert rows[0].action == 'created'
```

- [ ] **Step 3: Run it to confirm it fails**

Run: `cd backend && python -m pytest open_webui/test/policy_review/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'open_webui.models.policy_review'`.

- [ ] **Step 4: Implement the models + DAO**

`backend/open_webui/models/policy_review.py`:

```python
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
    import re

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


PolicyChecklistVersions = PolicyChecklistVersionTable()
PolicyReviews = PolicyReviewTable()
PolicyLibrary = PolicyLibraryTable()
PolicyAudits = PolicyAuditTable()
```

- [ ] **Step 5: Run the model tests to confirm they pass**

Run: `cd backend && python -m pytest open_webui/test/policy_review/test_models.py -v`
Expected: PASS (4 passed).

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/models/policy_review.py backend/open_webui/test/policy_review/conftest.py backend/open_webui/test/policy_review/test_models.py
git commit -m "feat(policy-review): add DB models + async DAO for checklist/reviews/library/audit"
```

---

## Task 3: Alembic migration for the four tables

The app auto-runs Alembic migrations at startup (`run_migrations()` in `config.py`). Tests use `create_all` (Task 2) and don't need this, but production does.

**Files:**
- Create: `backend/open_webui/migrations/versions/<generated>_add_policy_review_tables.py`

- [ ] **Step 1: Generate the revision skeleton (auto-resolves `down_revision` to the current head)**

Run: `cd backend && python -m alembic -c open_webui/alembic.ini revision -m "add policy review tables"`
Expected: prints `Generating .../open_webui/migrations/versions/<hash>_add_policy_review_tables.py ... done`. Open that file. The generated header already sets `revision` and `down_revision` correctly — **do not edit those lines.**

- [ ] **Step 2: Fill in `upgrade()` and `downgrade()`**

Replace the generated empty `upgrade()`/`downgrade()` with:

```python
def upgrade():
    op.create_table(
        'policy_checklist_version',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('label', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('published_at', sa.BigInteger(), nullable=True),
        sa.Column('published_by_id', sa.Text(), nullable=True),
        sa.Column('published_by_name', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_policy_checklist_version_status', 'policy_checklist_version', ['status'])

    op.create_table(
        'policy_review',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('policy_meta', sa.JSON(), nullable=True),
        sa.Column('checklist_version_id', sa.Text(), nullable=True),
        sa.Column('checklist_snapshot', sa.JSON(), nullable=True),
        sa.Column('results', sa.JSON(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('approval', sa.JSON(), nullable=True),
        sa.Column('strengths', sa.JSON(), nullable=True),
        sa.Column('created_by_id', sa.Text(), nullable=True),
        sa.Column('created_by_name', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_policy_review_created_by_id', 'policy_review', ['created_by_id'])
    op.create_index('ix_policy_review_status', 'policy_review', ['status'])

    op.create_table(
        'policy_library',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('code', sa.Text(), nullable=True),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('source_review_id', sa.Text(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )

    op.create_table(
        'policy_audit',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('entity_type', sa.Text(), nullable=True),
        sa.Column('entity_id', sa.Text(), nullable=True),
        sa.Column('action', sa.Text(), nullable=True),
        sa.Column('actor_id', sa.Text(), nullable=True),
        sa.Column('actor_name', sa.Text(), nullable=True),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_policy_audit_entity', 'policy_audit', ['entity_type', 'entity_id'])


def downgrade():
    op.drop_index('ix_policy_audit_entity', table_name='policy_audit')
    op.drop_table('policy_audit')
    op.drop_table('policy_library')
    op.drop_index('ix_policy_review_status', table_name='policy_review')
    op.drop_index('ix_policy_review_created_by_id', table_name='policy_review')
    op.drop_table('policy_review')
    op.drop_index('ix_policy_checklist_version_status', table_name='policy_checklist_version')
    op.drop_table('policy_checklist_version')
```

Ensure the file imports both `from alembic import op` and `import sqlalchemy as sa` (the generated skeleton includes them).

- [ ] **Step 3: Verify the migration applies and reverses on a scratch DB**

Run:
```bash
cd backend && DATABASE_URL="sqlite:///./_scratch_migrate.db" python -m alembic -c open_webui/alembic.ini upgrade head && \
DATABASE_URL="sqlite:///./_scratch_migrate.db" python -m alembic -c open_webui/alembic.ini downgrade -1 && \
DATABASE_URL="sqlite:///./_scratch_migrate.db" python -m alembic -c open_webui/alembic.ini upgrade head
```
Expected: each command exits 0 with no "Can't locate revision" / "multiple heads" errors. Then remove the scratch DB: `rm backend/_scratch_migrate.db`.

(On Windows PowerShell, set the env var per command instead: `$env:DATABASE_URL="sqlite:///./_scratch_migrate.db"; python -m alembic -c open_webui/alembic.ini upgrade head`.)

- [ ] **Step 4: Commit**

```bash
git add backend/open_webui/migrations/versions/*_add_policy_review_tables.py
git commit -m "feat(policy-review): Alembic migration for the four policy tables"
```

---

## Task 4: Export the canonical seed data from the frontend to JSON

The seed builders live in [seed.ts](src/lib/components/policy-review/lib/seed.ts) and import only type-only modules, so they run cleanly under vitest with the project's vite aliases. We run a one-off vitest test that writes a committed JSON the backend seeder reads.

**Files:**
- Create: `src/lib/components/policy-review/lib/exportSeed.test.ts`
- Create (generated): `backend/open_webui/internal/policy_review/seed_data.json`

- [ ] **Step 1: Write the export test**

`src/lib/components/policy-review/lib/exportSeed.test.ts`:

```ts
import { it } from 'vitest';
import { writeFileSync, mkdirSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { buildActiveVersion, buildSeedReviews, POLICIES } from './seed';

it('export policy seed data to backend JSON', () => {
	const active = buildActiveVersion();
	const reviews = buildSeedReviews();
	const payload = {
		activeVersion: active,
		library: POLICIES,
		reviews
	};
	const out = resolve('backend/open_webui/internal/policy_review/seed_data.json');
	mkdirSync(dirname(out), { recursive: true });
	writeFileSync(out, JSON.stringify(payload, null, 2));
});
```

- [ ] **Step 2: Run it to generate the JSON**

Run: `npx vitest run src/lib/components/policy-review/lib/exportSeed.test.ts`
Expected: PASS (1 test); the file `backend/open_webui/internal/policy_review/seed_data.json` now exists and contains `activeVersion` (with `themes`, `sections` of 70 items across 6 themes, `standards`, `verdictBands`), `library` (~60 entries), and `reviews` (5 entries).

- [ ] **Step 3: Sanity-check the generated JSON**

Run: `node -e "const d=require('./backend/open_webui/internal/policy_review/seed_data.json'); console.log(d.activeVersion.sections.reduce((a,s)=>a+s.items.length,0), d.library.length, d.reviews.length)"`
Expected: prints `70 60 5` (item count may differ slightly if the seed changed; library/reviews counts should be `60`/`5` — confirm they are non-zero and reasonable).

- [ ] **Step 4: Create the backend package marker**

Create `backend/open_webui/internal/policy_review/__init__.py`:

```python
```

(empty file)

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/policy-review/lib/exportSeed.test.ts backend/open_webui/internal/policy_review/__init__.py backend/open_webui/internal/policy_review/seed_data.json
git commit -m "feat(policy-review): export canonical seed data to committed backend JSON"
```

---

## Task 5: First-run seeder

Loads `seed_data.json` into the DB on startup when the checklist table is empty. Idempotent.

**Files:**
- Create: `backend/open_webui/internal/policy_review/seeder.py`
- Test: `backend/open_webui/test/policy_review/test_seeder.py`

- [ ] **Step 1: Write the failing seeder test**

`backend/open_webui/test/policy_review/test_seeder.py`:

```python
import pytest

from open_webui.internal.policy_review.seeder import seed_policy_review_data
from open_webui.models.policy_review import PolicyChecklistVersions, PolicyReviews, PolicyLibrary


@pytest.mark.asyncio
async def test_seeder_populates_then_is_idempotent():
    await seed_policy_review_data()

    active = await PolicyChecklistVersions.get_active()
    assert active is not None
    assert active.label == 'v2.0'
    item_count = sum(len(s.get('items', [])) for s in active.data['sections'])
    assert item_count > 0

    library_count = len(await PolicyLibrary.list_all())
    pending = await PolicyReviews.list_by_status('pending')
    assert library_count > 0
    assert len(pending) > 0  # demo reviews include pending ones

    # Second run must not duplicate.
    await seed_policy_review_data()
    assert len(await PolicyChecklistVersions.list_versions()) == 1
    assert len(await PolicyLibrary.list_all()) == library_count
```

- [ ] **Step 2: Run it to confirm it fails**

Run: `cd backend && python -m pytest open_webui/test/policy_review/test_seeder.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'open_webui.internal.policy_review.seeder'`.

- [ ] **Step 3: Implement the seeder**

Maps the frontend `LibraryPolicy`/`Review` shapes onto the DB rows. The frontend `Review` uses `checklistVersionId` and a name string for `createdBy`; we snapshot the seeded active version's `data` and set `created_by_id = None` for demo reviews.

`backend/open_webui/internal/policy_review/seeder.py`:

```python
import json
import logging
from pathlib import Path

from open_webui.models.policy_review import (
    PolicyChecklistVersions,
    PolicyReviews,
    PolicyLibrary,
)

log = logging.getLogger(__name__)

_SEED_FILE = Path(__file__).parent / 'seed_data.json'


async def seed_policy_review_data() -> None:
    """Idempotently seed the canonical checklist, demo library, and demo reviews.

    Runs only when no checklist version exists yet (first run).
    """
    existing = await PolicyChecklistVersions.list_versions()
    if existing:
        return

    if not _SEED_FILE.exists():
        log.warning('Policy Review seed_data.json missing; skipping seed.')
        return

    payload = json.loads(_SEED_FILE.read_text(encoding='utf-8'))
    active_raw = payload['activeVersion']

    # 1) Active checklist version. The frontend stores themes/sections/standards/
    #    verdictBands/changeSummary; lift them into `data`.
    data = {
        'changeSummary': active_raw.get('changeSummary', ''),
        'themes': active_raw.get('themes', []),
        'sections': active_raw.get('sections', []),
        'verdictBands': active_raw.get('verdictBands', {'approved': 85, 'conditional': 70}),
        'standards': active_raw.get('standards', []),
    }
    active = await PolicyChecklistVersions.insert_version(
        label=active_raw.get('label', 'v2.0'),
        status='active',
        data=data,
        published_by_id=None,
        published_by_name=active_raw.get('publishedBy') or 'Organizational Excellence',
    )

    # 2) Library canon.
    for entry in payload.get('library', []):
        await PolicyLibrary.upsert(code=entry['code'], data=entry, source_review_id=None)

    # 3) Demo reviews (fictional owners → created_by_id None).
    for r in payload.get('reviews', []):
        await PolicyReviews.insert_review(
            created_by_id=None,
            created_by_name=r.get('createdBy', 'Unknown'),
            policy_meta=r.get('policyMeta', {}),
            active_version=active,
            results=r.get('results', {}),
            status=r.get('status', 'draft'),
            approval=r.get('approval'),
            strengths=r.get('strengths', []),
        )

    log.info('Policy Review seed data loaded.')
```

- [ ] **Step 4: Run the seeder test to confirm it passes**

Run: `cd backend && python -m pytest open_webui/test/policy_review/test_seeder.py -v`
Expected: PASS (1 passed).

- [ ] **Step 5: Wire the seeder into startup**

In `backend/open_webui/main.py`, find the `lifespan` async context manager (search for `async def lifespan`). Inside it, after the existing startup work and before `yield`, add the seeding call guarded so a failure never blocks boot:

```python
    # Seed Policy Review canonical data on first run.
    try:
        from open_webui.internal.policy_review.seeder import seed_policy_review_data

        await seed_policy_review_data()
    except Exception as e:
        log.exception(f'Policy Review seeding failed: {e}')
```

(If `log` is not in scope at that point, use `logging.getLogger(__name__)`.)

- [ ] **Step 6: Commit**

```bash
git add backend/open_webui/internal/policy_review/seeder.py backend/open_webui/test/policy_review/test_seeder.py backend/open_webui/main.py
git commit -m "feat(policy-review): first-run seeder for checklist + library + demo reviews"
```

---

## Task 6: Router — checklist endpoints + permission enforcement

**Files:**
- Create: `backend/open_webui/routers/policy_review.py`
- Test: `backend/open_webui/test/policy_review/test_router_checklist.py`

- [ ] **Step 1: Write the router test harness + failing checklist tests**

This boots a minimal FastAPI app containing only the policy router, overrides `get_verified_user` to inject a chosen user, monkeypatches `has_permission` to a controllable result, and shares the test SQLite engine (the autouse `_create_schema` fixture from `conftest.py` creates the tables).

`backend/open_webui/test/policy_review/test_router_checklist.py`:

```python
import pytest
import pytest_asyncio
from types import SimpleNamespace

import httpx
from httpx import ASGITransport
from fastapi import FastAPI

import open_webui.routers.policy_review as pr_router
from open_webui.utils.auth import get_verified_user
from open_webui.models.policy_review import PolicyChecklistVersions

ACTIVE_DATA = {'changeSummary': 'init', 'themes': [{'id': 'T1', 'name': 'T1', 'weight': 100, 'gate': True, 'threshold': 85}], 'sections': [{'id': 'S1', 'theme': 'T1', 'items': [{'id': 'S1-1'}]}], 'verdictBands': {'approved': 85, 'conditional': 70}, 'standards': []}


def _make_app(current_user):
    app = FastAPI()
    app.state.config = SimpleNamespace(USER_PERMISSIONS={})
    app.include_router(pr_router.router, prefix='/api/v1/policy')
    app.dependency_overrides[get_verified_user] = lambda: current_user
    return app


@pytest_asyncio.fixture
async def client_factory(monkeypatch):
    def factory(role='user', allow=True):
        monkeypatch.setattr(pr_router, 'has_permission', _AsyncReturn(allow))
        user = SimpleNamespace(id='u1', role=role, name='Tester', email='t@x.io')
        app = _make_app(user)
        return httpx.AsyncClient(transport=ASGITransport(app=app), base_url='http://test')

    return factory


class _AsyncReturn:
    def __init__(self, value):
        self.value = value

    async def __call__(self, *args, **kwargs):
        return self.value


@pytest.mark.asyncio
async def test_get_active_requires_seeded_version(client_factory):
    await PolicyChecklistVersions.insert_version('v2.0', 'active', ACTIVE_DATA, None, 'OE')
    async with client_factory(role='user', allow=True) as client:
        res = await client.get('/api/v1/policy/checklist/active')
    assert res.status_code == 200
    assert res.json()['label'] == 'v2.0'


@pytest.mark.asyncio
async def test_start_draft_requires_admin_permission(client_factory):
    await PolicyChecklistVersions.insert_version('v2.0', 'active', ACTIVE_DATA, None, 'OE')
    # Lacks policy_admin -> 401
    async with client_factory(role='user', allow=False) as client:
        res = await client.post('/api/v1/policy/checklist/draft')
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_admin_can_start_and_publish_draft(client_factory):
    await PolicyChecklistVersions.insert_version('v2.0', 'active', ACTIVE_DATA, None, 'OE')
    async with client_factory(role='admin', allow=False) as client:  # admin bypass
        start = await client.post('/api/v1/policy/checklist/draft')
        assert start.status_code == 200
        publish = await client.post('/api/v1/policy/checklist/draft/publish')
        assert publish.status_code == 200
        assert publish.json()['label'] == 'v2.1'
```

- [ ] **Step 2: Run to confirm it fails**

Run: `cd backend && python -m pytest open_webui/test/policy_review/test_router_checklist.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'open_webui.routers.policy_review'`.

- [ ] **Step 3: Implement the router scaffold + checklist endpoints**

`backend/open_webui/routers/policy_review.py`:

```python
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from open_webui.constants import ERROR_MESSAGES
from open_webui.internal.db import get_async_session
from open_webui.utils.auth import get_verified_user
from open_webui.utils.access_control import has_permission
from open_webui.utils.policy_review.scoring import compute_scores
from open_webui.models.policy_review import (
    PolicyChecklistVersions,
    PolicyReviews,
    PolicyLibrary,
    PolicyAudits,
)

log = logging.getLogger(__name__)

router = APIRouter()


# ──────────────────────────── helpers ────────────────────────────


async def _require(request: Request, user, key: str, db: AsyncSession) -> None:
    """Raise 401 unless the user is an admin or holds features.<key>."""
    if user.role != 'admin' and not await has_permission(
        user.id, f'features.{key}', request.app.state.config.USER_PERMISSIONS, db=db
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ERROR_MESSAGES.UNAUTHORIZED)


# ──────────────────────────── checklist ────────────────────────────


class ChecklistDataForm(BaseModel):
    data: dict


@router.get('/checklist/active')
async def get_active_checklist(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    active = await PolicyChecklistVersions.get_active(db=db)
    if not active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return active


@router.get('/checklist/versions')
async def list_checklist_versions(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_admin', db)
    return await PolicyChecklistVersions.list_versions(db=db)


@router.get('/checklist/versions/{version_id}')
async def get_checklist_version(
    request: Request, version_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_admin', db)
    version = await PolicyChecklistVersions.get_by_id(version_id, db=db)
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return version


@router.get('/checklist/draft')
async def get_checklist_draft(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_admin', db)
    return await PolicyChecklistVersions.get_draft(db=db)


@router.post('/checklist/draft')
async def start_checklist_draft(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_admin', db)
    draft = await PolicyChecklistVersions.start_draft(db=db)
    if not draft:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='No active version to clone.')
    return draft


@router.put('/checklist/draft')
async def save_checklist_draft(
    request: Request, form: ChecklistDataForm, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_admin', db)
    saved = await PolicyChecklistVersions.save_draft(form.data, db=db)
    if not saved:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No draft to save.')
    return saved


@router.delete('/checklist/draft')
async def discard_checklist_draft(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_admin', db)
    await PolicyChecklistVersions.discard_draft(db=db)
    return {'success': True}


def _validate_checklist_data(data: dict) -> list[str]:
    """Mirror checklist.ts validateDraft."""
    errors: list[str] = []
    themes = data.get('themes', [])
    sections = data.get('sections', [])
    weight_sum = sum(t.get('weight', 0) for t in themes)
    if round(weight_sum) != 100:
        errors.append(f'Theme weights must sum to 100% (currently {round(weight_sum)}%).')
    for t in themes:
        secs = [s for s in sections if s.get('theme') == t['id']]
        if not secs:
            errors.append(f"Theme {t['id']} has no PRP groups.")
        if sum(len(s.get('items', [])) for s in secs) == 0:
            errors.append(f"Theme {t['id']} has no items.")
    for s in sections:
        if not s.get('items'):
            errors.append(f"Group {s['id']} has no items.")
    return errors


@router.post('/checklist/draft/publish')
async def publish_checklist_draft(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_admin', db)
    draft = await PolicyChecklistVersions.get_draft(db=db)
    if not draft:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='No draft to publish.')
    errors = _validate_checklist_data(draft.data or {})
    if errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=' '.join(errors))
    published = await PolicyChecklistVersions.publish_draft(by_id=user.id, by_name=user.name, db=db)
    await PolicyAudits.insert('checklist', published.id, 'checklist_published', user.id, user.name, {'label': published.label}, db=db)
    return published
```

Note: this references `ERROR_MESSAGES.NOT_FOUND` — confirm that member exists in `backend/open_webui/constants.py` (search for `NOT_FOUND`). If it does not, use the literal string `'404 Not Found'` instead.

- [ ] **Step 4: Run the checklist router tests to confirm they pass**

Run: `cd backend && python -m pytest open_webui/test/policy_review/test_router_checklist.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/policy_review.py backend/open_webui/test/policy_review/test_router_checklist.py
git commit -m "feat(policy-review): checklist router endpoints with policy_admin enforcement"
```

---

## Task 7: Router — reviews lifecycle + library upsert on approve

**Files:**
- Modify: `backend/open_webui/routers/policy_review.py`
- Test: `backend/open_webui/test/policy_review/test_router_reviews.py`

- [ ] **Step 1: Write the failing lifecycle tests**

`backend/open_webui/test/policy_review/test_router_reviews.py`:

```python
import pytest
import pytest_asyncio
from types import SimpleNamespace

import httpx
from httpx import ASGITransport
from fastapi import FastAPI

import open_webui.routers.policy_review as pr_router
from open_webui.utils.auth import get_verified_user
from open_webui.models.policy_review import PolicyChecklistVersions, PolicyLibrary

# One theme, one item -> compliant => fully resolved, score 100, gates pass.
ACTIVE_DATA = {
    'changeSummary': 'init',
    'themes': [{'id': 'T1', 'name': 'T1', 'weight': 100, 'gate': True, 'threshold': 85}],
    'sections': [{'id': 'S1', 'theme': 'T1', 'items': [{'id': 'S1-1', 'assessment': 'auto'}]}],
    'verdictBands': {'approved': 85, 'conditional': 70},
    'standards': [],
}

META = {'name': 'Test Policy', 'code': 'C-TEST', 'version': 'v1', 'owner': 'O', 'reviewer': 'R', 'reviewDate': 'd', 'pages': 1, 'filename': 'f.pdf'}


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


def _client(monkeypatch, *, user, allow=True):
    monkeypatch.setattr(pr_router, 'has_permission', _AsyncReturn(allow))
    return httpx.AsyncClient(transport=ASGITransport(app=_make_app(user)), base_url='http://test')


@pytest_asyncio.fixture(autouse=True)
async def _seed_active():
    await PolicyChecklistVersions.insert_version('v2.0', 'active', ACTIVE_DATA, None, 'OE')


@pytest.mark.asyncio
async def test_full_lifecycle_create_submit_approve_publishes(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')

    # Create
    async with _client(monkeypatch, user=reviewer) as c:
        created = await c.post('/api/v1/policy/reviews', json={'policy_meta': META})
        assert created.status_code == 200
        rid = created.json()['id']
        assert created.json()['status'] == 'draft'
        assert created.json()['checklist_snapshot']['changeSummary'] == 'init'

        # Submit blocked while item is pending
        blocked = await c.post(f'/api/v1/policy/reviews/{rid}/submit')
        assert blocked.status_code == 400

        # Resolve the only item, then submit
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        ok = await c.post(f'/api/v1/policy/reviews/{rid}/submit')
        assert ok.status_code == 200
        assert ok.json()['status'] == 'pending'

    # Approver sees it in the queue and approves
    async with _client(monkeypatch, user=approver) as c:
        queue = await c.get('/api/v1/policy/reviews/queue')
        assert any(r['id'] == rid for r in queue.json())
        approved = await c.post(f'/api/v1/policy/reviews/{rid}/approve', json={'note': 'ok'})
        assert approved.status_code == 200
        assert approved.json()['status'] == 'approved'

    # Published into the library
    entry = await PolicyLibrary.get_by_code('C-TEST')
    assert entry is not None
    assert entry.data['score'] == 100


@pytest.mark.asyncio
async def test_non_reviewer_cannot_create(monkeypatch):
    user = SimpleNamespace(id='x', role='user', name='X', email='x@x.io')
    async with _client(monkeypatch, user=user, allow=False) as c:
        res = await c.post('/api/v1/policy/reviews', json={'policy_meta': META})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_reject_requires_note_and_returns_to_owner(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    approver = SimpleNamespace(id='app1', role='user', name='Approver', email='a@x.io')

    async with _client(monkeypatch, user=reviewer) as c:
        rid = (await c.post('/api/v1/policy/reviews', json={'policy_meta': META})).json()['id']
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        await c.post(f'/api/v1/policy/reviews/{rid}/submit')

    async with _client(monkeypatch, user=approver) as c:
        no_note = await c.post(f'/api/v1/policy/reviews/{rid}/reject', json={'note': ''})
        assert no_note.status_code == 400
        rejected = await c.post(f'/api/v1/policy/reviews/{rid}/reject', json={'note': 'fix it'})
        assert rejected.status_code == 200
        assert rejected.json()['status'] == 'rejected'

    # Owner edits a rejected review -> reopens to draft
    async with _client(monkeypatch, user=reviewer) as c:
        reopened = await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'non-compliant'}}})
        assert reopened.status_code == 200
        assert reopened.json()['status'] == 'draft'


@pytest.mark.asyncio
async def test_cannot_edit_after_submit(monkeypatch):
    reviewer = SimpleNamespace(id='rev1', role='user', name='Reviewer', email='r@x.io')
    async with _client(monkeypatch, user=reviewer) as c:
        rid = (await c.post('/api/v1/policy/reviews', json={'policy_meta': META})).json()['id']
        await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'compliant'}}})
        await c.post(f'/api/v1/policy/reviews/{rid}/submit')
        # Now pending -> editing must be refused
        res = await c.patch(f'/api/v1/policy/reviews/{rid}/results', json={'results': {'S1-1': {'result': 'non-compliant'}}})
    assert res.status_code == 403
```

- [ ] **Step 2: Run to confirm it fails**

Run: `cd backend && python -m pytest open_webui/test/policy_review/test_router_reviews.py -v`
Expected: FAIL — review endpoints return 404 (routes not defined yet).

- [ ] **Step 3: Add the review endpoints to the router**

Append to `backend/open_webui/routers/policy_review.py` (after the checklist section):

```python
# ──────────────────────────── reviews ────────────────────────────


class ReviewCreateForm(BaseModel):
    policy_meta: dict
    strengths: Optional[list] = None


class ResultsForm(BaseModel):
    results: dict


class NoteForm(BaseModel):
    note: Optional[str] = ''


async def _load_owned_or_403(review_id: str, user, db, *, approver_ok: bool = False, request: Request = None):
    review = await PolicyReviews.get_by_id(review_id, db=db)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    is_owner = review.created_by_id is not None and review.created_by_id == user.id
    if is_owner or user.role == 'admin':
        return review
    if approver_ok:
        return review
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ERROR_MESSAGES.ACCESS_PROHIBITED)


@router.post('/reviews')
async def create_review(
    request: Request, form: ReviewCreateForm, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_checker', db)
    active = await PolicyChecklistVersions.get_active(db=db)
    if not active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='No active checklist version.')
    review = await PolicyReviews.insert_review(
        created_by_id=user.id,
        created_by_name=user.name,
        policy_meta=form.policy_meta,
        active_version=active,
        strengths=form.strengths or [],
        db=db,
    )
    await PolicyAudits.insert('review', review.id, 'created', user.id, user.name, None, db=db)
    return review


@router.get('/reviews/mine')
async def list_my_reviews(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_checker', db)
    return await PolicyReviews.list_by_creator(user.id, db=db)


@router.get('/reviews/queue')
async def list_approval_queue(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_approver', db)
    return await PolicyReviews.list_by_status('pending', db=db)


@router.get('/reviews/{review_id}')
async def get_review(
    request: Request, review_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    # Owner, admin, or any approver may read.
    is_approver = user.role == 'admin' or await has_permission(
        user.id, 'features.policy_approver', request.app.state.config.USER_PERMISSIONS, db=db
    )
    return await _load_owned_or_403(review_id, user, db, approver_ok=is_approver, request=request)


@router.patch('/reviews/{review_id}/results')
async def update_review_results(
    request: Request, review_id: str, form: ResultsForm, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_checker', db)
    review = await _load_owned_or_403(review_id, user, db)
    if review.status not in ('draft', 'rejected'):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Review is locked.')
    merged = {**(review.results or {})}
    for item_id, patch in form.results.items():
        merged[item_id] = {**(merged.get(item_id) or {}), **patch}
    fields = {'results': merged}
    if review.status == 'rejected':
        fields['status'] = 'draft'  # editing a returned review reopens it
        await PolicyAudits.insert('review', review_id, 'reopened', user.id, user.name, None, db=db)
    updated = await PolicyReviews.update_fields(review_id, fields, db=db)
    await PolicyAudits.insert('review', review_id, 'updated', user.id, user.name, None, db=db)
    return updated


@router.post('/reviews/{review_id}/submit')
async def submit_review(
    request: Request, review_id: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_checker', db)
    review = await _load_owned_or_403(review_id, user, db)
    if review.status != 'draft':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only a draft can be submitted.')
    score = compute_scores(review.checklist_snapshot or {}, review.results or {})
    if score['humanItemsRemain']:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Resolve all items before submitting.')
    approval = {**(review.approval or {}), 'status': 'pending', 'sentAt': _audit_now(), 'note': ''}
    updated = await PolicyReviews.update_fields(review_id, {'status': 'pending', 'approval': approval}, db=db)
    await PolicyAudits.insert('review', review_id, 'submitted', user.id, user.name, None, db=db)
    return updated


@router.post('/reviews/{review_id}/approve')
async def approve_review(
    request: Request, review_id: str, form: NoteForm, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_approver', db)
    review = await PolicyReviews.get_by_id(review_id, db=db)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    if review.status != 'pending':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only a pending review can be approved.')
    score = compute_scores(review.checklist_snapshot or {}, review.results or {})
    approval = {
        **(review.approval or {}),
        'status': 'approved',
        'decidedAt': _audit_now(),
        'decidedBy': user.name,
        'note': (form.note or '').strip() or 'Approved for issuance and published to the policy library.',
    }
    updated = await PolicyReviews.update_fields(review_id, {'status': 'approved', 'approval': approval}, db=db)
    # Upsert into the library.
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
    await PolicyLibrary.upsert(code=meta.get('code'), data=library_data, source_review_id=review_id, db=db)
    await PolicyAudits.insert('review', review_id, 'approved', user.id, user.name, {'score': score['overall']}, db=db)
    await PolicyAudits.insert('review', review_id, 'published', user.id, user.name, {'code': meta.get('code')}, db=db)
    return updated


@router.post('/reviews/{review_id}/reject')
async def reject_review(
    request: Request, review_id: str, form: NoteForm, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require(request, user, 'policy_approver', db)
    review = await PolicyReviews.get_by_id(review_id, db=db)
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    if review.status != 'pending':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Only a pending review can be rejected.')
    if not (form.note or '').strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='A rejection note is required.')
    approval = {
        **(review.approval or {}),
        'status': 'rejected',
        'decidedAt': _audit_now(),
        'decidedBy': user.name,
        'note': form.note.strip(),
    }
    updated = await PolicyReviews.update_fields(review_id, {'status': 'rejected', 'approval': approval}, db=db)
    await PolicyAudits.insert('review', review_id, 'rejected', user.id, user.name, {'note': form.note.strip()}, db=db)
    return updated
```

Also add this small helper near the top of the file (after `router = APIRouter()`), used for human-readable timestamps in `approval`:

```python
import time


def _audit_now() -> str:
    # Human-readable stamp matching the frontend's display style; stored in `approval`.
    return time.strftime('%d %b, %H:%M', time.gmtime())
```

- [ ] **Step 4: Run the reviews lifecycle tests to confirm they pass**

Run: `cd backend && python -m pytest open_webui/test/policy_review/test_router_reviews.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/routers/policy_review.py backend/open_webui/test/policy_review/test_router_reviews.py
git commit -m "feat(policy-review): reviews lifecycle endpoints with locking + library publish"
```

---

## Task 8: Router — library endpoints + register in main.py

**Files:**
- Modify: `backend/open_webui/routers/policy_review.py`
- Modify: `backend/open_webui/main.py`
- Test: `backend/open_webui/test/policy_review/test_router_library.py`

- [ ] **Step 1: Write the failing library tests**

`backend/open_webui/test/policy_review/test_router_library.py`:

```python
import pytest
from types import SimpleNamespace

import httpx
from httpx import ASGITransport
from fastapi import FastAPI

import open_webui.routers.policy_review as pr_router
from open_webui.utils.auth import get_verified_user
from open_webui.models.policy_review import PolicyLibrary


def _client(user):
    app = FastAPI()
    app.state.config = SimpleNamespace(USER_PERMISSIONS={})
    app.include_router(pr_router.router, prefix='/api/v1/policy')
    app.dependency_overrides[get_verified_user] = lambda: user
    return httpx.AsyncClient(transport=ASGITransport(app=app), base_url='http://test')


@pytest.mark.asyncio
async def test_library_open_to_any_verified_user():
    await PolicyLibrary.upsert(code='C-1', data={'code': 'C-1', 'title': 'First'}, source_review_id=None)
    user = SimpleNamespace(id='u', role='user', name='Any', email='a@x.io')
    async with _client(user) as c:
        lst = await c.get('/api/v1/policy/library')
        assert lst.status_code == 200
        assert len(lst.json()) == 1
        one = await c.get('/api/v1/policy/library/C-1')
        assert one.status_code == 200
        assert one.json()['data']['title'] == 'First'
        missing = await c.get('/api/v1/policy/library/NOPE')
        assert missing.status_code == 404
```

- [ ] **Step 2: Run to confirm it fails**

Run: `cd backend && python -m pytest open_webui/test/policy_review/test_router_library.py -v`
Expected: FAIL — library routes return 404.

- [ ] **Step 3: Add the library endpoints**

Append to `backend/open_webui/routers/policy_review.py`:

```python
# ──────────────────────────── library ────────────────────────────


@router.get('/library')
async def list_library(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    return await PolicyLibrary.list_all(db=db)


@router.get('/library/{code}')
async def get_library_entry(
    request: Request, code: str, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    entry = await PolicyLibrary.get_by_code(code, db=db)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ERROR_MESSAGES.NOT_FOUND)
    return entry
```

- [ ] **Step 4: Register the router in main.py**

In `backend/open_webui/main.py`, add `policy_review` to the `from open_webui.routers import (...)` block (the alphabetical list starting at line ~78):

```python
    policy_review,
```

Then, next to the other `app.include_router(...)` calls (near line ~1438 where `notes.router` is registered), add:

```python
app.include_router(policy_review.router, prefix='/api/v1/policy', tags=['policy'])
```

- [ ] **Step 5: Run the library tests + the whole policy suite to confirm green**

Run: `cd backend && python -m pytest open_webui/test/policy_review/ -v`
Expected: PASS (all policy tests green).

- [ ] **Step 6: Verify the app imports cleanly with the router registered**

Run: `cd backend && python -c "import open_webui.main"`
Expected: exits 0 with no ImportError (confirms `main.py` edits and the router import are valid).

- [ ] **Step 7: Commit**

```bash
git add backend/open_webui/routers/policy_review.py backend/open_webui/main.py backend/open_webui/test/policy_review/test_router_library.py
git commit -m "feat(policy-review): library endpoints + register policy router at /api/v1/policy"
```

---

## Task 9: Frontend API client

**Files:**
- Create: `src/lib/components/policy-review/lib/api.ts`

- [ ] **Step 1: Write the API client**

Mirrors the existing fetch convention from [src/lib/apis/notes/index.ts](src/lib/apis/notes/index.ts): `WEBUI_API_BASE_URL` base, Bearer token, throw `err.detail` on non-OK.

`src/lib/components/policy-review/lib/api.ts`:

```ts
import { WEBUI_API_BASE_URL } from '$lib/constants';
import type { ChecklistVersion, Review, LibraryPolicy } from './types';

const BASE = `${WEBUI_API_BASE_URL}/policy`;

async function request<T>(token: string, path: string, method = 'GET', body?: unknown): Promise<T> {
	let error: unknown = null;
	const res = await fetch(`${BASE}${path}`, {
		method,
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		...(body !== undefined ? { body: JSON.stringify(body) } : {})
	})
		.then(async (r) => {
			if (!r.ok) throw await r.json();
			return r.json();
		})
		.catch((err) => {
			error = err?.detail ?? err;
			console.error(err);
			return null;
		});
	if (error) throw error;
	return res as T;
}

// ── Checklist ──
export const getActiveChecklist = (token: string) =>
	request<ChecklistVersion>(token, '/checklist/active');
export const getChecklistVersions = (token: string) =>
	request<ChecklistVersion[]>(token, '/checklist/versions');
export const getChecklistDraft = (token: string) =>
	request<ChecklistVersion | null>(token, '/checklist/draft');
export const startChecklistDraft = (token: string) =>
	request<ChecklistVersion>(token, '/checklist/draft', 'POST');
export const saveChecklistDraft = (token: string, data: unknown) =>
	request<ChecklistVersion>(token, '/checklist/draft', 'PUT', { data });
export const publishChecklistDraft = (token: string) =>
	request<ChecklistVersion>(token, '/checklist/draft/publish', 'POST');
export const discardChecklistDraft = (token: string) =>
	request<{ success: boolean }>(token, '/checklist/draft', 'DELETE');

// ── Reviews ──
export const createReviewApi = (token: string, policy_meta: unknown, strengths: string[] = []) =>
	request<Review>(token, '/reviews', 'POST', { policy_meta, strengths });
export const getMyReviews = (token: string) => request<Review[]>(token, '/reviews/mine');
export const getApprovalQueue = (token: string) => request<Review[]>(token, '/reviews/queue');
export const getReviewApi = (token: string, id: string) => request<Review>(token, `/reviews/${id}`);
export const updateResultsApi = (token: string, id: string, results: unknown) =>
	request<Review>(token, `/reviews/${id}/results`, 'PATCH', { results });
export const submitReviewApi = (token: string, id: string) =>
	request<Review>(token, `/reviews/${id}/submit`, 'POST');
export const approveReviewApi = (token: string, id: string, note: string) =>
	request<Review>(token, `/reviews/${id}/approve`, 'POST', { note });
export const rejectReviewApi = (token: string, id: string, note: string) =>
	request<Review>(token, `/reviews/${id}/reject`, 'POST', { note });

// ── Library ──
export const getLibrary = (token: string) =>
	request<Array<{ code: string; data: LibraryPolicy }>>(token, '/library');
```

- [ ] **Step 2: Type-check it**

Run: `npx svelte-check --tsconfig ./tsconfig.json --threshold error 2>&1 | grep -i policy-review/lib/api || echo "no api.ts type errors"`
Expected: prints `no api.ts type errors` (the new file introduces no type errors). If errors are reported, fix the type imports/signatures.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/policy-review/lib/api.ts
git commit -m "feat(policy-review): frontend API client for the policy backend"
```

---

## Task 10: Rewire the store from localStorage to the API + snapshot fix

This is the highest-touch frontend change. The exported store names and mutator names stay identical so **no view changes are needed**; only their bodies change. The backend returns reviews with `checklist_snapshot`, `created_by_id`, `policy_meta`, etc. (snake_case) — we map those to the frontend camelCase types at the API boundary.

**Files:**
- Modify: `src/lib/components/policy-review/lib/store.ts`
- Modify: `src/lib/components/policy-review/lib/reviews.ts` (the `versionFor` snapshot fix)
- Modify: `src/lib/components/policy-review/lib/types.ts` (add `checklistSnapshot` to `Review`)

- [ ] **Step 1: Add the snapshot field to the Review type**

In `src/lib/components/policy-review/lib/types.ts`, in the `Review` interface, add after `checklistVersionId`:

```ts
	checklistSnapshot?: ChecklistVersion; // pinned copy returned by the backend
```

- [ ] **Step 2: Fix `versionFor` to prefer the pinned snapshot**

In `src/lib/components/policy-review/lib/reviews.ts`, replace the body of `versionFor` with:

```ts
export function versionFor(
	review: Review,
	versions: ChecklistVersion[]
): ChecklistVersion | undefined {
	// Prefer the review's own pinned snapshot — never re-grade against a newer active version.
	if (review.checklistSnapshot) return review.checklistSnapshot;
	return (
		versions.find((v) => v.id === review.checklistVersionId) ??
		versions.find((v) => v.status === 'active') ??
		versions[0]
	);
}
```

- [ ] **Step 3: Add a mapping helper + rewrite store init and mutators**

Replace `src/lib/components/policy-review/lib/store.ts` with the API-backed version below. It keeps every exported binding the views already use (`checklistVersions`, `checklistDraft`, `reviews`, `activeReviewId`, `stage`, `view`, `activeVersion`, `activeReview`, `approvalQueue`, `myReviews`, `publishedPolicies`, `canUseChecker`, `canApprove`, `canAdmin`, transient UI stores, and all mutators). The mutators become async and call the API, then refresh the stores.

`src/lib/components/policy-review/lib/store.ts`:

```ts
// API-backed stores for the Policy Review tool (Phase 1 backend).
// Public store/mutator names are unchanged so views need no edits.

import { writable, get, derived, type Writable } from 'svelte/store';
import { browser } from '$app/environment';
import type {
	ChecklistVersion,
	ItemResult,
	LibraryPolicy,
	Review,
	Stage,
	ViewKey
} from './types';
import { user } from '$lib/stores';
import * as api from './api';

function token(): string {
	return browser ? localStorage.token : '';
}

// Map a backend review (snake_case + snapshot) to the frontend Review shape.
function mapReview(r: any): Review {
	return {
		id: r.id,
		policyMeta: r.policy_meta,
		checklistVersionId: r.checklist_version_id,
		checklistSnapshot: r.checklist_snapshot
			? ({ ...r.checklist_snapshot, id: r.checklist_version_id, status: 'archived' } as ChecklistVersion)
			: undefined,
		results: r.results ?? {},
		status: r.status,
		approval: r.approval ?? { status: 'idle', sentAt: null, decidedAt: null, decidedBy: null, note: '' },
		strengths: r.strengths ?? [],
		createdBy: r.created_by_name,
		createdAt: r.created_at ? String(r.created_at) : ''
	};
}

function mapVersion(v: any): ChecklistVersion {
	const d = v.data ?? {};
	return {
		id: v.id,
		label: v.label,
		status: v.status,
		publishedAt: v.published_at ? String(v.published_at) : null,
		publishedBy: v.published_by_name ?? null,
		changeSummary: d.changeSummary ?? '',
		themes: d.themes ?? [],
		sections: d.sections ?? [],
		verdictBands: d.verdictBands ?? { approved: 85, conditional: 70 },
		standards: d.standards ?? []
	};
}

// ── Stores ──
export const checklistVersions: Writable<ChecklistVersion[]> = writable([]);
export const checklistDraft: Writable<ChecklistVersion | null> = writable(null);
export const reviews: Writable<Review[]> = writable([]);
export const activeReviewId: Writable<string | null> = writable(null);
export const stage: Writable<Stage> = writable('upload');
export const view: Writable<ViewKey> = writable('overview');
export const libraryEntries: Writable<LibraryPolicy[]> = writable([]);

// ── Derived ──
export const activeVersion = derived(checklistVersions, ($v) => $v.find((x) => x.status === 'active') ?? $v[0]);
export const activeReview = derived([reviews, activeReviewId], ([$r, $id]) => $r.find((x) => x.id === $id) ?? null);
export const approvalQueue = derived(reviews, ($r) => $r.filter((x) => x.status === 'pending'));
export const myReviews = derived([reviews, user], ([$r, $u]) => $r.filter((x) => x.createdBy === ($u?.name ?? '')));
export const publishedPolicies = derived(libraryEntries, ($l) => $l);

// ── Access gates (unchanged) ──
export const canUseChecker = derived(user, ($u) => $u?.role === 'admin' || ($u?.permissions?.features?.policy_checker ?? false));
export const canApprove = derived(user, ($u) => $u?.role === 'admin' || ($u?.permissions?.features?.policy_approver ?? false));
export const canAdmin = derived(user, ($u) => $u?.role === 'admin' || ($u?.permissions?.features?.policy_admin ?? false));

// ── Transient UI (not persisted) ──
export const picked: Writable<{ sectionId: string; n: number } | null> = writable(null);
export const drawerOpen: Writable<boolean> = writable(false);
export const submitModalOpen: Writable<boolean> = writable(false);
export const policyPopupOpen: Writable<boolean> = writable(false);
export const selectedPolicy: Writable<LibraryPolicy | null> = writable(null);

// ── Loaders ──
export async function loadChecklist(): Promise<void> {
	const active = await api.getActiveChecklist(token());
	checklistVersions.set([mapVersion(active)]);
}

export async function loadReviews(): Promise<void> {
	const mine = (await api.getMyReviews(token()).catch(() => [])) ?? [];
	let queue: any[] = [];
	if (get(canApprove)) queue = (await api.getApprovalQueue(token()).catch(() => [])) ?? [];
	const byId = new Map<string, Review>();
	[...mine, ...queue].forEach((r) => byId.set(r.id, mapReview(r)));
	reviews.set([...byId.values()]);
}

export async function loadLibrary(): Promise<void> {
	const entries = (await api.getLibrary(token()).catch(() => [])) ?? [];
	libraryEntries.set(entries.map((e: any) => e.data as LibraryPolicy));
}

export async function loadAll(): Promise<void> {
	await Promise.all([loadChecklist(), loadLibrary()]);
	if (get(canUseChecker) || get(canApprove)) await loadReviews();
}

// ── Review mutators ──
export async function updateItemResult(reviewId: string, itemId: string, patch: Partial<ItemResult>): Promise<void> {
	const updated = mapReview(await api.updateResultsApi(token(), reviewId, { [itemId]: patch }));
	reviews.update((arr) => arr.map((r) => (r.id === reviewId ? updated : r)));
}

export function markReviewed(reviewId: string, itemId: string): void {
	void updateItemResult(reviewId, itemId, { reviewed: true, confidence: 0.99 });
}

export function openReview(id: string): void {
	activeReviewId.set(id);
	view.set('review');
}

export function goNewReview(): void {
	activeReviewId.set(null);
	stage.set('upload');
	view.set('new-review');
}

export async function createReview(policyMeta: Review['policyMeta'], strengths: string[] = []): Promise<Review> {
	const created = mapReview(await api.createReviewApi(token(), policyMeta, strengths));
	reviews.update((arr) => [created, ...arr]);
	activeReviewId.set(created.id);
	stage.set('review');
	return created;
}

export async function submitForApproval(reviewId: string, _note: string): Promise<void> {
	const updated = mapReview(await api.submitReviewApi(token(), reviewId));
	reviews.update((arr) => arr.map((r) => (r.id === reviewId ? updated : r)));
}

export async function approveAndPublish(reviewId: string, note?: string): Promise<void> {
	const updated = mapReview(await api.approveReviewApi(token(), reviewId, note ?? ''));
	reviews.update((arr) => arr.map((r) => (r.id === reviewId ? updated : r)));
	await loadLibrary();
}

export async function rejectPolicy(reviewId: string, note?: string): Promise<void> {
	const updated = mapReview(await api.rejectReviewApi(token(), reviewId, note ?? ''));
	reviews.update((arr) => arr.map((r) => (r.id === reviewId ? updated : r)));
}

// ── Checklist draft mutators ──
export async function startDraft(): Promise<void> {
	checklistDraft.set(mapVersion(await api.startChecklistDraft(token())));
}

export async function discardDraft(): Promise<void> {
	await api.discardChecklistDraft(token());
	checklistDraft.set(null);
}

export async function publishDraft(): Promise<{ ok: boolean; errors: string[] }> {
	try {
		const published = mapVersion(await api.publishChecklistDraft(token()));
		checklistVersions.update((arr) => [published, ...arr.map((v) => ({ ...v, status: 'archived' as const }))]);
		checklistDraft.set(null);
		return { ok: true, errors: [] };
	} catch (e) {
		return { ok: false, errors: [String(e)] };
	}
}

// ── Library popup helpers (unchanged) ──
export function openPolicyPopup(policy: LibraryPolicy): void {
	selectedPolicy.set(policy);
	policyPopupOpen.set(true);
}
export function closePolicyPopup(): void {
	policyPopupOpen.set(false);
}
```

- [ ] **Step 4: Trigger `loadAll()` when the tool mounts**

In `src/lib/components/policy-review/PolicyReviewApp.svelte`, import `loadAll` from the store and call it in `onMount`. Add to the `<script>` block:

```ts
import { onMount } from 'svelte';
import { loadAll } from './lib/store';

onMount(() => {
	loadAll();
});
```

(If `onMount` is already imported or an `onMount` block exists, add the `loadAll()` call inside the existing one instead of adding a second import.)

- [ ] **Step 5: Reconcile callers of changed mutators**

Some views call `resetReview()`/`createReview()` and the now-async mutators. Find usages and adjust:

Run: `npx svelte-check --tsconfig ./tsconfig.json --threshold error 2>&1 | grep -iE "policy-review" || echo "no policy-review type errors"`
Expected: lists any view still calling a removed/renamed symbol (e.g. `resetReview`). For each:
- Replace `resetReview()` usage with `goNewReview()` (the upload screen now starts empty; `createReview(meta)` is called on form submit).
- Wire the upload form's submit handler to `await createReview(policyMeta)` (metadata only; file optional/unparsed per the spec).
- `submitForApproval`/`approveAndPublish`/`rejectPolicy`/`updateItemResult`/`startDraft`/`discardDraft`/`publishDraft` are now async — add `await` where their return value or ordering matters; otherwise calls still work.

Repeat svelte-check until it prints `no policy-review type errors`.

- [ ] **Step 6: Build to confirm the frontend compiles**

Run: `npm run build 2>&1 | tail -n 20`
Expected: build completes without errors referencing `policy-review`.

- [ ] **Step 7: Commit**

```bash
git add src/lib/components/policy-review/
git commit -m "feat(policy-review): rewire store to backend API + pin review snapshot in versionFor"
```

---

## Task 11: End-to-end smoke check (manual, with the app running)

**Files:** none (verification only)

- [ ] **Step 1: Start the backend and frontend**

Follow the repo's normal dev run (backend: `cd backend && bash start.sh` or the documented command; frontend: `npm run dev`). On first backend start, the seeder runs (Task 5) and migrations create the tables (Task 3).

- [ ] **Step 2: Verify seeding via the API**

With a valid token (log in via the UI, copy `localStorage.token`), run:
```bash
curl -s -H "authorization: Bearer <token>" http://localhost:8080/api/v1/policy/library | python -c "import sys,json;print(len(json.load(sys.stdin)))"
curl -s -H "authorization: Bearer <token>" http://localhost:8080/api/v1/policy/checklist/active | python -c "import sys,json;d=json.load(sys.stdin);print(d['label'], sum(len(s['items']) for s in d['data']['sections']))"
```
Expected: library count `60`; checklist prints `v2.0 70`.

- [ ] **Step 3: Verify the workflow in the UI**

As a user with `policy_checker`: open the tool, start a New review, fill metadata, set verdicts, submit. As a user with `policy_approver` (second login/browser): confirm the review appears in the Approval queue, approve it, and confirm it now appears in the Policy Library. As `policy_admin`: open Checklist admin, start a draft, publish, and confirm the previously-created review still shows its original snapshot (open it and check the checklist is unchanged).

- [ ] **Step 4: Record the result**

Note any failures and fix in the relevant task. When all three roles work end-to-end and the snapshot holds, Phase 1 is complete.

---

## Self-review (completed during planning)

**Spec coverage:** §3 tables → Task 2 (+ migration Task 3); §4 endpoints → Tasks 6/7/8; §5 enforcement/locking → Tasks 6/7 (tests assert each transition); §6 scoring port → Task 1; §7 rewire + snapshot fix → Tasks 9/10; §8 seeding → Tasks 4/5; §9 testing → tests embedded in every task; §10 file map → matches files created. Audit writes → covered in Tasks 6/7 (no read surface, per spec).

**Placeholder scan:** no TBD/TODO; every code/test block is literal. Two explicit verification branches are intentional, not placeholders: confirm `ERROR_MESSAGES.NOT_FOUND` exists (Task 6 Step 3) and reconcile renamed mutator callers via svelte-check (Task 10 Step 5) — both give an exact fallback.

**Type/name consistency:** DAO singletons (`PolicyChecklistVersions`, `PolicyReviews`, `PolicyLibrary`, `PolicyAudits`) are used identically in seeder, router, and tests; `compute_scores` returns the dict shape the router reads (`humanItemsRemain`, `overall`); the frontend `mapReview`/`mapVersion` translate the snake_case API payload to the camelCase types the views consume; `versionFor` now reads `checklistSnapshot` added to the `Review` type in the same task.

**Known follow-ups (out of Phase 1 scope):** the seeded demo reviews have `created_by_id = null` so they appear in the queue/library but not under a real user's "My reviews" (documented in spec §8); the optional `POLICY_REVIEW_SEED_DEMO_DATA` flag is omitted (demo data always seeds on first run).
