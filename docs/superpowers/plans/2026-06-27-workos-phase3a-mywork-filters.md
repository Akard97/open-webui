# WorkOS Phase 3a — My Work + Filters/Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a cross-team "My Work" dashboard, a shared client-side filter+scoped-search bar on board/list/My Work, and live realtime for the sidebar nav and My Work.

**Architecture:** One new read-only backend endpoint (`GET /me/tasks`) aggregates the caller's assigned-or-created tasks, visibility-filtered per task via `can_see_workstream`. All filtering, search, due-date bucketing, and the All/Assigned/Created segment are pure, unit-tested client modules. Realtime uses a ref-counted room manager so My Work can subscribe to many workstream rooms without disturbing the board's single active room.

**Tech Stack:** FastAPI + SQLAlchemy async (backend), pytest-asyncio; SvelteKit + Svelte 5 + TypeScript stores, Vitest; Socket.IO realtime.

## Global Constraints

- Branch: `osool` (the working branch). All commits land here.
- **No DB migration** — `/me/tasks` is read-only; nothing is persisted this slice.
- **Access-control standing rule:** `/me/tasks` is access-control-sensitive. After it lands, update `docs/superpowers/specs/2026-06-26-workos-access-control.md` §4 to document the endpoint + its per-task `can_see_workstream` filter (Task 1, final step). Assignment/authorship confer NO access — the filter enforces it.
- **Visibility filter is mandatory:** every task returned by `/me/tasks` must pass `can_see_workstream(user.id, is_admin, task.workstream_id)`. A task the caller created or is assigned to but cannot currently see is excluded.
- **Due-date buckets** are rolling, local-time: `overdue` = `due < start-of-today`; `today` = `start-of-today ≤ due ≤ end-of-today`; `thisWeek` = `end-of-today < due ≤ end-of-today + 7d`; `later` = `due > +7d`; `noDate` = `due == null`.
- **My Work excludes `done`/`canceled` by default** (re-includable via the Status facet) — applied in `MyWorkView`, not in `buckets.ts`.
- **§5 client-side guard:** the sidebar nav reconciler ignores incoming `*.created` events for `restricted` workspaces and workstream events whose parent workspace is not already in the store. The server-side fix stays a tracked §5 follow-up.
- `ViewKey` is defined in `src/lib/components/workos/lib/store.ts:14`; the default `view` (line 32) changes from `'board'` to `'mywork'`.
- **Test commands:**
  - Backend: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/<file> -v`
  - Frontend unit: `npx vitest run src/lib/components/workos/lib/<file>.test.ts`
  - Type check: `npm run check` (expect no new errors in touched files; the WorkOS tree must stay clean).
- Timestamps are epoch milliseconds in both task `due_date`/`start_date` and the frontend.

---

## File Structure

**Backend**
- `backend/open_webui/models/workos.py` — add `TasksDao.list_for_user(user_id, team_ids)` (near `list_for_workstream`, ~line 669).
- `backend/open_webui/routers/workos.py` — add `GET /me/tasks` handler (after `list_tasks`, ~line 655).
- `backend/open_webui/test/workos/test_router_my_tasks.py` — new test module.
- `docs/superpowers/specs/2026-06-26-workos-access-control.md` — §4 doc update.

**Frontend** (`src/lib/components/workos/`)
- `lib/filters.ts` + `lib/filters.test.ts` — pure `TaskFilter`, `matchesFilter`, `applyFilters`.
- `lib/buckets.ts` + `lib/buckets.test.ts` — pure `bucketByDueDate`.
- `lib/rooms.ts` + `lib/rooms.test.ts` — pure ref-counted `RoomRefs`.
- `lib/api.ts` — `listMyTasks(token)`.
- `lib/types.ts` — `TaskFilter`, `DueBuckets`, `MyWorkSegment` types.
- `lib/store.ts` — `myTasks`, `boardFilter`, `myWorkFilter`, `loadMyWork`/`teardownMyWork`, `applyMyWorkTaskEvent`, `foldInMyWorkFromNotification`, RoomRefs wiring, `'mywork'` view + default, filtered `tasksByStatus`, nav reconciler `applyNavEvent`, team-room subscription.
- `lib/store.test.ts` — extend with `tasksByStatus` filtering, My Work reconcile, nav reconcile tests.
- `chrome/FilterBar.svelte` — new shared filter+search bar.
- `views/MyWorkView.svelte` — new view (segment + buckets + FilterBar).
- `views/BoardView.svelte`, `views/ListView.svelte` — mount FilterBar.
- `chrome/Sidebar.svelte` — My Work entry.
- `WorkOSApp.svelte` — route `'mywork'`.

---

## Task 1: Backend `GET /me/tasks` aggregate endpoint

**Files:**
- Modify: `backend/open_webui/models/workos.py` (add `TasksDao.list_for_user`, ~after line 676)
- Modify: `backend/open_webui/routers/workos.py` (add handler after `list_tasks`, ~line 655)
- Test: `backend/open_webui/test/workos/test_router_my_tasks.py` (create)
- Modify: `docs/superpowers/specs/2026-06-26-workos-access-control.md` (§4)

**Interfaces:**
- Consumes: `Tasks` DAO, `Teams.list_for_user(user_id)` (models/workos.py:193), `Teams.list_all()` (:188), `can_see_workstream(user_id, is_admin, workstream_id, db)` (:1108), `_require_workos(request, user, db)` (routers/workos.py:53).
- Produces: `Tasks.list_for_user(user_id: str, team_ids: list[str], db=None) -> list[TaskModel]`; route `GET /api/v1/workos/me/tasks -> list[TaskModel]`.

- [ ] **Step 1: Write the failing test**

Create `backend/open_webui/test/workos/test_router_my_tasks.py`:

```python
import pytest

from open_webui.test.workos.test_router_teams import _client, U1, U2


async def _stream(c, *, visibility='team', name='Eng'):
    team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
    ws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                       json={'name': name, 'visibility': visibility})).json()
    s = (await c.post(f"/api/v1/workos/workspaces/{ws['id']}/workstreams", json={'name': 'Platform'})).json()
    return team, ws, s


@pytest.mark.asyncio
async def test_me_tasks_returns_created_and_assigned(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        # U1 adds U2 to the team so U2 is a valid (visible) assignee.
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        created = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'Mine'})).json()
        assigned = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks",
                                 json={'title': 'For u2', 'assignee_ids': ['u2']})).json()
        # U1 created both -> both appear for U1.
        ids = {t['id'] for t in (await c.get('/api/v1/workos/me/tasks')).json()}
        assert created['id'] in ids and assigned['id'] in ids
    async with _client(monkeypatch, user=U2) as c:
        u2_ids = {t['id'] for t in (await c.get('/api/v1/workos/me/tasks')).json()}
        # U2 sees only the task assigned to U2, not U1's solo task.
        assert assigned['id'] in u2_ids
        assert created['id'] not in u2_ids


