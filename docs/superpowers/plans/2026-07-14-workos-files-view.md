# WorkOS Files View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Activate the workstream **Files** tab: one read-only view listing every attachment (task + comment) across the workstream, with type filtering, search, sort, list/grid modes, and links back to each owning task.

**Architecture:** One new aggregate read endpoint (`GET /workstreams/{id}/attachments`, gated by `require_workstream_visible` — same posture as the workstream activity endpoint) joins attachments to tasks server-side. The frontend adds a `files` view (`FilesView` + `FileRow`/`FileCard`) fed by a `wsFiles` store; all filtering/sorting/grouping is client-side in pure helpers (`lib/files.ts`). Realtime = refetch on `workos:attachment.created/deleted` room events while the view is active.

**Tech Stack:** FastAPI + SQLAlchemy (async), Svelte 4 syntax components, Tailwind, shadcn-svelte (DropdownMenu, Input, Button), vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-07-14-workos-files-view-design.md`. Approved mockup: `docs/mockups/workos-files-v1.html` (list + grid anatomy, chips, recency groups).

## Global Constraints

- Read-only view: NO upload, NO delete, NO "More" menu in this view. Upload stays on the task drawer.
- Server caps the listing at 1000 rows; no pagination UI.
- Never start a Vite dev server for verification (user rule) — verify with `npm run check`, `npx vitest run`, and pytest only. Manual browser smoke happens after the build, driven by the user's own hot-reload server.
- NEVER use a haiku-model subagent to edit `.svelte` files (cp1252 corruption risk on this machine).
- Backend tests run with the venv python: `backend/.venv/Scripts/python.exe`.
- Frontend code style: tabs, single quotes, matching the existing WorkOS idioms — `export let` props, `$:` reactivity, `onclick` DOM attributes (like `ListView.svelte`), and the `{#snippet child({ props })}` pattern for shadcn DropdownMenu triggers (like `FilterBar.svelte`).
- Every task's commit runs on branch `osool` (current branch), normal commit messages, `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` trailer.

---

### Task 1: Backend — DAO join + `GET /workstreams/{id}/attachments` + tests

**Files:**
- Modify: `backend/open_webui/models/workos.py` (AttachmentsDao, after `list_for_task` ~line 1099)
- Modify: `backend/open_webui/routers/workos.py` (attachments section, after `list_attachments` ~line 1146)
- Create: `backend/open_webui/test/workos/test_router_workstream_attachments.py`
- Modify: `docs/superpowers/specs/2026-06-26-workos-access-control.md` (§4 Attachments table — standing rule: keep in sync)

**Interfaces:**
- Consumes: existing `WorkosAttachment`, `WorkosTask`, `AttachmentModel`, `require_workos`, `require_workstream_visible`, `get_async_db_context`.
- Produces: `Attachments.list_for_workstream(workstream_id, limit=1000, db=None) -> list[dict]` — each dict = `AttachmentModel` fields + `task_key: str`, `task_title: str`, `task_status: str`, ordered `created_at` DESC. Route `GET /api/v1/workos/workstreams/{workstream_id}/attachments` returning that list. Task 2's `WorkstreamFile` type mirrors this shape.

- [ ] **Step 1: Write the failing tests**

Create `backend/open_webui/test/workos/test_router_workstream_attachments.py`:

```python
import io

import pytest

import open_webui.routers.workos as wr
from open_webui.test.workos.test_router_teams import _client, U1, U2
from open_webui.test.workos.test_router_task import _stream
from open_webui.test.workos.test_router_attachments import _FakeStorage
from open_webui.test.workos.test_router_access_leaks import _restricted_task


async def _upload(c, task_id, name='f.txt', body=b'x', ctype='text/plain', comment_id=None):
    files = {'file': (name, io.BytesIO(body), ctype)}
    qs = f'?comment_id={comment_id}' if comment_id else ''
    r = await c.post(f'/api/v1/workos/tasks/{task_id}/attachments{qs}', files=files)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.asyncio
async def test_member_lists_files_across_tasks_with_task_join(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', _FakeStorage)
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        t1 = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'A'})).json()
        t2 = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'B'})).json()
        a1 = await _upload(c, t1['id'], name='one.txt')
        a2 = await _upload(c, t2['id'], name='two.pdf', ctype='application/pdf')
        # comment attachment on t1 must be included, with comment_id set
        com = (await c.post(f"/api/v1/workos/tasks/{t1['id']}/comments", json={'body': 'ctx'})).json()
        a3 = await _upload(c, t1['id'], name='three.png', ctype='image/png', comment_id=com['id'])

        r = await c.get(f"/api/v1/workos/workstreams/{s['id']}/attachments")
        assert r.status_code == 200, r.text
        rows = r.json()
        assert {x['id'] for x in rows} == {a1['id'], a2['id'], a3['id']}
        by_id = {x['id']: x for x in rows}
        assert by_id[a1['id']]['task_key'] == t1['key']
        assert by_id[a1['id']]['task_title'] == 'A'
        assert by_id[a1['id']]['task_status'] == t1['status']
        assert by_id[a2['id']]['task_key'] == t2['key']
        assert by_id[a3['id']]['comment_id'] == com['id']
        # newest first (ties allowed)
        times = [x['created_at'] for x in rows]
        assert times == sorted(times, reverse=True)


@pytest.mark.asyncio
async def test_empty_workstream_returns_empty_list(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, s = await _stream(c)
        r = await c.get(f"/api/v1/workos/workstreams/{s['id']}/attachments")
        assert r.status_code == 200 and r.json() == []


@pytest.mark.asyncio
async def test_non_member_gets_404(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', _FakeStorage)
    async with _client(monkeypatch, user=U1) as c:
        _, _, s = await _stream(c)
        stream_id = s['id']
    async with _client(monkeypatch, user=U2) as c2:
        r = await c2.get(f'/api/v1/workos/workstreams/{stream_id}/attachments')
        assert r.status_code == 404


@pytest.mark.asyncio
async def test_restricted_workspace_gates_team_member_without_ws_row(monkeypatch):
    monkeypatch.setattr(wr, 'Storage', _FakeStorage)
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s, t = await _restricted_task(c)
        await _upload(c, t['id'])
        # u2 joins the TEAM but not the restricted workspace
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c2:
        r = await c2.get(f"/api/v1/workos/workstreams/{s['id']}/attachments")
        assert r.status_code == 404
    async with _client(monkeypatch, user=U1) as c:
        await c.post(f"/api/v1/workos/workspaces/{ws['id']}/members", json={'user_id': 'u2', 'role': 'member'})
    async with _client(monkeypatch, user=U2) as c2:
        r = await c2.get(f"/api/v1/workos/workstreams/{s['id']}/attachments")
        assert r.status_code == 200
        assert len(r.json()) == 1


@pytest.mark.asyncio
async def test_unknown_workstream_404(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        r = await c.get('/api/v1/workos/workstreams/nope/attachments')
        assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
cd C:\Projects\open-webui\backend; .\.venv\Scripts\python.exe -m pytest open_webui\test\workos\test_router_workstream_attachments.py -v
```

Expected: FAIL — every test 404s (route doesn't exist), e.g. `assert 404 == 200`.

- [ ] **Step 3: Add the DAO method**

In `backend/open_webui/models/workos.py`, inside `class AttachmentsDao`, directly after `list_for_task` (which ends around line 1098), add — modeled byte-for-byte on `ActivityDao.list_for_workstream` (line 977):

```python
    async def list_for_workstream(
        self, workstream_id: str, limit: int = 1000, db: Optional[AsyncSession] = None
    ) -> list:
        """Newest attachments across the workstream's tasks, joined with task key/title/status."""
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosAttachment, WorkosTask.key, WorkosTask.title, WorkosTask.status)
                .join(WorkosTask, WorkosTask.id == WorkosAttachment.task_id)
                .where(WorkosTask.workstream_id == workstream_id)
                .order_by(WorkosAttachment.created_at.desc())
                .limit(limit)
            )
            out = []
            for row, task_key, task_title, task_status in res.all():
                item = AttachmentModel.model_validate(row).model_dump()
                item['task_key'] = task_key
                item['task_title'] = task_title
                item['task_status'] = task_status
                out.append(item)
            return out
```

(`select`, `WorkosTask`, `AttachmentModel` are already imported/defined in this module.)

- [ ] **Step 4: Add the route**

In `backend/open_webui/routers/workos.py`, directly after the `list_attachments` handler (ends ~line 1146), add:

```python
@router.get('/workstreams/{workstream_id}/attachments')
async def list_workstream_attachments(
    request: Request, workstream_id: str,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await require_workos(request, user, db)
    await require_workstream_visible(user, workstream_id, db)
    return await Attachments.list_for_workstream(workstream_id, db=db)
```

(All names already imported in the router.)

- [ ] **Step 5: Run the new tests — expect PASS**

```powershell
cd C:\Projects\open-webui\backend; .\.venv\Scripts\python.exe -m pytest open_webui\test\workos\test_router_workstream_attachments.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Run the whole workos backend suite (regression gate)**

```powershell
cd C:\Projects\open-webui\backend; .\.venv\Scripts\python.exe -m pytest open_webui\test\workos -q
```

Expected: all pass, no new failures.

- [ ] **Step 7: Sync the access-control reference (standing rule)**

In `docs/superpowers/specs/2026-06-26-workos-access-control.md`, §4 "Attachments" table, add this row after the `GET /tasks/{id}/attachments` row:

```markdown
| `GET /workstreams/{id}/attachments` | `require_workos` + `require_workstream_visible` — workstream-wide listing (rows joined w/ task key/title/status), read-only, cap 1000 | [workos.py](backend/open_webui/routers/workos.py) `list_workstream_attachments` |
```

- [ ] **Step 8: Commit**

```bash
git add backend/open_webui/models/workos.py backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_workstream_attachments.py docs/superpowers/specs/2026-06-26-workos-access-control.md
git commit -m "feat(workos): workstream-wide attachments endpoint

GET /workstreams/{id}/attachments joins attachments to tasks
(key/title/status), newest first, gated by require_workstream_visible —
same read posture as the workstream activity endpoint. Feeds the Files
tab.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Frontend lib — `WorkstreamFile` type, API client, pure file helpers + tests

**Files:**
- Modify: `src/lib/components/workos/lib/types.ts` (after the `Attachment` interface, ~line 112)
- Modify: `src/lib/components/workos/lib/api.ts` (Attachments section, ~line 159)
- Create: `src/lib/components/workos/lib/files.ts`
- Test: `src/lib/components/workos/lib/files.test.ts`

**Interfaces:**
- Consumes: `Attachment`, `TaskStatus` from `./types`; `formatDateShort` from `./format`; `request`/`BASE` pattern in `api.ts`.
- Produces (used by Tasks 3–5):
  - type `WorkstreamFile extends Attachment { task_key: string; task_title: string; task_status: TaskStatus }`
  - `api.listWorkstreamAttachments(token: string, workstreamId: string): Promise<WorkstreamFile[]>`
  - `files.ts`: `type FileGroup = 'img' | 'pdf' | 'doc' | 'sheet' | 'other'`; `interface FileKind { group: FileGroup; color: string; icon: string; ext: string }`; `fileKind(name: string, contentType?: string | null): FileKind`; `FILE_GROUPS: { id: FileGroup; label: string; dot: string }[]`; `formatBytes(n: number): string`; `type RecencyBucket = 'today' | 'week' | 'earlier'`; `recencyBucket(ts: number, now: number): RecencyBucket`; `formatFileDate(ts: number, now: number): string`; `interface FileBucket { id: RecencyBucket; label: string; rows: WorkstreamFile[] }`; `bucketFiles(files: WorkstreamFile[], now: number): FileBucket[]`; `type FileSort = 'newest' | 'name' | 'size'`; `sortFiles(files: WorkstreamFile[], sort: FileSort): WorkstreamFile[]`; `filterFiles(files: WorkstreamFile[], group: FileGroup | 'all', query: string): WorkstreamFile[]`; `groupCounts(files: WorkstreamFile[]): Record<FileGroup | 'all', number>`

- [ ] **Step 1: Write the failing tests**

Create `src/lib/components/workos/lib/files.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import {
	fileKind, formatBytes, recencyBucket, formatFileDate,
	bucketFiles, sortFiles, filterFiles, groupCounts
} from './files';
import type { WorkstreamFile } from './types';

const mk = (over: Partial<WorkstreamFile>): WorkstreamFile => ({
	id: 'a1', task_id: 't1', comment_id: null, storage_key: 'k', name: 'file.txt',
	size: 10, content_type: 'text/plain', created_by_id: 'u1', created_at: 0,
	task_key: 'OSL-1', task_title: 'T', task_status: 'todo', ...over
});

describe('fileKind', () => {
	it('classifies images by content type regardless of extension', () => {
		expect(fileKind('shot', 'image/png').group).toBe('img');
	});
	it('classifies by extension', () => {
		expect(fileKind('a.pdf', null).group).toBe('pdf');
		expect(fileKind('a.docx', null).group).toBe('doc');
		expect(fileKind('a.pptx', null).group).toBe('doc');
		expect(fileKind('a.xlsx', null).group).toBe('sheet');
		expect(fileKind('a.csv', null).group).toBe('sheet');
		expect(fileKind('a.zip', null).group).toBe('other');
	});
	it('uppercases the extension badge and falls back to FILE', () => {
		expect(fileKind('a.pdf', null).ext).toBe('PDF');
		expect(fileKind('noext', null).ext).toBe('FILE');
	});
	it('unknown extension → other', () => {
		expect(fileKind('a.xyz', null).group).toBe('other');
	});
});

describe('formatBytes', () => {
	it('formats B / KB / MB like the mockup', () => {
		expect(formatBytes(900)).toBe('900 B');
		expect(formatBytes(342 * 1024)).toBe('342 KB');
		expect(formatBytes(3.2 * 1024 * 1024)).toBe('3.2 MB');
	});
});

describe('recencyBucket', () => {
	// now = 2026-07-14T12:00 local
	const now = new Date(2026, 6, 14, 12, 0).getTime();
	it('same local day → today', () => {
		expect(recencyBucket(new Date(2026, 6, 14, 0, 5).getTime(), now)).toBe('today');
	});
	it('yesterday → week', () => {
		expect(recencyBucket(new Date(2026, 6, 13, 23, 0).getTime(), now)).toBe('week');
	});
	it('6 days ago → week, 8 days ago → earlier', () => {
		expect(recencyBucket(new Date(2026, 6, 8, 12, 0).getTime(), now)).toBe('week');
		expect(recencyBucket(new Date(2026, 6, 6, 12, 0).getTime(), now)).toBe('earlier');
	});
});

describe('formatFileDate', () => {
	const now = new Date(2026, 6, 14, 12, 0).getTime();
	it('today → time only; week → weekday + time; earlier → short date', () => {
		expect(formatFileDate(new Date(2026, 6, 14, 9, 30).getTime(), now)).toMatch(/9:30/);
		expect(formatFileDate(new Date(2026, 6, 13, 9, 30).getTime(), now)).toMatch(/^Mon/);
		expect(formatFileDate(new Date(2026, 5, 1).getTime(), now)).toBe('Jun 1');
	});
});

describe('bucketFiles / sortFiles / filterFiles / groupCounts', () => {
	const now = new Date(2026, 6, 14, 12, 0).getTime();
	const files = [
		mk({ id: 'a', name: 'zeta.pdf', size: 5, created_at: new Date(2026, 6, 14, 9, 0).getTime() }),
		mk({ id: 'b', name: 'alpha.png', content_type: 'image/png', size: 50, created_at: new Date(2026, 6, 12).getTime() }),
		mk({ id: 'c', name: 'mid.xlsx', size: 20, created_at: new Date(2026, 5, 1).getTime() })
	];
	it('buckets only non-empty groups in today/week/earlier order', () => {
		const buckets = bucketFiles(files, now);
		expect(buckets.map((b) => b.id)).toEqual(['today', 'week', 'earlier']);
		expect(buckets[0].rows.map((r) => r.id)).toEqual(['a']);
		expect(bucketFiles([files[0]], now).map((b) => b.id)).toEqual(['today']);
	});
	it('sorts newest / name / size without mutating input', () => {
		expect(sortFiles(files, 'newest').map((f) => f.id)).toEqual(['a', 'b', 'c']);
		expect(sortFiles(files, 'name').map((f) => f.id)).toEqual(['b', 'c', 'a']);
		expect(sortFiles(files, 'size').map((f) => f.id)).toEqual(['b', 'c', 'a']);
		expect(files.map((f) => f.id)).toEqual(['a', 'b', 'c']);
	});
	it('filters by group and by name substring (case-insensitive)', () => {
		expect(filterFiles(files, 'img', '').map((f) => f.id)).toEqual(['b']);
		expect(filterFiles(files, 'all', 'ZETA').map((f) => f.id)).toEqual(['a']);
	});
	it('counts per group plus all', () => {
		const c = groupCounts(files);
		expect(c.all).toBe(3);
		expect(c.img).toBe(1);
		expect(c.pdf).toBe(1);
		expect(c.sheet).toBe(1);
		expect(c.doc).toBe(0);
	});
});
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
npx vitest run src/lib/components/workos/lib/files.test.ts
```

Expected: FAIL — `Cannot find module './files'` (or equivalent resolve error).

- [ ] **Step 3: Add the type + API client**

In `src/lib/components/workos/lib/types.ts`, directly after the `Attachment` interface (line 112), add:

```ts
/** Attachment row from the workstream-wide listing, joined with its task. */
export interface WorkstreamFile extends Attachment {
	task_key: string;
	task_title: string;
	task_status: TaskStatus;
}
```

In `src/lib/components/workos/lib/api.ts`:
1. Add `WorkstreamFile` to the type import list at the top (line 2–6).
2. In the `// Attachments` section, after `listAttachments` (line 156), add:

```ts
export const listWorkstreamAttachments = (token: string, workstreamId: string) =>
	request<WorkstreamFile[]>(token, `/workstreams/${workstreamId}/attachments`);
```

- [ ] **Step 4: Write `files.ts`**

Create `src/lib/components/workos/lib/files.ts`:

```ts
import type { WorkstreamFile } from './types';
import { formatDateShort } from './format';

// ── type classification ────────────────────────────────────────────────────
// Groups + colors mirror docs/mockups/workos-files-v1.html (approved v1).

export type FileGroup = 'img' | 'pdf' | 'doc' | 'sheet' | 'other';

export interface FileKind {
	group: FileGroup;
	color: string;
	icon: string; // Icon.svelte name for the tile glyph (unused for images)
	ext: string; // uppercase badge, e.g. 'PDF'
}

const COLOR: Record<string, string> = {
	img: '#00a5ba', pdf: '#dc2626', doc: '#2563eb', slides: '#ea580c',
	sheet: '#769a4a', zip: '#ca8a04', video: '#7c3aed', other: '#6b7280'
};

/** Chip definitions for the toolbar (All is added by the view). */
export const FILE_GROUPS: { id: FileGroup; label: string; dot: string }[] = [
	{ id: 'img', label: 'Images', dot: COLOR.img },
	{ id: 'pdf', label: 'PDFs', dot: COLOR.pdf },
	{ id: 'doc', label: 'Docs', dot: COLOR.doc },
	{ id: 'sheet', label: 'Sheets', dot: COLOR.sheet },
	{ id: 'other', label: 'Other', dot: COLOR.zip }
];

/** ext → [group, color key, icon] — pptx keeps its slide color inside the doc group. */
const EXT: Record<string, [FileGroup, string, string]> = {
	jpg: ['img', 'img', 'image'], jpeg: ['img', 'img', 'image'], png: ['img', 'img', 'image'],
	gif: ['img', 'img', 'image'], webp: ['img', 'img', 'image'], svg: ['img', 'img', 'image'],
	pdf: ['pdf', 'pdf', 'file-text'],
	doc: ['doc', 'doc', 'file-text'], docx: ['doc', 'doc', 'file-text'],
	txt: ['doc', 'doc', 'file-text'], md: ['doc', 'doc', 'file-text'], json: ['doc', 'doc', 'file-text'],
	ppt: ['doc', 'slides', 'presentation'], pptx: ['doc', 'slides', 'presentation'],
	xls: ['sheet', 'sheet', 'file-spreadsheet'], xlsx: ['sheet', 'sheet', 'file-spreadsheet'],
	csv: ['sheet', 'sheet', 'file-spreadsheet'],
	zip: ['other', 'zip', 'archive'],
	mp4: ['other', 'video', 'play-circle'], mov: ['other', 'video', 'play-circle'],
	webm: ['other', 'video', 'play-circle']
};

export function fileKind(name: string, contentType?: string | null): FileKind {
	const dot = name.lastIndexOf('.');
	const ext = dot > 0 ? name.slice(dot + 1).toLowerCase() : '';
	if (contentType?.startsWith('image/')) {
		return { group: 'img', color: COLOR.img, icon: 'image', ext: ext ? ext.toUpperCase() : 'IMG' };
	}
	const hit = EXT[ext];
	if (hit) return { group: hit[0], color: COLOR[hit[1]], icon: hit[2], ext: ext.toUpperCase() };
	return { group: 'other', color: COLOR.other, icon: 'file', ext: ext ? ext.toUpperCase() : 'FILE' };
}

/** True when the browser can render the attachment as an <img> thumbnail. */
export function isImage(f: WorkstreamFile): boolean {
	return !!f.content_type && f.content_type.startsWith('image/');
}

// ── formatting ─────────────────────────────────────────────────────────────

/** '900 B' / '342 KB' / '3.2 MB' — mirrors the mockup's size column. */
export function formatBytes(n: number): string {
	if (n >= 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`;
	if (n >= 1024) return `${Math.round(n / 1024)} KB`;
	return `${n} B`;
}

// ── recency grouping ───────────────────────────────────────────────────────

export type RecencyBucket = 'today' | 'week' | 'earlier';

export function recencyBucket(ts: number, now: number): RecencyBucket {
	const d = new Date(ts);
	const n = new Date(now);
	if (
		d.getFullYear() === n.getFullYear() && d.getMonth() === n.getMonth() && d.getDate() === n.getDate()
	) return 'today';
	if (now - ts < 7 * 86_400_000) return 'week';
	return 'earlier';
}

/** Today → '09:30 AM'; this week → 'Mon 09:30 AM'; earlier → 'Jun 1'. */
export function formatFileDate(ts: number, now: number): string {
	const bucket = recencyBucket(ts, now);
	const d = new Date(ts);
	const time = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
	if (bucket === 'today') return time;
	if (bucket === 'week') return `${d.toLocaleDateString('en-US', { weekday: 'short' })} ${time}`;
	return formatDateShort(ts);
}

export interface FileBucket {
	id: RecencyBucket;
	label: string;
	rows: WorkstreamFile[];
}

const BUCKET_LABEL: Record<RecencyBucket, string> = {
	today: 'Today', week: 'This week', earlier: 'Earlier'
};

/** Non-empty buckets in today → week → earlier order, preserving input order. */
export function bucketFiles(files: WorkstreamFile[], now: number): FileBucket[] {
	const order: RecencyBucket[] = ['today', 'week', 'earlier'];
	return order
		.map((id) => ({ id, label: BUCKET_LABEL[id], rows: files.filter((f) => recencyBucket(f.created_at, now) === id) }))
		.filter((b) => b.rows.length > 0);
}

// ── filter / sort / counts ─────────────────────────────────────────────────

export type FileSort = 'newest' | 'name' | 'size';

export const FILE_SORT_LABEL: Record<FileSort, string> = {
	newest: 'Newest', name: 'Name', size: 'Size'
};

export function sortFiles(files: WorkstreamFile[], sort: FileSort): WorkstreamFile[] {
	const out = [...files];
	if (sort === 'name') out.sort((a, b) => a.name.localeCompare(b.name));
	else if (sort === 'size') out.sort((a, b) => b.size - a.size);
	else out.sort((a, b) => b.created_at - a.created_at);
	return out;
}

export function filterFiles(files: WorkstreamFile[], group: FileGroup | 'all', query: string): WorkstreamFile[] {
	const q = query.trim().toLowerCase();
	return files.filter(
		(f) =>
			(group === 'all' || fileKind(f.name, f.content_type).group === group) &&
			(!q || f.name.toLowerCase().includes(q))
	);
}

export function groupCounts(files: WorkstreamFile[]): Record<FileGroup | 'all', number> {
	const out: Record<FileGroup | 'all', number> = { all: files.length, img: 0, pdf: 0, doc: 0, sheet: 0, other: 0 };
	for (const f of files) out[fileKind(f.name, f.content_type).group] += 1;
	return out;
}
```

- [ ] **Step 5: Run the tests — expect PASS**

```powershell
npx vitest run src/lib/components/workos/lib/files.test.ts
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/lib/types.ts src/lib/components/workos/lib/api.ts src/lib/components/workos/lib/files.ts src/lib/components/workos/lib/files.test.ts
git commit -m "feat(workos): files-view lib — WorkstreamFile type, API client, pure helpers

Type classification (mockup groups/colors), byte/date formatting,
recency bucketing, filter/sort/counts. All pure + vitest-covered.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Store — `files` view key, `wsFiles` state, loader, realtime refetch

**Files:**
- Modify: `src/lib/components/workos/lib/store.ts`
- Test: `src/lib/components/workos/lib/store.test.ts` (extend)

**Interfaces:**
- Consumes: `api.listWorkstreamAttachments` (Task 2), existing `view`, `currentWorkstreamId`, `token()`, `connectRealtime` COLLAB handler.
- Produces (used by Task 5):
  - `ViewKey` union includes `'files'`
  - `interface WsFilesState { items: WorkstreamFile[]; loaded: boolean; error: boolean }`
  - `wsFiles: Writable<WsFilesState>`
  - `loadWorkstreamFiles(id: string): Promise<void>`
  - `applyFilesEvent(event: string, payload: any): void` — wired into the socket COLLAB handler

- [ ] **Step 1: Write the failing tests**

In `src/lib/components/workos/lib/store.test.ts`:

1. Add to the `vi.mock('./api', …)` factory (after `getWorkstreamActivity`, line 28):

```ts
	listWorkstreamAttachments: vi.fn(async () => []),
```

2. Append a new describe block at the end of the file:

```ts
describe('files view realtime', () => {
	it('attachment events refetch while the Files view is open on that workstream', async () => {
		const api = await import('./api');
		const { view, applyFilesEvent } = await import('./store');
		view.set('files');
		currentWorkstreamId.set('w1');
		(api.listWorkstreamAttachments as any).mockClear();
		applyFilesEvent('workos:attachment.created', { id: 'a1', workstream_id: 'w1' });
		applyFilesEvent('workos:attachment.deleted', { id: 'a1', workstream_id: 'w1' });
		expect(api.listWorkstreamAttachments).toHaveBeenCalledTimes(2);
	});
	it('ignores other views, other workstreams, and other events', async () => {
		const api = await import('./api');
		const { view, applyFilesEvent } = await import('./store');
		(api.listWorkstreamAttachments as any).mockClear();
		view.set('board');
		currentWorkstreamId.set('w1');
		applyFilesEvent('workos:attachment.created', { id: 'a1', workstream_id: 'w1' });
		view.set('files');
		applyFilesEvent('workos:attachment.created', { id: 'a1', workstream_id: 'other' });
		applyFilesEvent('workos:comment.created', { id: 'c1', workstream_id: 'w1' });
		expect(api.listWorkstreamAttachments).not.toHaveBeenCalled();
	});
	it('loadWorkstreamFiles marks loaded and keeps items on success', async () => {
		const api = await import('./api');
		const { wsFiles, loadWorkstreamFiles } = await import('./store');
		(api.listWorkstreamAttachments as any).mockResolvedValueOnce([
			{ id: 'f1', task_id: 't1', name: 'a.txt', size: 1, created_at: 1, storage_key: 'k',
			  task_key: 'OSL-1', task_title: 'T', task_status: 'todo' }
		]);
		currentWorkstreamId.set('w1');
		await loadWorkstreamFiles('w1');
		expect(get(wsFiles)).toMatchObject({ loaded: true, error: false });
		expect(get(wsFiles).items.map((f) => f.id)).toEqual(['f1']);
	});
	it('loadWorkstreamFiles discards a stale response after workstream switch', async () => {
		const api = await import('./api');
		const { wsFiles, loadWorkstreamFiles } = await import('./store');
		(api.listWorkstreamAttachments as any).mockImplementationOnce(async () => {
			currentWorkstreamId.set('w2'); // user moved on mid-flight
			return [{ id: 'stale' }];
		});
		currentWorkstreamId.set('w1');
		await loadWorkstreamFiles('w1');
		expect(get(wsFiles).items).toEqual([]);
	});
});
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
npx vitest run src/lib/components/workos/lib/store.test.ts
```

Expected: FAIL — `applyFilesEvent` / `wsFiles` / `loadWorkstreamFiles` are not exported.

- [ ] **Step 3: Implement the store changes**

In `src/lib/components/workos/lib/store.ts`:

1. Line 20 — extend the union:

```ts
export type ViewKey = 'board' | 'list' | 'admin' | 'inbox' | 'mywork' | 'calendar' | 'overview' | 'timeline' | 'files';
```

2. Add `WorkstreamFile` to the type import from `./types` (line 8–14).

3. After the `wsActivity` block (line 105), add:

```ts
export interface WsFilesState {
	items: WorkstreamFile[];
	loaded: boolean;
	error: boolean;
}
export const wsFiles: Writable<WsFilesState> = writable({ items: [], loaded: false, error: false });
```

4. After `loadWorkstreamActivity` (ends line 397), add:

```ts
export async function loadWorkstreamFiles(id: string): Promise<void> {
	wsFiles.set({ items: [], loaded: false, error: false });
	try {
		const items = await api.listWorkstreamAttachments(token(), id);
		if (get(currentWorkstreamId) !== id) return; // user moved on
		wsFiles.set({ items, loaded: true, error: false });
	} catch {
		if (get(currentWorkstreamId) !== id) return; // user moved on
		wsFiles.set({ items: [], loaded: true, error: true });
	}
}

/** While the Files view is open, an attachment room event for the current
 * workstream refetches the listing (rows need the server-side task join). */
export function applyFilesEvent(event: string, payload: any): void {
	if (event !== 'workos:attachment.created' && event !== 'workos:attachment.deleted') return;
	if (get(view) !== 'files') return;
	const ws = get(currentWorkstreamId);
	if (!ws || !payload || payload.workstream_id !== ws) return;
	void loadWorkstreamFiles(ws);
}
```

5. In `connectRealtime`, extend the COLLAB handler (line 612–618) to also fold files events:

```ts
	for (const ev of COLLAB_EVENTS) {
		handlers[ev] = (payload: any) => {
			applyCollabEvent(ev, payload);
			if (ev === 'workos:activity.created') applyOverviewActivityEvent(payload);
			applyFilesEvent(ev, payload);
		};
		s.on(ev, handlers[ev]);
	}
```

- [ ] **Step 4: Run the store tests — expect PASS**

```powershell
npx vitest run src/lib/components/workos/lib/store.test.ts
```

Expected: all pass (old + new).

- [ ] **Step 5: Run the full frontend unit suite (regression gate)**

```powershell
npx vitest run src/lib/components/workos
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/lib/store.ts src/lib/components/workos/lib/store.test.ts
git commit -m "feat(workos): files view store — wsFiles state, loader, realtime refetch

ViewKey gains 'files'; attachment.created/deleted room events refetch
the workstream listing while the view is active (rows need the
server-side task join, so a fold-in isn't enough).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: UI atoms — Icon glyphs + `FileRow` + `FileCard`

**Files:**
- Modify: `src/lib/components/workos/ui/Icon.svelte` (LUCIDE map)
- Create: `src/lib/components/workos/views/files/FileRow.svelte`
- Create: `src/lib/components/workos/views/files/FileCard.svelte`

**Interfaces:**
- Consumes: `WorkstreamFile` (Task 2 types), `fileKind`/`isImage`/`formatBytes`/`formatFileDate` (Task 2 files.ts), `attachmentUrl` (api.ts), `openTask`/`displayName`/`initials` (store), `avatarColors` (`../../lib/avatar`), `StatusDot` + `statusShape`/`STATUS_COLOR`/`tint` (existing), `Icon`.
- Produces: `FileRow` with props `{ file: WorkstreamFile; now: number }`; `FileCard` with props `{ file: WorkstreamFile; now: number }`. Both are display-only; the grid column template in `FileRow` must match the header template in Task 5's `FilesView` exactly.

- [ ] **Step 1: Add the missing Lucide glyphs**

In `src/lib/components/workos/ui/Icon.svelte`, add to the `LUCIDE` record (after the `archive` entry, line 55):

```ts
		'file-text': '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 12h4"/><path d="M10 16h4"/>',
		'file-spreadsheet': '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M8 13h8"/><path d="M8 17h8"/><path d="M12 13v4"/>',
		presentation: '<path d="M2 3h20"/><path d="M21 3v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V3"/><path d="m9 16-2 5"/><path d="m15 16 2 5"/>',
		'play-circle': '<circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/>',
		image: '<rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.09-3.09a2 2 0 0 0-2.82 0L6 21"/>',
		'arrow-up-right': '<path d="M7 7h10v10"/><path d="M7 17 17 7"/>',
		'layout-grid': '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>',
```

- [ ] **Step 2: Create `FileRow.svelte`**

Create `src/lib/components/workos/views/files/FileRow.svelte`:

```svelte
<script lang="ts">
	// One list row of the Files view. Columns must stay in lockstep with the
	// header template in FilesView.svelte.
	import Icon from '../../ui/Icon.svelte';
	import StatusDot from '../../ui/StatusDot.svelte';
	import { attachmentUrl } from '../../lib/api';
	import { fileKind, isImage, formatBytes, formatFileDate } from '../../lib/files';
	import { STATUS_COLOR, statusShape, tint } from '../../lib/colors';
	import { openTask, displayName, initials } from '../../lib/store';
	import { avatarColors } from '../../lib/avatar';
	import type { WorkstreamFile } from '../../lib/types';

	export let file: WorkstreamFile;
	export let now: number;

	$: kind = fileKind(file.name, file.content_type);
	$: av = avatarColors(file.created_by_id ?? '');
</script>

<div
	class="group grid items-center gap-3 px-3 py-2 border-t border-gray-100 dark:border-gray-900 hover:bg-gray-50 dark:hover:bg-gray-900/50 grid-cols-[minmax(0,1fr)_auto_auto] md:grid-cols-[minmax(0,1fr)_180px_90px_72px_84px] xl:grid-cols-[minmax(0,1fr)_220px_150px_90px_72px_84px]"
>
	<!-- Name: type tile / image thumb + filename + sub line -->
	<span class="flex items-center gap-3 min-w-0">
		{#if isImage(file)}
			<img
				src={attachmentUrl(file.id)}
				alt={file.name}
				loading="lazy"
				class="size-9 rounded-lg object-cover flex-none ring-1 ring-black/5 dark:ring-white/10"
			/>
		{:else}
			<span
				class="size-9 rounded-lg flex-none grid place-items-center"
				style="background:{tint(kind.color, 12)}; color:{kind.color}"
			>
				<Icon name={kind.icon} size={17} />
			</span>
		{/if}
		<span class="min-w-0">
			<a
				class="block text-sm font-medium truncate hover:text-primary"
				href={attachmentUrl(file.id)}
				target="_blank"
				rel="noreferrer"
				title={file.name}
			>{file.name}</a>
			<span class="flex items-center gap-1.5 text-[11px] text-gray-400">
				<span class="inline-flex items-center gap-1 md:hidden font-semibold tabular-nums">{file.task_key}</span>
				{#if file.comment_id}
					<span class="inline-flex items-center gap-1 rounded-full border border-gray-200 dark:border-gray-800 px-1.5 text-[10px] font-semibold text-gray-400">
						<Icon name="message-square" size={9} /> via comment
					</span>
				{/if}
			</span>
		</span>
	</span>

	<!-- Task chip (≥md) -->
	<button
		class="hidden md:inline-flex items-center gap-1.5 min-w-0 text-xs text-gray-500 dark:text-gray-400 hover:text-primary text-left"
		onclick={() => openTask(file.task_id)}
		title="{file.task_key} — {file.task_title}"
	>
		<StatusDot shape={statusShape(file.task_status)} color={STATUS_COLOR[file.task_status]} size={12} />
		<span class="font-semibold tabular-nums text-[11px] text-gray-400 flex-none">{file.task_key}</span>
		<span class="truncate">{file.task_title}</span>
	</button>

	<!-- Uploader (≥xl) -->
	<span class="hidden xl:flex items-center gap-2 min-w-0 text-xs text-gray-500 dark:text-gray-400">
		<span
			class="size-[22px] rounded-full flex-none grid place-items-center text-[9px] font-bold"
			style="background:{av.background};color:{av.foreground}"
		>{initials(file.created_by_id)}</span>
		<span class="truncate">{displayName(file.created_by_id)}</span>
	</span>

	<!-- Added (≥md) -->
	<span class="hidden md:block text-xs text-gray-400 tabular-nums whitespace-nowrap">{formatFileDate(file.created_at, now)}</span>

	<!-- Size -->
	<span class="text-xs text-gray-400 tabular-nums whitespace-nowrap">{formatBytes(file.size)}</span>

	<!-- Actions: hover-reveal on desktop, always visible on touch widths -->
	<span class="flex items-center justify-end gap-0.5 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
		<a
			class="grid place-items-center size-7 rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-200/60 dark:hover:text-gray-200 dark:hover:bg-gray-800"
			href={attachmentUrl(file.id)}
			target="_blank"
			rel="noreferrer"
			title="Download"
		><Icon name="download" size={15} /></a>
		<button
			class="grid place-items-center size-7 rounded-md text-gray-400 hover:text-gray-700 hover:bg-gray-200/60 dark:hover:text-gray-200 dark:hover:bg-gray-800"
			onclick={() => openTask(file.task_id)}
			title="Open task"
		><Icon name="arrow-up-right" size={15} /></button>
	</span>
</div>
```

- [ ] **Step 3: Create `FileCard.svelte`**

Create `src/lib/components/workos/views/files/FileCard.svelte`:

```svelte
<script lang="ts">
	// Grid-mode gallery card: big preview (image thumb or tinted type glyph),
	// extension pill, hover actions, name + task-key/size meta.
	import Icon from '../../ui/Icon.svelte';
	import { attachmentUrl } from '../../lib/api';
	import { fileKind, isImage, formatBytes } from '../../lib/files';
	import { tint } from '../../lib/colors';
	import { openTask } from '../../lib/store';
	import type { WorkstreamFile } from '../../lib/types';

	export let file: WorkstreamFile;

	$: kind = fileKind(file.name, file.content_type);
</script>

<div
	class="group relative overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 transition-shadow hover:shadow-md hover:-translate-y-px"
>
	<!-- Preview -->
	<div class="relative h-28 grid place-items-center" style={isImage(file) ? '' : `background:${tint(kind.color, 9)}`}>
		{#if isImage(file)}
			<img src={attachmentUrl(file.id)} alt={file.name} loading="lazy" class="absolute inset-0 h-full w-full object-cover" />
		{:else}
			<span style="color:{kind.color}"><Icon name={kind.icon} size={30} /></span>
		{/if}
		<span
			class="absolute left-2 bottom-2 rounded-full px-2 py-0.5 text-[9.5px] font-bold tracking-wide text-white"
			style="background:{isImage(file) ? 'rgb(0 0 0 / 0.45)' : kind.color}"
		>{kind.ext}</span>
		<!-- Hover actions -->
		<span class="absolute right-2 top-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
			<a
				class="grid place-items-center size-7 rounded-md bg-white/90 dark:bg-gray-900/90 shadow-sm backdrop-blur text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
				href={attachmentUrl(file.id)}
				target="_blank"
				rel="noreferrer"
				title="Download"
			><Icon name="download" size={14} /></a>
			<button
				class="grid place-items-center size-7 rounded-md bg-white/90 dark:bg-gray-900/90 shadow-sm backdrop-blur text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
				onclick={() => openTask(file.task_id)}
				title="Open task"
			><Icon name="arrow-up-right" size={14} /></button>
		</span>
	</div>

	<!-- Body -->
	<div class="px-3 py-2.5">
		<a
			class="block text-xs font-medium truncate hover:text-primary"
			href={attachmentUrl(file.id)}
			target="_blank"
			rel="noreferrer"
			title={file.name}
		>{file.name}</a>
		<div class="mt-1 flex items-center gap-1.5 text-[11px] text-gray-400 min-w-0">
			<button class="font-semibold tabular-nums hover:text-primary flex-none" onclick={() => openTask(file.task_id)} title={file.task_title}>{file.task_key}</button>
			<span class="flex-1"></span>
			{#if file.comment_id}<Icon name="message-square" size={10} />{/if}
			<span class="tabular-nums">{formatBytes(file.size)}</span>
		</div>
	</div>
</div>
```

- [ ] **Step 4: Type-check gate**

```powershell
npm run check
```

Expected: no NEW errors introduced by these files (compare against the pre-change baseline; the repo may carry pre-existing warnings).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/ui/Icon.svelte src/lib/components/workos/views/files/FileRow.svelte src/lib/components/workos/views/files/FileCard.svelte
git commit -m "feat(workos): files view atoms — FileRow, FileCard, new icon glyphs

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: `FilesView` + activate the Files tab

**Files:**
- Create: `src/lib/components/workos/views/FilesView.svelte`
- Modify: `src/lib/components/workos/chrome/Topbar.svelte` (TABS entry, line 19; `selectTab` cast, line 22)
- Modify: `src/lib/components/workos/WorkOSApp.svelte` (import + Topbar condition line 51 + view branch)

**Interfaces:**
- Consumes: `wsFiles`, `loadWorkstreamFiles`, `currentWorkstreamId` (Task 3), all `lib/files.ts` helpers (Task 2), `FileRow`/`FileCard` (Task 4), `EmptyState`, shadcn `Input`/`DropdownMenu`/`Button`.
- Produces: the live `files` view. Grid column template in the list header MUST equal `FileRow`'s row template.

- [ ] **Step 1: Create `FilesView.svelte`**

Create `src/lib/components/workos/views/FilesView.svelte`:

```svelte
<script lang="ts">
	// Files tab — every attachment across the workstream (task + comment uploads),
	// read-only: download + open-task. Upload lives on the task drawer.
	// Anatomy per docs/mockups/workos-files-v1.html (approved v1).
	import Icon from '../ui/Icon.svelte';
	import EmptyState from '../ui/EmptyState.svelte';
	import FileRow from './files/FileRow.svelte';
	import FileCard from './files/FileCard.svelte';
	import { Input } from '$lib/components/ui/input';
	import { Button } from '$lib/components/ui/button';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { wsFiles, loadWorkstreamFiles, currentWorkstreamId } from '../lib/store';
	import {
		FILE_GROUPS, FILE_SORT_LABEL, bucketFiles, filterFiles, formatBytes, groupCounts, sortFiles,
		type FileGroup, type FileSort
	} from '../lib/files';

	let ftype: FileGroup | 'all' = 'all';
	let query = '';
	let sort: FileSort = 'newest';
	let mode: 'list' | 'grid' = 'list';

	// Fetch on mount + on workstream switch (view is only mounted while active).
	$: if ($currentWorkstreamId) void loadWorkstreamFiles($currentWorkstreamId);

	const now = Date.now();

	$: counts = groupCounts($wsFiles.items);
	$: visible = sortFiles(filterFiles($wsFiles.items, ftype, query), sort);
	// Recency sections only make sense in recency order; Name/Size sorts render flat.
	$: buckets = sort === 'newest'
		? bucketFiles(visible, now)
		: visible.length ? [{ id: 'earlier' as const, label: 'All files', rows: visible }] : [];
	$: totalSize = $wsFiles.items.reduce((n, f) => n + f.size, 0);
	$: filtered = visible.length !== $wsFiles.items.length;

	const chipBase =
		'inline-flex items-center gap-1.5 h-8 px-3 rounded-full border text-xs font-medium transition-colors';
	const chipOff =
		'border-gray-200 dark:border-gray-800 text-gray-500 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-900';
	const chipOn = 'border-primary/45 bg-primary/10 text-primary font-semibold';

	// Header must match FileRow's grid template exactly.
	const cols =
		'grid-cols-[minmax(0,1fr)_auto_auto] md:grid-cols-[minmax(0,1fr)_180px_90px_72px_84px] xl:grid-cols-[minmax(0,1fr)_220px_150px_90px_72px_84px]';
</script>

<div class="h-full flex flex-col min-h-0">
	<!-- Toolbar: type chips · meta · sort · search · list/grid toggle -->
	<div class="flex-none flex flex-wrap items-center gap-2 px-4 py-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
		<button class="{chipBase} {ftype === 'all' ? chipOn : chipOff}" onclick={() => (ftype = 'all')}>
			All <span class="tabular-nums opacity-60">{counts.all}</span>
		</button>
		{#each FILE_GROUPS as g (g.id)}
			<button class="{chipBase} {ftype === g.id ? chipOn : chipOff}" onclick={() => (ftype = g.id)}>
				<span class="size-[7px] rounded-full" style="background:{g.dot}"></span>
				{g.label} <span class="tabular-nums opacity-60">{counts[g.id]}</span>
			</button>
		{/each}

		<span class="text-xs text-gray-400 px-1 whitespace-nowrap">
			{#if $wsFiles.loaded && !$wsFiles.error}
				{filtered ? `${visible.length} of ${counts.all} files` : `${counts.all} files · ${formatBytes(totalSize)}`}
			{/if}
		</span>

		<span class="flex-1"></span>

		<DropdownMenu.Root>
			<DropdownMenu.Trigger>
				{#snippet child({ props }: { props: Record<string, any> })}
					<Button {...props} variant="outline" size="sm">
						<span class="text-gray-400">Sort</span><span class="font-medium">{FILE_SORT_LABEL[sort]}</span>
						<Icon name="chevron-down" size={13} />
					</Button>
				{/snippet}
			</DropdownMenu.Trigger>
			<DropdownMenu.Content align="end" class="min-w-[9rem]">
				{#each Object.entries(FILE_SORT_LABEL) as [key, label] (key)}
					<DropdownMenu.CheckboxItem checked={sort === key} onCheckedChange={() => (sort = key as FileSort)}>
						{label}
					</DropdownMenu.CheckboxItem>
				{/each}
			</DropdownMenu.Content>
		</DropdownMenu.Root>

		<div class="relative">
			<Input class="h-8 pl-8 w-40 md:w-52" placeholder="Search files…" bind:value={query} />
			<span class="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"><Icon name="search" size={14} /></span>
		</div>

		<span class="inline-flex rounded-lg border border-gray-200 dark:border-gray-800 overflow-hidden">
			<button
				class="grid place-items-center w-9 h-8 {mode === 'list' ? 'bg-primary/10 text-primary' : 'text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-900'}"
				title="List"
				onclick={() => (mode = 'list')}
			><Icon name="list" size={15} /></button>
			<button
				class="grid place-items-center w-9 h-8 {mode === 'grid' ? 'bg-primary/10 text-primary' : 'text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-900'}"
				title="Grid"
				onclick={() => (mode = 'grid')}
			><Icon name="layout-grid" size={15} /></button>
		</span>
	</div>

	<!-- Content -->
	<div class="flex-1 overflow-auto p-4 bg-white dark:bg-gray-900">
		{#if !$wsFiles.loaded}
			<div class="h-full flex items-center justify-center text-sm text-gray-400">Loading…</div>
		{:else if $wsFiles.error}
			<EmptyState
				icon="alert-triangle"
				title="Couldn't load files"
				sub="Something went wrong fetching this workstream's files."
				ctaLabel="Retry"
				onCta={() => $currentWorkstreamId && loadWorkstreamFiles($currentWorkstreamId)}
			/>
		{:else if !$wsFiles.items.length}
			<EmptyState
				icon="paperclip"
				title="No files yet"
				sub="Files attached to tasks in this workstream will show up here."
			/>
		{:else if !visible.length}
			<EmptyState icon="search" title="No files match" sub="Try a different type or clear the search." />
		{:else if mode === 'list'}
			<div class="space-y-3">
				{#each buckets as b (b.id)}
					<section class="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-hidden">
						<div class="flex items-center gap-2 px-3 py-2.5">
							<span class="text-sm font-semibold">{b.label}</span>
							<span class="text-xs text-gray-400 tabular-nums">{b.rows.length}</span>
						</div>
						<!-- Column header (desktop) — template mirrors FileRow -->
						<div class="hidden md:grid items-center gap-3 px-3 py-1.5 border-t border-gray-100 dark:border-gray-900 text-xs text-gray-400 {cols}">
							<span style="padding-left: 48px;">Name</span>
							<span>Task</span>
							<span class="hidden xl:block">Uploaded by</span>
							<span>Added</span>
							<span>Size</span>
							<span></span>
						</div>
						{#each b.rows as f (f.id)}
							<FileRow file={f} {now} />
						{/each}
					</section>
				{/each}
			</div>
		{:else}
			{#each buckets as b (b.id)}
				<div class="flex items-baseline gap-2 mb-2.5 mt-1 first:mt-0">
					<span class="text-sm font-semibold">{b.label}</span>
					<span class="text-xs text-gray-400 tabular-nums">{b.rows.length}</span>
				</div>
				<div class="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-3 mb-5">
					{#each b.rows as f (f.id)}
						<FileCard file={f} />
					{/each}
				</div>
			{/each}
		{/if}
	</div>
</div>
```

Note: the desktop column header hides `Uploaded by` below `xl` (matching `FileRow`'s `hidden xl:flex`), but the 5-column `md` template still reserves its slot — the header/row templates collapse together because both use the same `cols` classes; the `md` template simply has 5 tracks (no uploader) while `xl` has 6. Keep the two template strings identical between `FilesView` and `FileRow` — that is the alignment contract.

- [ ] **Step 2: Activate the tab in `Topbar.svelte`**

Line 19 — flip the stub:

```ts
		{ key: 'files', label: 'Files', icon: 'paperclip', live: true }
```

Line 21–23 — widen the cast:

```ts
	function selectTab(t: (typeof TABS)[number]) {
		if (t.live) view.set(t.key as 'board' | 'list' | 'calendar' | 'overview' | 'timeline' | 'files');
	}
```

- [ ] **Step 3: Register the view in `WorkOSApp.svelte`**

1. Add the import after `TimelineView` (line 12):

```ts
	import FilesView from './views/FilesView.svelte';
```

2. Extend the Topbar condition (line 51):

```svelte
			{#if $view === 'board' || $view === 'list' || $view === 'calendar' || $view === 'overview' || $view === 'timeline' || $view === 'files'}
```

3. Add the branch after the `timeline` branch (line 74–75):

```svelte
				{:else if $view === 'files'}
					<FilesView />
```

- [ ] **Step 4: Full verification gate**

```powershell
npm run check
npx vitest run src/lib/components/workos
cd C:\Projects\open-webui\backend; .\.venv\Scripts\python.exe -m pytest open_webui\test\workos -q
```

Expected: no new svelte-check errors; all vitest + pytest pass.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/views/FilesView.svelte src/lib/components/workos/chrome/Topbar.svelte src/lib/components/workos/WorkOSApp.svelte
git commit -m "feat(workos): activate the Files tab — workstream-wide files view

Type chips w/ live counts, search, Newest/Name/Size sort, list ⇄ grid,
recency sections (list) / gallery (grid), image thumbs via the cookie-
authed content URL, download + open-task actions, empty/error states.
Read-only by design — uploads stay on the task drawer.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Post-plan (not tasks): manual browser smoke

After all tasks land, smoke on the user's hot-reload server (do NOT start Vite): tab activation, chips/search/sort/toggle, image thumbnail auth, download, open-task drawer, live refetch when uploading/deleting a file from the task drawer in a second tab, dark mode, phone width.