@pytest.mark.asyncio
async def test_me_tasks_excludes_restricted_after_membership_revoked(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team = (await c.post('/api/v1/workos/teams', json={'name': 'Acme', 'key': 'OSL'})).json()
        await c.post(f"/api/v1/workos/teams/{team['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        rws = (await c.post(f"/api/v1/workos/teams/{team['id']}/workspaces",
                            json={'name': 'Secret', 'visibility': 'restricted'})).json()
        await c.post(f"/api/v1/workos/workspaces/{rws['id']}/members", json={'user_id': 'u2', 'role': 'member'})
        s = (await c.post(f"/api/v1/workos/workspaces/{rws['id']}/workstreams", json={'name': 'S'})).json()
    async with _client(monkeypatch, user=U2) as c:
        task = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'U2 secret'})).json()
        assert task['id'] in {t['id'] for t in (await c.get('/api/v1/workos/me/tasks')).json()}
    # U1 revokes U2's access to the restricted workspace.
    async with _client(monkeypatch, user=U1) as c:
        assert (await c.delete(f"/api/v1/workos/workspaces/{rws['id']}/members/u2")).status_code == 200
    async with _client(monkeypatch, user=U2) as c:
        # U2 created the task but can no longer see the workstream -> excluded.
        assert task['id'] not in {t['id'] for t in (await c.get('/api/v1/workos/me/tasks')).json()}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_router_my_tasks.py -v`
Expected: FAIL — `404 Not Found` for `/api/v1/workos/me/tasks` (route does not exist).

- [ ] **Step 3: Add the DAO method**

In `backend/open_webui/models/workos.py`, inside `class TasksDao`, after `list_for_workstream` (ends ~line 676), add:

```python
    async def list_for_user(
        self, user_id: str, team_ids: list, db: Optional[AsyncSession] = None
    ) -> list[TaskModel]:
        """Tasks the user created or is assigned to, within the given teams.

        Candidates are bounded by ``team_id IN team_ids`` (the denormalized team
        column), then membership is decided in Python because ``assignee_ids`` is a
        JSON list with no portable SQL containment across SQLite/Postgres. The router
        applies the per-task visibility filter on top.
        """
        if not team_ids:
            return []
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosTask)
                .filter(WorkosTask.team_id.in_(team_ids))
                .order_by(WorkosTask.created_at.asc())
            )
            rows = [
                r for r in res.scalars().all()
                if r.created_by_id == user_id or user_id in (r.assignee_ids or [])
            ]
            return await self._with_counts(rows, db)
```

- [ ] **Step 4: Add the router endpoint**

In `backend/open_webui/routers/workos.py`, after the `list_tasks` handler (ends line 654), add:

```python
@router.get('/me/tasks')
async def list_my_tasks(
    request: Request, user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    is_admin = user.role == 'admin'
    teams = await Teams.list_all(db=db) if is_admin else await Teams.list_for_user(user.id, db=db)
    candidates = await Tasks.list_for_user(user.id, [t.id for t in teams], db=db)
    visible = []
    for task in candidates:
        if await can_see_workstream(user.id, is_admin, task.workstream_id, db=db):
            visible.append(task)
    return visible
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_router_my_tasks.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Guard against route-shadowing regressions**

Run the existing task-route suite to confirm `/me/tasks` did not shadow `/tasks/{id}` or vice versa:
Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/test_router_task.py -v`
Expected: PASS (all existing tests).

- [ ] **Step 7: Update the access-control reference doc**

In `docs/superpowers/specs/2026-06-26-workos-access-control.md`, in the §4 **Tasks** table, add a row after the `GET /tasks/{id}` row:

```markdown
| `GET /me/tasks` | `_require_workos`; intrinsically user-scoped; returns tasks where caller is creator OR in `assignee_ids`, each filtered through `can_see_workstream` (assignment/authorship confer no access — visibility still enforced); admin scoped to own created/assigned across all teams | [workos.py](backend/open_webui/routers/workos.py) |
```

- [ ] **Step 8: Commit**

```bash
git add backend/open_webui/models/workos.py backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_my_tasks.py docs/superpowers/specs/2026-06-26-workos-access-control.md
git commit -m "feat(workos): GET /me/tasks aggregate endpoint (Phase 3a)"
```

---

## Task 2: Pure filter engine (`lib/filters.ts`)

**Files:**
- Create: `src/lib/components/workos/lib/filters.ts`
- Modify: `src/lib/components/workos/lib/types.ts` (add `TaskFilter`)
- Test: `src/lib/components/workos/lib/filters.test.ts` (create)

**Interfaces:**
- Consumes: `Task`, `TaskStatus`, `TaskPriority` from `./types`.
- Produces: `TaskFilter` type; `emptyFilter(): TaskFilter`; `matchesFilter(task: Task, f: TaskFilter): boolean`; `applyFilters(tasks: Task[], f: TaskFilter): Task[]`.

- [ ] **Step 1: Add the type**

In `src/lib/components/workos/lib/types.ts`, after `PRIORITY_ORDER` (line 178), add:

```typescript
export interface TaskFilter {
	statuses: TaskStatus[];
	priorities: TaskPriority[];
	labelIds: string[];
	assigneeIds: string[];
	text: string;
}
```

- [ ] **Step 2: Write the failing test**

Create `src/lib/components/workos/lib/filters.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { emptyFilter, matchesFilter, applyFilters } from './filters';
import type { Task, TaskFilter } from './types';

const mk = (over: Partial<Task>): Task => ({
	id: 'x', workstream_id: 'w1', team_id: 'tm', number: 1, key: 'OSL-1', title: 'Hello',
	status: 'todo', priority: 'high', assignee_ids: ['u1'], progress: 0, labels: ['l1'],
	sort_key: 1, created_by_id: 'u1', created_at: 0, updated_at: 0, ...over
});
const f = (over: Partial<TaskFilter>): TaskFilter => ({ ...emptyFilter(), ...over });

describe('matchesFilter', () => {
	it('empty filter matches everything', () => {
		expect(matchesFilter(mk({}), emptyFilter())).toBe(true);
	});
	it('status facet narrows by status', () => {
		expect(matchesFilter(mk({ status: 'todo' }), f({ statuses: ['done'] }))).toBe(false);
		expect(matchesFilter(mk({ status: 'done' }), f({ statuses: ['done'] }))).toBe(true);
	});
	it('priority facet narrows by priority', () => {
		expect(matchesFilter(mk({ priority: 'low' }), f({ priorities: ['high'] }))).toBe(false);
	});
	it('label facet matches when any label overlaps', () => {
		expect(matchesFilter(mk({ labels: ['l1', 'l2'] }), f({ labelIds: ['l2'] }))).toBe(true);
		expect(matchesFilter(mk({ labels: ['l1'] }), f({ labelIds: ['l9'] }))).toBe(false);
	});
	it('assignee facet matches when any assignee overlaps', () => {
		expect(matchesFilter(mk({ assignee_ids: ['u1'] }), f({ assigneeIds: ['u1'] }))).toBe(true);
		expect(matchesFilter(mk({ assignee_ids: ['u1'] }), f({ assigneeIds: ['u2'] }))).toBe(false);
	});
	it('text matches title or key, case-insensitive', () => {
		expect(matchesFilter(mk({ title: 'Migrate billing' }), f({ text: 'BILL' }))).toBe(true);
		expect(matchesFilter(mk({ key: 'OSL-42' }), f({ text: 'osl-42' }))).toBe(true);
		expect(matchesFilter(mk({ title: 'X', key: 'OSL-1' }), f({ text: 'zzz' }))).toBe(false);
	});
});

describe('applyFilters', () => {
	it('returns only matching tasks', () => {
		const tasks = [mk({ id: 'a', status: 'todo' }), mk({ id: 'b', status: 'done' })];
		expect(applyFilters(tasks, f({ statuses: ['done'] })).map((t) => t.id)).toEqual(['b']);
	});
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npx vitest run src/lib/components/workos/lib/filters.test.ts`
Expected: FAIL — cannot resolve `./filters`.

- [ ] **Step 4: Implement the engine**

Create `src/lib/components/workos/lib/filters.ts`:

```typescript
import type { Task, TaskFilter } from './types';

export function emptyFilter(): TaskFilter {
	return { statuses: [], priorities: [], labelIds: [], assigneeIds: [], text: '' };
}

const overlaps = (a: string[], b: string[]): boolean => a.some((x) => b.includes(x));

export function matchesFilter(task: Task, f: TaskFilter): boolean {
	if (f.statuses.length && !f.statuses.includes(task.status)) return false;
	if (f.priorities.length && !(task.priority && f.priorities.includes(task.priority))) return false;
	if (f.labelIds.length && !overlaps(task.labels ?? [], f.labelIds)) return false;
	if (f.assigneeIds.length && !overlaps(task.assignee_ids ?? [], f.assigneeIds)) return false;
	const text = f.text.trim().toLowerCase();
	if (text && !(`${task.title} ${task.key}`.toLowerCase().includes(text))) return false;
	return true;
}

export function applyFilters(tasks: Task[], f: TaskFilter): Task[] {
	return tasks.filter((t) => matchesFilter(t, f));
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run src/lib/components/workos/lib/filters.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/lib/filters.ts src/lib/components/workos/lib/filters.test.ts src/lib/components/workos/lib/types.ts
git commit -m "feat(workos): pure task filter engine (Phase 3a)"
```

---

## Task 3: Pure due-date bucketing (`lib/buckets.ts`)

**Files:**
- Create: `src/lib/components/workos/lib/buckets.ts`
- Modify: `src/lib/components/workos/lib/types.ts` (add `DueBuckets`)
- Test: `src/lib/components/workos/lib/buckets.test.ts` (create)

**Interfaces:**
- Consumes: `Task` from `./types`.
- Produces: `DueBuckets` type; `bucketByDueDate(tasks: Task[], now: number): DueBuckets`; `BUCKET_ORDER: (keyof DueBuckets)[]`; `BUCKET_LABEL: Record<keyof DueBuckets, string>`.

- [ ] **Step 1: Add the type**

In `src/lib/components/workos/lib/types.ts`, after the `TaskFilter` interface (from Task 2), add:

```typescript
export interface DueBuckets {
	overdue: Task[];
	today: Task[];
	thisWeek: Task[];
	later: Task[];
	noDate: Task[];
}
```

- [ ] **Step 2: Write the failing test**

Create `src/lib/components/workos/lib/buckets.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { bucketByDueDate } from './buckets';
import type { Task } from './types';

const DAY = 86_400_000;
// Fixed "now": 2024-03-06 12:00 local.
const NOW = new Date(2024, 2, 6, 12, 0, 0).getTime();
const at = (d: Date) => d.getTime();

const mk = (id: string, due: number | null): Task => ({
	id, workstream_id: 'w1', team_id: 'tm', number: 1, key: 'OSL-1', title: id,
	status: 'todo', assignee_ids: [], progress: 0, labels: [], sort_key: 1,
	created_by_id: 'u1', due_date: due, created_at: 0, updated_at: 0
});

describe('bucketByDueDate', () => {
	it('classifies each task into the right rolling bucket', () => {
		const tasks = [
			mk('overdue', at(new Date(2024, 2, 5, 9, 0))),       // yesterday
			mk('today', at(new Date(2024, 2, 6, 18, 0))),        // later today
			mk('thisWeek', NOW + 3 * DAY),                       // +3 days
			mk('later', NOW + 30 * DAY),                         // +30 days
			mk('noDate', null)
		];
		const b = bucketByDueDate(tasks, NOW);
		expect(b.overdue.map((t) => t.id)).toEqual(['overdue']);
		expect(b.today.map((t) => t.id)).toEqual(['today']);
		expect(b.thisWeek.map((t) => t.id)).toEqual(['thisWeek']);
		expect(b.later.map((t) => t.id)).toEqual(['later']);
		expect(b.noDate.map((t) => t.id)).toEqual(['noDate']);
	});
	it('the 7-day boundary is inclusive of thisWeek, exclusive into later', () => {
		const endToday = new Date(2024, 2, 6, 23, 59, 59, 999).getTime();
		const b = bucketByDueDate([mk('edge', endToday + 7 * DAY)], NOW);
		expect(b.thisWeek.map((t) => t.id)).toEqual(['edge']);
	});
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `npx vitest run src/lib/components/workos/lib/buckets.test.ts`
Expected: FAIL — cannot resolve `./buckets`.

- [ ] **Step 4: Implement bucketing**

Create `src/lib/components/workos/lib/buckets.ts`:

```typescript
import type { Task, DueBuckets } from './types';

export const BUCKET_ORDER: (keyof DueBuckets)[] = ['overdue', 'today', 'thisWeek', 'later', 'noDate'];
export const BUCKET_LABEL: Record<keyof DueBuckets, string> = {
	overdue: 'Overdue', today: 'Today', thisWeek: 'This week', later: 'Later', noDate: 'No date'
};

export function bucketByDueDate(tasks: Task[], now: number): DueBuckets {
	const d = new Date(now);
	const startToday = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
	const endToday = startToday + 86_400_000 - 1;
	const endWeek = endToday + 7 * 86_400_000;
	const out: DueBuckets = { overdue: [], today: [], thisWeek: [], later: [], noDate: [] };
	for (const t of tasks) {
		const due = t.due_date;
		if (due == null) out.noDate.push(t);
		else if (due < startToday) out.overdue.push(t);
		else if (due <= endToday) out.today.push(t);
		else if (due <= endWeek) out.thisWeek.push(t);
		else out.later.push(t);
	}
	return out;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run src/lib/components/workos/lib/buckets.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/lib/buckets.ts src/lib/components/workos/lib/buckets.test.ts src/lib/components/workos/lib/types.ts
git commit -m "feat(workos): pure due-date bucketing (Phase 3a)"
```

---

## Task 4: Pure ref-counted room manager (`lib/rooms.ts`)

**Files:**
- Create: `src/lib/components/workos/lib/rooms.ts`
- Test: `src/lib/components/workos/lib/rooms.test.ts` (create)

**Interfaces:**
- Produces: `class RoomRefs` with constructor `(onSubscribe: (key: string) => void, onUnsubscribe: (key: string) => void)`, methods `enter(key: string): void`, `leave(key: string): void`, `keys(): string[]`.

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/workos/lib/rooms.test.ts`:

```typescript
import { describe, it, expect, vi } from 'vitest';
import { RoomRefs } from './rooms';

describe('RoomRefs', () => {
	it('subscribes once on first enter, no re-emit on second enter', () => {
		const sub = vi.fn(), unsub = vi.fn();
		const r = new RoomRefs(sub, unsub);
		r.enter('stream:a');
		r.enter('stream:a');
		expect(sub).toHaveBeenCalledTimes(1);
	});
	it('unsubscribes only when the last reference leaves', () => {
		const sub = vi.fn(), unsub = vi.fn();
		const r = new RoomRefs(sub, unsub);
		r.enter('stream:a');
		r.enter('stream:a');
		r.leave('stream:a');
		expect(unsub).not.toHaveBeenCalled(); // board still holds it
		r.leave('stream:a');
		expect(unsub).toHaveBeenCalledTimes(1);
	});
	it('leave on an unknown key is a no-op', () => {
		const sub = vi.fn(), unsub = vi.fn();
		const r = new RoomRefs(sub, unsub);
		r.leave('stream:ghost');
		expect(unsub).not.toHaveBeenCalled();
	});
	it('keys() lists currently-held rooms', () => {
		const r = new RoomRefs(vi.fn(), vi.fn());
		r.enter('team:t1');
		r.enter('stream:a');
		expect(r.keys().sort()).toEqual(['stream:a', 'team:t1']);
	});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/lib/components/workos/lib/rooms.test.ts`
Expected: FAIL — cannot resolve `./rooms`.

- [ ] **Step 3: Implement RoomRefs**

Create `src/lib/components/workos/lib/rooms.ts`:

```typescript
/** Reference-counted room membership. Emits subscribe on 0→1 and unsubscribe on 1→0,
 * so overlapping subscribers (e.g. the board's active workstream and My Work's set)
 * never tear down a room another consumer still needs. */
export class RoomRefs {
	private refs = new Map<string, number>();
	constructor(
		private onSubscribe: (key: string) => void,
		private onUnsubscribe: (key: string) => void
	) {}

	enter(key: string): void {
		const n = (this.refs.get(key) ?? 0) + 1;
		this.refs.set(key, n);
		if (n === 1) this.onSubscribe(key);
	}

	leave(key: string): void {
		const cur = this.refs.get(key);
		if (!cur) return;
		if (cur <= 1) {
			this.refs.delete(key);
			this.onUnsubscribe(key);
		} else {
			this.refs.set(key, cur - 1);
		}
	}

	keys(): string[] {
		return [...this.refs.keys()];
	}
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/lib/components/workos/lib/rooms.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/rooms.ts src/lib/components/workos/lib/rooms.test.ts
git commit -m "feat(workos): pure ref-counted room manager (Phase 3a)"
```

---

## Task 5: Rewire store socket subscriptions onto RoomRefs

**Files:**
- Modify: `src/lib/components/workos/lib/store.ts` (subscription helpers + call sites)

**Interfaces:**
- Consumes: `RoomRefs` from `./rooms`.
- Produces: module functions `enterRoom(key: string)`, `leaveRoom(key: string)` used by later tasks; `streamKey(id)`/`teamKey(id)` helpers.

This task refactors the existing single-room logic (`subscribeRoom`/`unsubscribeRoom`, `selectWorkstream`, `connectRealtime`, `disconnectRealtime`) onto `RoomRefs` without behavior change for the board. It is verified by `npm run check` + the existing `store.test.ts` still passing (no new unit test — the ref-count logic is covered by Task 4).

- [ ] **Step 1: Replace the subscription helpers**

In `src/lib/components/workos/lib/store.ts`, replace the existing `subscribeRoom`/`unsubscribeRoom` block (lines 378–388) with:

```typescript
function streamKey(id: string): string { return `stream:${id}`; }
function teamKey(id: string): string { return `team:${id}`; }

function emitSub(key: string): void {
	const s = get(socket);
	if (!s || !browser) return;
	const [kind, id] = [key.slice(0, key.indexOf(':')), key.slice(key.indexOf(':') + 1)];
	if (kind === 'team') s.emit('workos:subscribe', { auth: { token: token() }, team_id: id });
	else s.emit('workos:subscribe', { auth: { token: token() }, workstream_id: id });
}
function emitUnsub(key: string): void {
	const s = get(socket);
	if (!s || !browser) return;
	const [kind, id] = [key.slice(0, key.indexOf(':')), key.slice(key.indexOf(':') + 1)];
	if (kind === 'team') s.emit('workos:unsubscribe', { team_id: id });
	else s.emit('workos:unsubscribe', { workstream_id: id });
}

const rooms = new RoomRefs(emitSub, emitUnsub);
export function enterRoom(key: string): void { rooms.enter(key); }
export function leaveRoom(key: string): void { rooms.leave(key); }
```

- [ ] **Step 2: Import RoomRefs**

At the top of `store.ts`, add to the imports (after the `./key` import, line 6):

```typescript
import { RoomRefs } from './rooms';
```

- [ ] **Step 3: Update `selectWorkstream` call sites**

In `selectWorkstream` (lines 138–145), replace `unsubscribeRoom(prev)` with `leaveRoom(streamKey(prev))` and `subscribeRoom(id)` with `enterRoom(streamKey(id))`:

```typescript
export async function selectWorkstream(id: string): Promise<void> {
	const prev = get(currentWorkstreamId);
	if (prev && prev !== id) leaveRoom(streamKey(prev));
	currentWorkstreamId.set(id);
	selectedTaskId.set(null);
	tasks.set(await api.listTasks(token(), id).catch(() => []));
	enterRoom(streamKey(id));
}
```

- [ ] **Step 4: Update `connectRealtime` / `disconnectRealtime`**

In `connectRealtime` (lines 393–415), replace the reconnect handler and the trailing initial-subscribe so they re-subscribe the whole held set:

```typescript
	// Re-subscribe every held room on reconnect.
	handlers['connect'] = () => {
		for (const key of rooms.keys()) emitSub(key);
	};
	s.on('connect', handlers['connect']);
	bound = true;
}
```

(Remove the old trailing `const ws = get(currentWorkstreamId); if (ws) subscribeRoom(ws);` — `selectWorkstream` already entered the room, and the `connect` handler re-subscribes it.)

In `disconnectRealtime` (lines 417–429), replace the trailing `const ws = get(currentWorkstreamId); if (ws) unsubscribeRoom(ws);` with:

```typescript
	for (const key of rooms.keys()) emitUnsub(key);
```

- [ ] **Step 5: Verify type-check and existing tests**

Run: `npm run check`
Expected: no new errors in `store.ts`.
Run: `npx vitest run src/lib/components/workos/lib/store.test.ts`
Expected: PASS (existing realtime/optimistic tests unaffected).

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/lib/store.ts
git commit -m "refactor(workos): ref-counted room subscriptions (Phase 3a)"
```

---

## Task 6: My Work store state + live reconciliation

**Files:**
- Modify: `src/lib/components/workos/lib/api.ts` (add `listMyTasks`)
- Modify: `src/lib/components/workos/lib/store.ts` (state, load/teardown, reconcilers, wiring)
- Modify: `src/lib/components/workos/lib/store.test.ts` (extend)

**Interfaces:**
- Consumes: `api.listMyTasks(token)`, `api.getTask(token, id)`, `enterRoom`/`leaveRoom`/`streamKey` (Task 5), `user` store.
- Produces: `myTasks: Writable<Task[]>`; `loadMyWork(): Promise<void>`; `teardownMyWork(): void`; `applyMyWorkTaskEvent(event, payload, uid): void`; `foldInMyWorkFromNotification(payload): Promise<void>`.

- [ ] **Step 1: Add the API wrapper**

In `src/lib/components/workos/lib/api.ts`, after `listTasks` (line 87), add:

```typescript
export const listMyTasks = (token: string) => request<Task[]>(token, '/me/tasks');
```

- [ ] **Step 2: Write the failing tests**

Append to `src/lib/components/workos/lib/store.test.ts`. First extend the `./api` mock (add `listMyTasks` + `getTask` to the `vi.mock('./api', ...)` object near line 4):

```typescript
	listMyTasks: vi.fn(async () => []),
	getTask: vi.fn(async () => ({
		id: 'folded', workstream_id: 'wX', team_id: 'tm', number: 9, key: 'OSL-9', title: 'Folded',
		status: 'todo', priority: null, assignee_ids: ['u1'], progress: 0, labels: [], sort_key: 1,
		created_by_id: 'u2', created_at: 0, updated_at: 0
	})),
```

Then add a new describe block at the end of the file:

```typescript
import { myTasks, applyMyWorkTaskEvent, loadMyWork, foldInMyWorkFromNotification } from './store';

const mkT = (over: Partial<Task>): Task => ({
	id: 'x', workstream_id: 'w1', team_id: 'tm', number: 1, key: 'OSL-1', title: 't',
	status: 'todo', assignee_ids: [], progress: 0, labels: [], sort_key: 1, created_by_id: 'u9',
	created_at: 0, updated_at: 0, ...over
});

describe('my work reconcile', () => {
	beforeEach(() => myTasks.set([]));

	it('adds a created-by-me task on task.created', () => {
		applyMyWorkTaskEvent('workos:task.created', mkT({ id: 'a', created_by_id: 'u1' }), 'u1');
		expect(get(myTasks).map((t) => t.id)).toEqual(['a']);
	});
	it('adds an assigned-to-me task and dedupes', () => {
		applyMyWorkTaskEvent('workos:task.created', mkT({ id: 'a', assignee_ids: ['u1'] }), 'u1');
		applyMyWorkTaskEvent('workos:task.created', mkT({ id: 'a', assignee_ids: ['u1'] }), 'u1');
		expect(get(myTasks).filter((t) => t.id === 'a')).toHaveLength(1);
	});
	it('removes a task on update when I am no longer assignee/creator', () => {
		myTasks.set([mkT({ id: 'a', assignee_ids: ['u1'], created_by_id: 'u9' })]);
		applyMyWorkTaskEvent('workos:task.updated', mkT({ id: 'a', assignee_ids: [], created_by_id: 'u9' }), 'u1');
		expect(get(myTasks)).toHaveLength(0);
	});
	it('removes a task on delete', () => {
		myTasks.set([mkT({ id: 'a', created_by_id: 'u1' })]);
		applyMyWorkTaskEvent('workos:task.deleted', { id: 'a' }, 'u1');
		expect(get(myTasks)).toHaveLength(0);
	});
	it('folds in a task from a new assigned notification while active', async () => {
		await loadMyWork(); // sets myWorkActive = true; mocked listMyTasks returns []
		await foldInMyWorkFromNotification({ type: 'assigned', task_id: 'folded' });
		expect(get(myTasks).map((t) => t.id)).toContain('folded');
	});
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `npx vitest run src/lib/components/workos/lib/store.test.ts`
Expected: FAIL — `applyMyWorkTaskEvent` / `loadMyWork` / `foldInMyWorkFromNotification` not exported.

- [ ] **Step 4: Add state, load/teardown, and reconcilers**

In `src/lib/components/workos/lib/store.ts`, after the `subtasks` writable (line 40), add:

```typescript
export const myTasks: Writable<Task[]> = writable([]);
let myWorkActive = false;
const myWorkRooms = new Set<string>();
```

After `loadNotifications` (around line 310), add:

```typescript
export async function loadMyWork(): Promise<void> {
	myWorkActive = true;
	const mine = await api.listMyTasks(token()).catch(() => []);
	myTasks.set(mine);
	for (const id of new Set(mine.map((t) => t.workstream_id))) {
		const key = streamKey(id);
		myWorkRooms.add(key);
		enterRoom(key);
	}
}

export function teardownMyWork(): void {
	myWorkActive = false;
	for (const key of myWorkRooms) leaveRoom(key);
	myWorkRooms.clear();
}

/** Reconcile a task realtime event into the cross-team My Work list. */
export function applyMyWorkTaskEvent(event: string, payload: any, uid: string): void {
	if (!payload || !payload.id) return;
	if (event === 'workos:task.deleted') {
		myTasks.update((l) => l.filter((t) => t.id !== payload.id));
		return;
	}
	const mine = payload.created_by_id === uid || (payload.assignee_ids ?? []).includes(uid);
	myTasks.update((l) => {
		const exists = l.some((t) => t.id === payload.id);
		if (mine) return exists ? l.map((t) => (t.id === payload.id ? payload : t)) : [...l, payload];
		return exists ? l.filter((t) => t.id !== payload.id) : l;
	});
}

/** A new assigned/mentioned notification may reference a task in a workstream My Work
 * has not subscribed to yet — pull it in and join its room. */
export async function foldInMyWorkFromNotification(payload: any): Promise<void> {
	if (!myWorkActive || !payload || (payload.type !== 'assigned' && payload.type !== 'mentioned')) return;
	const taskId = payload.task_id;
	if (!taskId || get(myTasks).some((t) => t.id === taskId)) return;
	const t = await api.getTask(token(), taskId).catch(() => null);
	if (!t) return;
	myTasks.update((l) => (l.some((x) => x.id === t.id) ? l : [...l, t]));
	const key = streamKey(t.workstream_id);
	myWorkRooms.add(key);
	enterRoom(key);
}
```

- [ ] **Step 5: Wire reconcilers into the socket handlers**

In `connectRealtime` (the `TASK_EVENTS` loop, lines 396–399), change the task handler to also reconcile My Work:

```typescript
	for (const ev of TASK_EVENTS) {
		handlers[ev] = (payload: any) => {
			applyTaskEvent(ev, payload);
			if (myWorkActive) applyMyWorkTaskEvent(ev, payload, get(user)?.id ?? '');
		};
		s.on(ev, handlers[ev]);
	}
```

And change the notification handler (lines 404–405) to also fold in:

```typescript
	handlers['workos:notification.created'] = (payload: any) => {
		applyNotificationEvent(payload);
		void foldInMyWorkFromNotification(payload);
	};
	s.on('workos:notification.created', handlers['workos:notification.created']);
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `npx vitest run src/lib/components/workos/lib/store.test.ts`
Expected: PASS (existing + 5 new).

- [ ] **Step 7: Commit**

```bash
git add src/lib/components/workos/lib/api.ts src/lib/components/workos/lib/store.ts src/lib/components/workos/lib/store.test.ts
git commit -m "feat(workos): My Work store state + live reconciliation (Phase 3a)"
```

---

## Task 7: Filtered `tasksByStatus` + shared FilterBar on board/list

**Files:**
- Modify: `src/lib/components/workos/lib/store.ts` (`boardFilter`, filter `tasksByStatus`)
- Modify: `src/lib/components/workos/lib/store.test.ts` (filtering test)
- Create: `src/lib/components/workos/chrome/FilterBar.svelte`
- Modify: `src/lib/components/workos/views/BoardView.svelte` (mount FilterBar, drop placeholders)
- Modify: `src/lib/components/workos/views/ListView.svelte` (mount FilterBar)

**Interfaces:**
- Consumes: `applyFilters` (Task 2), `labels`, `directory`, `STATUS_ORDER`, `PRIORITY_ORDER`.
- Produces: `boardFilter: Writable<TaskFilter>`; `FilterBar.svelte` (props: `filter: Writable<TaskFilter>`, `showAssignee?: boolean`).

- [ ] **Step 1: Write the failing store test**

Append to `src/lib/components/workos/lib/store.test.ts`:

```typescript
import { boardFilter } from './store';

describe('tasksByStatus filtering', () => {
	beforeEach(() => { boardFilter.set({ statuses: [], priorities: [], labelIds: [], assigneeIds: [], text: '' }); });
	it('applies the board filter before grouping', () => {
		tasks.set([mkT({ id: 'a', status: 'todo', title: 'Alpha' }), mkT({ id: 'b', status: 'todo', title: 'Beta' })]);
		boardFilter.set({ statuses: [], priorities: [], labelIds: [], assigneeIds: [], text: 'alpha' });
		const grouped = get(tasksByStatus);
		expect(grouped.todo.map((t) => t.id)).toEqual(['a']);
	});
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run src/lib/components/workos/lib/store.test.ts`
Expected: FAIL — `boardFilter` not exported.

- [ ] **Step 3: Add `boardFilter` and filter `tasksByStatus`**

In `store.ts`, add the import near the top (after the `./rooms` import):

```typescript
import { applyFilters, emptyFilter } from './filters';
```

Add the store (after `view`, line 32):

```typescript
export const boardFilter: Writable<TaskFilter> = writable(emptyFilter());
export const myWorkFilter: Writable<TaskFilter> = writable(emptyFilter());
```

Add `TaskFilter` to the `./types` import list (line 9–11). Then replace the `tasksByStatus` derived (lines 70–76) with:

```typescript
export const tasksByStatus = derived([tasks, boardFilter], ([$tasks, $filter]) => {
	const out: Record<TaskStatus, Task[]> = {
		backlog: [], todo: [], in_progress: [], in_review: [], done: [], canceled: []
	};
	for (const t of applyFilters([...$tasks].sort((a, b) => a.sort_key - b.sort_key), $filter)) out[t.status]?.push(t);
	return out;
});
```

- [ ] **Step 4: Run store test to verify pass**

Run: `npx vitest run src/lib/components/workos/lib/store.test.ts`
Expected: PASS.

- [ ] **Step 5: Create FilterBar.svelte**

Create `src/lib/components/workos/chrome/FilterBar.svelte`:

```svelte
<script lang="ts">
	import type { Writable } from 'svelte/store';
	import Icon from '../ui/Icon.svelte';
	import { STATUS_ORDER, STATUS_LABEL, PRIORITY_ORDER, type TaskFilter } from '../lib/types';
	import { labels, directory } from '../lib/store';

	export let filter: Writable<TaskFilter>;
	export let showAssignee = true;

	let open: string | null = null;
	const toggle = (k: string) => (open = open === k ? null : k);

	function flip(key: 'statuses' | 'priorities' | 'labelIds' | 'assigneeIds', val: string) {
		filter.update((f) => {
			const set = new Set(f[key] as string[]);
			set.has(val) ? set.delete(val) : set.add(val);
			return { ...f, [key]: [...set] };
		});
	}
	const count = (n: number) => (n ? ` · ${n}` : '');
	$: dirEntries = Object.entries($directory);
</script>

<div class="flex-none flex items-center gap-2 px-4 py-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
	<!-- Status -->
	<div class="relative">
		<button class="filter-chip" onclick={() => toggle('status')}>
			<span class="text-gray-400">Status</span><span class="font-medium">{count($filter.statuses.length) || ' All'}</span>
			<Icon name="chevron-down" size={13} />
		</button>
		{#if open === 'status'}
			<div class="filter-menu">
				{#each STATUS_ORDER as s (s)}
					<label class="filter-item"><input type="checkbox" checked={$filter.statuses.includes(s)} onchange={() => flip('statuses', s)} /> {STATUS_LABEL[s]}</label>
				{/each}
			</div>
		{/if}
	</div>
	<!-- Priority -->
	<div class="relative">
		<button class="filter-chip" onclick={() => toggle('priority')}>
			<span class="text-gray-400">Priority</span><span class="font-medium">{count($filter.priorities.length) || ' All'}</span>
			<Icon name="chevron-down" size={13} />
		</button>
		{#if open === 'priority'}
			<div class="filter-menu">
				{#each PRIORITY_ORDER as p (p)}
					<label class="filter-item"><input type="checkbox" checked={$filter.priorities.includes(p)} onchange={() => flip('priorities', p)} /> {p}</label>
				{/each}
			</div>
		{/if}
	</div>
	<!-- Label -->
	<div class="relative">
		<button class="filter-chip" onclick={() => toggle('label')}>
			<span class="text-gray-400">Label</span><span class="font-medium">{count($filter.labelIds.length) || ' All'}</span>
			<Icon name="chevron-down" size={13} />
		</button>
		{#if open === 'label'}
			<div class="filter-menu">
				{#each $labels as l (l.id)}
					<label class="filter-item"><input type="checkbox" checked={$filter.labelIds.includes(l.id)} onchange={() => flip('labelIds', l.id)} /> {l.name}</label>
				{/each}
			</div>
		{/if}
	</div>
	<!-- Assignee (hidden on My Work) -->
	{#if showAssignee}
		<div class="relative">
			<button class="filter-chip" onclick={() => toggle('assignee')}>
				<span class="text-gray-400">Assignee</span><span class="font-medium">{count($filter.assigneeIds.length) || ' All'}</span>
				<Icon name="chevron-down" size={13} />
			</button>
			{#if open === 'assignee'}
				<div class="filter-menu">
					{#each dirEntries as [id, u] (id)}
						<label class="filter-item"><input type="checkbox" checked={$filter.assigneeIds.includes(id)} onchange={() => flip('assigneeIds', id)} /> {u.name}</label>
					{/each}
				</div>
			{/if}
		</div>
	{/if}

	<div class="flex-1"></div>

	<div class="relative">
		<input
			class="text-sm pl-8 pr-2 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-transparent w-56"
			placeholder="Search title or key…"
			value={$filter.text}
			oninput={(e) => filter.update((f) => ({ ...f, text: (e.target as HTMLInputElement).value }))}
		/>
		<span class="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"><Icon name="search" size={14} /></span>
	</div>
</div>

<style>
	.filter-chip { display: inline-flex; align-items: center; gap: 0.375rem; padding: 0.375rem 0.75rem; border-radius: 0.5rem; border: 1px solid rgb(229 231 235); font-size: 0.75rem; }
	:global(.dark) .filter-chip { border-color: rgb(31 41 55); }
	.filter-menu { position: absolute; z-index: 30; margin-top: 0.25rem; min-width: 11rem; border-radius: 0.5rem; border: 1px solid rgb(229 231 235); background: white; box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1); padding: 0.25rem; }
	:global(.dark) .filter-menu { background: rgb(17 24 39); border-color: rgb(31 41 55); }
	.filter-item { display: flex; align-items: center; gap: 0.5rem; padding: 0.25rem 0.5rem; font-size: 0.8125rem; border-radius: 0.25rem; cursor: pointer; }
	.filter-item:hover { background: rgb(243 244 246); }
	:global(.dark) .filter-item:hover { background: rgb(31 41 55); }
</style>
```

(If `search` is not a registered glyph in `ui/Icon.svelte`, reuse an existing one — check `ui/Icon.svelte` and substitute, e.g. `sliders`.)

- [ ] **Step 6: Mount FilterBar in BoardView**

In `src/lib/components/workos/views/BoardView.svelte`: remove the `FILTERS` constant (lines 21–25) and replace the placeholder filter block (lines 130–149, the `{#each FILTERS …}` buttons and the "Advance Filters" button) with the FilterBar, keeping the "Add New" control. First add imports:

```svelte
	import FilterBar from '../chrome/FilterBar.svelte';
	import { boardFilter } from '../lib/store';
```

Replace the filter buttons inside the `<div class="flex-none flex items-center gap-2 …">` so the bar's left side is `<FilterBar filter={boardFilter} />`. Simplest: replace the whole top `<div class="flex-none …">…</div>` (lines 129–169) with:

```svelte
	<div class="flex-none flex items-stretch">
		<div class="flex-1"><FilterBar filter={boardFilter} /></div>
		<div class="flex items-center px-4 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
			{#if creatingTop}
				<input class="text-sm px-2 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent w-56" placeholder="Task title…" bind:value={topTitle} onkeydown={(e) => { if (e.key === 'Enter') submitTop(); if (e.key === 'Escape') { creatingTop = false; topTitle = ''; } }} autofocus />
			{:else}
				<button class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground text-sm font-medium" onclick={() => (creatingTop = true)}>
					<Icon name="plus" size={15} /> Add New
				</button>
			{/if}
		</div>
	</div>
```

- [ ] **Step 7: Mount FilterBar in ListView**

In `src/lib/components/workos/views/ListView.svelte`, add imports and render `<FilterBar filter={boardFilter} />` at the top of the view (above the grouped list). Add:

```svelte
	import FilterBar from '../chrome/FilterBar.svelte';
	import { boardFilter } from '../lib/store';
```

and place `<FilterBar filter={boardFilter} />` as the first child of the view's root container. (ListView already reads `tasksByStatus`, which is now filtered — no other change needed.)

- [ ] **Step 8: Type-check**

Run: `npm run check`
Expected: no new errors in BoardView/ListView/FilterBar/store.

- [ ] **Step 9: Commit**

```bash
git add src/lib/components/workos/lib/store.ts src/lib/components/workos/lib/store.test.ts src/lib/components/workos/chrome/FilterBar.svelte src/lib/components/workos/views/BoardView.svelte src/lib/components/workos/views/ListView.svelte
git commit -m "feat(workos): shared filter+search bar on board & list (Phase 3a)"
```

---

## Task 8: MyWorkView (segment + buckets + FilterBar)

**Files:**
- Modify: `src/lib/components/workos/lib/types.ts` (add `MyWorkSegment`)
- Create: `src/lib/components/workos/views/MyWorkView.svelte`

**Interfaces:**
- Consumes: `myTasks`, `myWorkFilter`, `loadMyWork`, `teardownMyWork`, `openTask`, `displayName`, `initials` (store); `applyFilters` (Task 2); `bucketByDueDate`, `BUCKET_ORDER`, `BUCKET_LABEL` (Task 3); `FilterBar` (Task 7); `user` store; `STATUS_LABEL`.
- Produces: `MyWorkSegment = 'all' | 'assigned' | 'created'`; `MyWorkView.svelte`.

- [ ] **Step 1: Add the segment type**

In `src/lib/components/workos/lib/types.ts`, after `DueBuckets`, add:

```typescript
export type MyWorkSegment = 'all' | 'assigned' | 'created';
```

- [ ] **Step 2: Create MyWorkView.svelte**

Create `src/lib/components/workos/views/MyWorkView.svelte`:

```svelte
<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { user } from '$lib/stores';
	import FilterBar from '../chrome/FilterBar.svelte';
	import Icon from '../ui/Icon.svelte';
	import { STATUS_LABEL, type Task, type MyWorkSegment } from '../lib/types';
	import { applyFilters } from '../lib/filters';
	import { bucketByDueDate, BUCKET_ORDER, BUCKET_LABEL } from '../lib/buckets';
	import { myTasks, myWorkFilter, loadMyWork, teardownMyWork, openTask, displayName, initials } from '../lib/store';

	let segment: MyWorkSegment = 'all';
	const SEGMENTS: { k: MyWorkSegment; label: string }[] = [
		{ k: 'all', label: 'All' }, { k: 'assigned', label: 'Assigned' }, { k: 'created', label: 'Created' }
	];

	onMount(() => { void loadMyWork(); });
	onDestroy(() => teardownMyWork());

	$: uid = $user?.id ?? '';
	function inSegment(t: Task): boolean {
		if (segment === 'assigned') return (t.assignee_ids ?? []).includes(uid);
		if (segment === 'created') return t.created_by_id === uid;
		return true;
	}
	// My Work shows open work; the Status facet can re-include done/canceled.
	$: statusFilterActive = $myWorkFilter.statuses.length > 0;
	$: visible = applyFilters(
		$myTasks.filter((t) => inSegment(t) && (statusFilterActive || (t.status !== 'done' && t.status !== 'canceled'))),
		$myWorkFilter
	);
	$: buckets = bucketByDueDate(visible, Date.now());
	const fmt = (ms: number | null | undefined) => (ms == null ? '' : new Date(ms).toLocaleDateString());
</script>

<div class="h-full flex flex-col min-h-0">
	<div class="flex-none flex items-center gap-2 px-4 pt-4">
		<h1 class="text-lg font-semibold">My Work</h1>
		<div class="flex-1"></div>
		<div class="inline-flex rounded-lg border border-gray-200 dark:border-gray-800 p-0.5 text-xs">
			{#each SEGMENTS as s (s.k)}
				<button class="px-3 py-1 rounded-md" class:bg-accent={segment === s.k} onclick={() => (segment = s.k)}>{s.label}</button>
			{/each}
		</div>
	</div>
	<FilterBar filter={myWorkFilter} showAssignee={false} />

	<div class="flex-1 overflow-auto p-4 bg-white dark:bg-gray-950">
		{#if !visible.length}
			<div class="h-full flex flex-col items-center justify-center gap-2 text-center text-gray-400">
				<Icon name="check" size={28} />
				<div class="text-sm">Nothing on your plate yet</div>
			</div>
		{:else}
			{#each BUCKET_ORDER as bucket (bucket)}
				{#if buckets[bucket].length}
					<div class="mb-5">
						<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-2">{BUCKET_LABEL[bucket]} · {buckets[bucket].length}</div>
						<div class="flex flex-col divide-y divide-gray-100 dark:divide-gray-900 rounded-lg border border-gray-200 dark:border-gray-800">
							{#each buckets[bucket] as t (t.id)}
								<button class="flex items-center gap-3 px-3 py-2 text-left hover:bg-gray-50 dark:hover:bg-gray-900" onclick={() => openTask(t.id)}>
									<span class="text-[11px] text-gray-400 w-16 flex-none">{t.key}</span>
									<span class="flex-1 truncate text-sm">{t.title}</span>
									<span class="text-[11px] text-gray-400">{STATUS_LABEL[t.status]}</span>
									{#if t.due_date}<span class="text-[11px] text-gray-400 w-24 text-right">{fmt(t.due_date)}</span>{/if}
									<span class="flex -space-x-1.5">
										{#each (t.assignee_ids ?? []).slice(0, 3) as a (a)}
											<span class="w-6 h-6 rounded-full bg-gray-200 dark:bg-gray-700 text-[10px] flex items-center justify-center border border-white dark:border-gray-950" title={displayName(a)}>{initials(a)}</span>
										{/each}
									</span>
								</button>
							{/each}
						</div>
					</div>
				{/if}
			{/each}
		{/if}
	</div>
</div>
```

- [ ] **Step 3: Type-check**

Run: `npm run check`
Expected: no new errors in MyWorkView/types.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/lib/types.ts src/lib/components/workos/views/MyWorkView.svelte
git commit -m "feat(workos): My Work view with segment + due-date buckets (Phase 3a)"
```

---

## Task 9: Wire navigation — sidebar entry, route, default landing

**Files:**
- Modify: `src/lib/components/workos/lib/store.ts` (`ViewKey` + default)
- Modify: `src/lib/components/workos/WorkOSApp.svelte` (route `'mywork'`)
- Modify: `src/lib/components/workos/chrome/Sidebar.svelte` (My Work entry)

**Interfaces:**
- Consumes: `view` store, `MyWorkView` component.
- Produces: `'mywork'` is a valid `ViewKey` and the default landing view.

- [ ] **Step 1: Extend `ViewKey` and change the default**

In `store.ts` line 14, change:

```typescript
export type ViewKey = 'board' | 'list' | 'admin' | 'inbox' | 'mywork';
```

In `store.ts` line 32, change the default:

```typescript
export const view: Writable<ViewKey> = writable('mywork');
```

- [ ] **Step 2: Route the view in WorkOSApp**

In `src/lib/components/workos/WorkOSApp.svelte`, add the import (after the `InboxView` import, line 10):

```svelte
	import MyWorkView from './views/MyWorkView.svelte';
```

Add a branch in the view switch. After the `{:else if $view === 'inbox'}` block (lines 38–39) add:

```svelte
				{:else if $view === 'mywork'}
					<MyWorkView />
```

Note: My Work renders regardless of `$teams.length` (it is cross-team and has its own empty state), so place this branch **before** the `{:else if !$teams.length}` guard.

- [ ] **Step 3: Add the sidebar entry**

In `src/lib/components/workos/chrome/Sidebar.svelte`, add a "My Work" button at the very top of the `<aside>`, above the team switcher `<div class="p-2.5 relative">` (line 21). Insert:

```svelte
	<div class="p-2.5 pb-0">
		<button
			class="flex items-center gap-2 w-full h-9 px-2 rounded-lg text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-900"
			class:bg-accent={$view === 'mywork'}
			onclick={() => view.set('mywork')}
		>
			<Icon name="check" size={15} />
			<span class="flex-1 text-left">My Work</span>
		</button>
	</div>
```

(`view` is already imported in Sidebar at line 8.)

- [ ] **Step 4: Type-check**

Run: `npm run check`
Expected: no new errors.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/store.ts src/lib/components/workos/WorkOSApp.svelte src/lib/components/workos/chrome/Sidebar.svelte
git commit -m "feat(workos): My Work navigation + default landing (Phase 3a)"
```

---

## Task 10: Sidebar realtime carry-over (nav reconciler + team-room subscription)

**Files:**
- Modify: `src/lib/components/workos/lib/store.ts` (`applyNavEvent`, NAV_EVENTS, team-room subscription)
- Modify: `src/lib/components/workos/lib/store.test.ts` (nav reconcile tests)

**Interfaces:**
- Consumes: `workspaces`, `workstreams`, `teams` stores; `enterRoom`/`teamKey` (Task 5).
- Produces: `applyNavEvent(event: string, payload: any): void`; team-room subscriptions established in `connectRealtime`.

- [ ] **Step 1: Write the failing tests**

Append to `src/lib/components/workos/lib/store.test.ts`:

```typescript
import { workspaces, workstreams, applyNavEvent } from './store';

const mkWs = (over: any) => ({ id: 'ws1', team_id: 'tm', name: 'Eng', visibility: 'team', archived: false, created_at: 0, updated_at: 0, ...over });
const mkSt = (over: any) => ({ id: 's1', workspace_id: 'ws1', name: 'Plat', archived: false, created_at: 0, updated_at: 0, ...over });

describe('nav reconcile (sidebar carry-over)', () => {
	beforeEach(() => { workspaces.set([]); workstreams.set([]); });

	it('adds a team-visible workspace on workspace.created', () => {
		applyNavEvent('workos:workspace.created', mkWs({ id: 'a', visibility: 'team' }));
		expect(get(workspaces).map((w) => w.id)).toEqual(['a']);
	});
	it('ignores a restricted workspace on workspace.created (§5 client guard)', () => {
		applyNavEvent('workos:workspace.created', mkWs({ id: 'b', visibility: 'restricted' }));
		expect(get(workspaces)).toHaveLength(0);
	});
	it('removes a workspace on workspace.deleted', () => {
		workspaces.set([mkWs({ id: 'a' })]);
		applyNavEvent('workos:workspace.deleted', { id: 'a' });
		expect(get(workspaces)).toHaveLength(0);
	});
	it('adds a workstream only when its workspace is visible', () => {
		applyNavEvent('workos:workstream.created', mkSt({ id: 's9', workspace_id: 'ghost' }));
		expect(get(workstreams)).toHaveLength(0); // unknown workspace -> ignored
		workspaces.set([mkWs({ id: 'ws1' })]);
		applyNavEvent('workos:workstream.created', mkSt({ id: 's9', workspace_id: 'ws1' }));
		expect(get(workstreams).map((s) => s.id)).toEqual(['s9']);
	});
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run src/lib/components/workos/lib/store.test.ts`
Expected: FAIL — `applyNavEvent` not exported.

- [ ] **Step 3: Implement `applyNavEvent`**

In `store.ts`, after `applyTaskEvent` (line 367), add:

```typescript
/** Reconcile a workspace/workstream nav event into the sidebar tree.
 * §5 client-side guard: never reveal a restricted workspace from the team-wide room,
 * and only accept a workstream whose parent workspace is already visible. */
export function applyNavEvent(event: string, payload: any): void {
	if (!payload || !payload.id) return;
	if (event === 'workos:workspace.created' || event === 'workos:workspace.updated') {
		workspaces.update((l) => {
			const exists = l.some((w) => w.id === payload.id);
			if (payload.visibility === 'restricted') return exists ? l.map((w) => (w.id === payload.id ? payload : w)) : l;
			return exists ? l.map((w) => (w.id === payload.id ? payload : w)) : [...l, payload];
		});
	} else if (event === 'workos:workspace.deleted') {
		workspaces.update((l) => l.filter((w) => w.id !== payload.id));
		workstreams.update((l) => l.filter((s) => s.workspace_id !== payload.id));
	} else if (event === 'workos:workstream.created' || event === 'workos:workstream.updated') {
		workstreams.update((l) => {
			if (!get(workspaces).some((w) => w.id === payload.workspace_id)) return l;
			const exists = l.some((s) => s.id === payload.id);
			return exists ? l.map((s) => (s.id === payload.id ? payload : s)) : [...l, payload];
		});
	} else if (event === 'workos:workstream.deleted') {
		workstreams.update((l) => l.filter((s) => s.id !== payload.id));
	}
}
```

- [ ] **Step 4: Wire NAV_EVENTS + team-room subscription into the socket**

In `store.ts`, add the event list next to `TASK_EVENTS` (line 371):

```typescript
const NAV_EVENTS = [
	'workos:workspace.created', 'workos:workspace.updated', 'workos:workspace.deleted',
	'workos:workstream.created', 'workos:workstream.updated', 'workos:workstream.deleted'
];
```

In `connectRealtime`, after the COLLAB_EVENTS loop (lines 400–403), add:

```typescript
	for (const ev of NAV_EVENTS) {
		handlers[ev] = (payload: any) => applyNavEvent(ev, payload);
		s.on(ev, handlers[ev]);
	}
	// Subscribe to every team room so workspace/workstream nav events arrive live.
	for (const t of get(teams)) enterRoom(teamKey(t.id));
```

In `disconnectRealtime`, add `NAV_EVENTS` to the off-loop (line 423):

```typescript
	for (const ev of [...TASK_EVENTS, ...COLLAB_EVENTS, ...NAV_EVENTS, 'workos:notification.created', 'connect']) {
		if (handlers[ev]) s.off(ev, handlers[ev]);
	}
```

- [ ] **Step 5: Run tests to verify pass**

Run: `npx vitest run src/lib/components/workos/lib/store.test.ts`
Expected: PASS (existing + 4 new nav tests).

- [ ] **Step 6: Full type-check + full WorkOS suites**

Run: `npm run check`
Expected: no new errors in the WorkOS tree.
Run: `npx vitest run src/lib/components/workos/`
Expected: PASS (all WorkOS frontend tests).
Run: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/ -q`
Expected: PASS (all WorkOS backend tests, including the new `/me/tasks` module).

- [ ] **Step 7: Commit**

```bash
git add src/lib/components/workos/lib/store.ts src/lib/components/workos/lib/store.test.ts
git commit -m "feat(workos): live sidebar nav carry-over with §5 client guard (Phase 3a)"
```

---

## Final verification

- [ ] Run the full WorkOS backend suite: `cd backend && .venv/Scripts/python -m pytest open_webui/test/workos/ -q` → all pass.
- [ ] Run the full WorkOS frontend suite: `npx vitest run src/lib/components/workos/` → all pass.
- [ ] Run `npm run check` → no new errors in the WorkOS tree.
- [ ] **Manual browser smoke is DEFERRED** (consistent with prior WorkOS phases and the "ask before starting Vite" rule): My Work landing + empty state, segment toggle, due-date buckets, filter facets + search on board/list/My Work, live sidebar update when a workspace/workstream is created in another session, live My Work update on assignment. Flag these to the user as pending manual verification.

## Notes for the implementer

- **`Date.now()` in MyWorkView** is intentional (live "now" for bucketing in the browser); `bucketByDueDate` takes `now` as a parameter precisely so the pure tests stay deterministic. Do not inject a fixed clock into the component.
- **Icon glyphs:** `FilterBar` uses `search`/`chevron-down` and `MyWorkView`/`Sidebar` use `check`. If any is missing from `ui/Icon.svelte`, either add it following the existing glyph pattern or substitute an existing glyph — do not invent a name that isn't registered (it renders blank).
- **Do not clear `myTasks` in `teardownMyWork`** — keeping the last list avoids an empty flash on re-entry; `loadMyWork` refetches. Live reconciliation is gated by `myWorkActive`, so the list does not grow while My Work is closed.
- **`/me/tasks` performance** is candidate-by-team + Python filter — fine for current scale; a denormalized assignee index is the documented future optimization if task volume grows (see spec §4.2 / §10).
