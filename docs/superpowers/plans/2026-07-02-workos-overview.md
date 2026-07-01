# WorkOS Workstream Overview Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the workstream-level Overview tab (ink-dark KPI hero + LayerChart momentum + distribution + team table + attention list + activity pulse) per the approved spec `docs/superpowers/specs/2026-07-02-workos-overview-design.md`, with every metric precisely defined and unit-tested.

**Architecture:** All metrics are pure functions in a new `lib/overview.ts` computed client-side from the already-loaded `tasks` store (so Overview matches Board/List and updates live via existing task socket events). One new backend endpoint supplies workstream activity (pulse + daily histogram). Presentational Svelte components receive precomputed props from `OverviewView.svelte`. Two small shared correctness fixes (taskHealth overdue boundary, `completed_at` transition-only stamping) land first because the metrics depend on them.

**Tech Stack:** Svelte 5 (runes-era syntax w/ `onclick`), Tailwind 4, shadcn-svelte + LayerChart (`chart` component), vitest, FastAPI + SQLAlchemy async, pytest-asyncio.

## Global Constraints

- Branch: `osool`. The working tree has PRE-EXISTING uncommitted changes NOT owned by this plan: `src/lib/components/workos/chrome/Topbar.svelte` (modified) and two deleted `backend/open_webui/static/workos-logo-*.png`. NEVER stage the deleted PNGs. Topbar.svelte must be edited on top of its current working-tree state (Task 9); its commit will include the pre-existing edits — say so in the commit body.
- `git add` explicit paths only. Never `git add -A` / `git add .`.
- Do NOT run prettier on workos files (repo convention: compact one-liners; prettier reflows them into noise).
- Status/priority colors come ONLY from `src/lib/components/workos/lib/colors.ts` in card bodies. The ink hero uses its own local hex constants (deliberate; both themes).
- Do NOT reference `MyWorkView.svelte` for styling (user explicitly rejected it). The approved mockup (spec header) is the visual reference.
- UI copy: sentence case, no Title Case, no exclamation marks.
- Frontend unit tests: `npx vitest run <file>` (from repo root). Type check: `npm run check` (slow; run where a step says so). Expected: no NEW errors in workos files.
- Backend tests: `cd backend; .venv/Scripts/python.exe -m pytest open_webui/test/workos -q` (PowerShell; the venv lives at `backend/.venv`).
- Commit after every task, message per step, ending with:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- Timestamps in the data model are **epoch milliseconds**. `due_date`/`start_date` are stored as **UTC midnight** of the picked calendar date.
- `STATUS_ORDER` (types.ts) = `['backlog','todo','in_progress','in_review','done']` — excludes `canceled`. Canceled tasks are excluded from every Overview metric.

---

### Task 1: Due-day helpers + `taskHealth` overdue boundary fix

**Files:**
- Modify: `src/lib/components/workos/lib/progress.ts`
- Test: `src/lib/components/workos/lib/progress.test.ts` (append; adjust any existing test that encodes the old boundary)

**Interfaces:**
- Consumes: nothing new.
- Produces (used by Tasks 3–5, 10–14):
  - `dueDayStartLocal(ts: number): number` — local 00:00.000 of the UTC-date of `ts`
  - `dueDayEndLocal(ts: number): number` — local 23:59:59.999 of the UTC-date of `ts`
  - `taskHealth(task, now)` unchanged signature; overdue now means `now > dueDayEndLocal(due_date)`

- [ ] **Step 1: Write the failing tests**

Append to `src/lib/components/workos/lib/progress.test.ts` (follow the file's existing import style):

```ts
describe('due-day helpers', () => {
	// Due dates are stored as UTC midnight of the picked date (DueDateCell parses 'YYYY-MM-DD').
	const dueJun15 = Date.UTC(2026, 5, 15); // 2026-06-15T00:00Z

	it('dueDayStartLocal maps the UTC date to local midnight', () => {
		expect(dueDayStartLocal(dueJun15)).toBe(new Date(2026, 5, 15).getTime());
	});

	it('dueDayEndLocal maps the UTC date to local 23:59:59.999', () => {
		expect(dueDayEndLocal(dueJun15)).toBe(new Date(2026, 5, 15, 23, 59, 59, 999).getTime());
	});
});

describe('taskHealth overdue boundary (due day counts as not-overdue)', () => {
	const dueJun15 = Date.UTC(2026, 5, 15);
	const base = { status: 'todo', progress: 0, labels: [], assignee_ids: [] } as any;

	it('is not overdue during the due day', () => {
		const now = new Date(2026, 5, 15, 9, 0).getTime();
		expect(taskHealth({ ...base, due_date: dueJun15, start_date: null }, now)).not.toBe('overdue');
	});

	it('is overdue one ms after the due day ends', () => {
		const now = new Date(2026, 5, 15, 23, 59, 59, 999).getTime() + 1;
		expect(taskHealth({ ...base, due_date: dueJun15, start_date: null }, now)).toBe('overdue');
	});
});
```

Add `dueDayStartLocal, dueDayEndLocal` to the existing `progress` import in the test file.

- [ ] **Step 2: Run tests to verify they fail**

Run: `npx vitest run src/lib/components/workos/lib/progress.test.ts`
Expected: FAIL — `dueDayStartLocal is not defined` (and the boundary test fails against the old rule).

- [ ] **Step 3: Implement**

In `src/lib/components/workos/lib/progress.ts`, add above `taskHealth`:

```ts
// due_date/start_date are stored as UTC midnight of the picked calendar date
// (DueDateCell parses 'YYYY-MM-DD' → UTC). The calendar date is the timestamp's
// UTC Y/M/D; deadlines are experienced in the viewer's local time.
export function dueDayStartLocal(ts: number): number {
	const d = new Date(ts);
	return new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()).getTime();
}

export function dueDayEndLocal(ts: number): number {
	const d = new Date(ts);
	return new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), 23, 59, 59, 999).getTime();
}
```

In `taskHealth`, replace the overdue line:

```ts
	if (task.due_date != null && now > task.due_date) return 'overdue';
```

with:

```ts
	if (task.due_date != null && now > dueDayEndLocal(task.due_date)) return 'overdue';
```

(Keep the explanatory comment above it; update its wording: overdue means the due *day* has fully ended locally.)

- [ ] **Step 4: Run the full progress suite; fix any test that asserted the old boundary**

Run: `npx vitest run src/lib/components/workos/lib/progress.test.ts`
Expected: PASS. If an existing case fails, it encodes the old (buggy) boundary — update that case's `now` to be past `dueDayEndLocal` and keep its intent.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/progress.ts src/lib/components/workos/lib/progress.test.ts
git commit -m "fix(workos): overdue starts after the due day ends locally

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `completed_at` stamps only on a status transition (backend)

**Files:**
- Modify: `backend/open_webui/models/workos.py` (TasksDao `update_fields`, ~lines 700–715)
- Test: `backend/open_webui/test/workos/test_models_task.py` (append)

**Interfaces:**
- Consumes: existing `Tasks.update_fields(id, fields, db=None)`.
- Produces: same signature; behavior change only — re-saving `status='done'` on an already-done task no longer re-stamps `completed_at`. Transition out of `done` still clears it.

- [ ] **Step 1: Write the failing tests**

Append to `backend/open_webui/test/workos/test_models_task.py` (mirror the file's existing fixtures/imports for creating a task; it already tests `Tasks`):

```python
@pytest.mark.asyncio
async def test_completed_at_not_restamped_on_done_resave():
    t = await Tasks.insert('ws1', 'team1', 1, 'T', 'Task', status='todo', created_by_id='u1')
    done1 = await Tasks.update_fields(t.id, {'status': 'done'})
    assert done1.completed_at is not None
    import asyncio
    await asyncio.sleep(0.002)  # ensure a later _now() would differ
    done2 = await Tasks.update_fields(t.id, {'status': 'done', 'title': 'Renamed'})
    assert done2.completed_at == done1.completed_at


@pytest.mark.asyncio
async def test_completed_at_cleared_on_reopen_and_restamped_on_redone():
    t = await Tasks.insert('ws1', 'team1', 2, 'T', 'Task', status='todo', created_by_id='u1')
    done = await Tasks.update_fields(t.id, {'status': 'done'})
    reopened = await Tasks.update_fields(t.id, {'status': 'in_progress'})
    assert reopened.completed_at is None
    redone = await Tasks.update_fields(t.id, {'status': 'done'})
    assert redone.completed_at is not None and redone.completed_at >= done.completed_at
```

Adjust the `Tasks.insert(...)` call to match the exact signature used elsewhere in this test file (read it first; the DAO signature is `insert(workstream_id, team_id, number, team_key, title, ...)` — copy an existing call).

- [ ] **Step 2: Run to verify the first test fails**

Run: `cd backend; .venv/Scripts/python.exe -m pytest open_webui/test/workos/test_models_task.py -q`
Expected: the re-save test FAILS (completed_at changes today); the reopen test may already pass.

- [ ] **Step 3: Implement**

In `backend/open_webui/models/workos.py` `update_fields`, capture the prior status before the setattr loop and gate the stamp on an actual transition. Replace:

```python
            for k, v in fields.items():
                setattr(row, k, v)
            if 'status' in fields:
                row.completed_at = _now() if fields['status'] == 'done' else None
```

with:

```python
            prev_status = row.status
            for k, v in fields.items():
                setattr(row, k, v)
            if 'status' in fields and fields['status'] != prev_status:
                # Stamp only on a real transition; a no-op re-save of 'done' must not
                # shift completion history (feeds the Overview momentum chart).
                row.completed_at = _now() if fields['status'] == 'done' else None
```

- [ ] **Step 4: Run the backend workos suite**

Run: `cd backend; .venv/Scripts/python.exe -m pytest open_webui/test/workos -q`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add backend/open_webui/models/workos.py backend/open_webui/test/workos/test_models_task.py
git commit -m "fix(workos): stamp completed_at only on status transitions

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: `lib/overview.ts` — day helpers + KPI metrics (TDD)

**Files:**
- Create: `src/lib/components/workos/lib/overview.ts`
- Create: `src/lib/components/workos/lib/overview.test.ts`

**Interfaces:**
- Consumes: `dueDayStartLocal`, `dueDayEndLocal` from `./progress`; `Task` from `./types`.
- Produces (used by Tasks 4, 5, 9, 10):

```ts
export const notCanceled: (t: Task) => boolean;
export const isOpen: (t: Task) => boolean;
export function startOfLocalDay(now: number): number;
export function addLocalDays(dayStart: number, n: number): number; // DST-safe (Date parts, not ms math)
export function isOverdue(t: Pick<Task, 'status' | 'due_date'>, now: number): boolean;
export function daysLate(due: number, now: number): number; // ≥ 1
export function agoLabel(ts: number, now: number): string; // '42s' | '5m' | '3h' | '2d'
export interface OverviewKpis {
	open: number; inProgress: number; inReview: number;
	dueThisWeek: number; dueTomorrow: number;
	overdue: number; oldestOverdueDays: number | null;
	completed7d: number; completedPrev7d: number;
	new7d: number;
}
export function computeKpis(all: Task[], now: number): OverviewKpis;
```

- [ ] **Step 1: Write the failing tests**

Create `src/lib/components/workos/lib/overview.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import type { Task } from './types';
import { computeKpis, isOverdue, daysLate, startOfLocalDay, addLocalDays, agoLabel } from './overview';

// now = local 2026-06-17 (Wednesday) 12:00
const NOW = new Date(2026, 5, 17, 12, 0).getTime();
const dueUtc = (y: number, m: number, d: number) => Date.UTC(y, m, d);

let seq = 0;
function task(over: Partial<Task>): Task {
	seq += 1;
	return {
		id: `t${seq}`, workstream_id: 'ws', team_id: 'tm', number: seq, key: `K-${seq}`,
		title: `Task ${seq}`, status: 'todo', priority: null, assignee_ids: [],
		start_date: null, due_date: null, progress: 0, labels: [], sort_key: seq,
		created_by_id: 'u1', completed_at: null,
		created_at: NOW - 30 * 86_400_000, updated_at: NOW,
		...over
	} as Task;
}

describe('isOverdue / daysLate', () => {
	it('not overdue during the due day, overdue after it ends', () => {
		const dueToday = dueUtc(2026, 5, 17);
		expect(isOverdue(task({ due_date: dueToday }), NOW)).toBe(false);
		const dueYesterday = dueUtc(2026, 5, 16);
		expect(isOverdue(task({ due_date: dueYesterday }), NOW)).toBe(true);
		expect(daysLate(dueYesterday, NOW)).toBe(1);
	});
	it('done/canceled tasks are never overdue', () => {
		const past = dueUtc(2026, 5, 1);
		expect(isOverdue(task({ due_date: past, status: 'done' }), NOW)).toBe(false);
		expect(isOverdue(task({ due_date: past, status: 'canceled' }), NOW)).toBe(false);
	});
});

describe('computeKpis', () => {
	it('counts open/in_progress/in_review and excludes canceled everywhere', () => {
		const k = computeKpis([
			task({ status: 'in_progress' }), task({ status: 'in_review' }),
			task({ status: 'todo' }), task({ status: 'done', completed_at: NOW - 1000 }),
			task({ status: 'canceled' })
		], NOW);
		expect(k.open).toBe(3);
		expect(k.inProgress).toBe(1);
		expect(k.inReview).toBe(1);
	});

	it('dueThisWeek spans today..today+6 local days; dueTomorrow only tomorrow', () => {
		const k = computeKpis([
			task({ due_date: dueUtc(2026, 5, 17) }), // today → in week
			task({ due_date: dueUtc(2026, 5, 18) }), // tomorrow → in week + tomorrow
			task({ due_date: dueUtc(2026, 5, 23) }), // today+6 → in week
			task({ due_date: dueUtc(2026, 5, 24) }), // today+7 → NOT in week
			task({ due_date: dueUtc(2026, 5, 16) })  // yesterday → overdue, not in week
		], NOW);
		expect(k.dueThisWeek).toBe(3);
		expect(k.dueTomorrow).toBe(1);
		expect(k.overdue).toBe(1);
		expect(k.oldestOverdueDays).toBe(1);
	});

	it('completed7d/prev7d use rolling windows over status done + completed_at', () => {
		const k = computeKpis([
			task({ status: 'done', completed_at: NOW - 2 * 86_400_000 }),
			task({ status: 'done', completed_at: NOW - 9 * 86_400_000 }),
			task({ status: 'done', completed_at: NOW - 20 * 86_400_000 }),
			task({ status: 'todo', completed_at: NOW - 1000 }) // not done → never counted
		], NOW);
		expect(k.completed7d).toBe(1);
		expect(k.completedPrev7d).toBe(1);
	});

	it('new7d counts by created_at regardless of status', () => {
		const k = computeKpis([
			task({ created_at: NOW - 3 * 86_400_000, status: 'done', completed_at: NOW - 1000 }),
			task({ created_at: NOW - 8 * 86_400_000 })
		], NOW);
		expect(k.new7d).toBe(1);
	});
});

describe('agoLabel', () => {
	it('formats seconds/minutes/hours/days', () => {
		expect(agoLabel(NOW - 42_000, NOW)).toBe('42s');
		expect(agoLabel(NOW - 5 * 60_000, NOW)).toBe('5m');
		expect(agoLabel(NOW - 3 * 3_600_000, NOW)).toBe('3h');
		expect(agoLabel(NOW - 2 * 86_400_000, NOW)).toBe('2d');
	});
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/lib/components/workos/lib/overview.test.ts`
Expected: FAIL — cannot resolve `./overview`.

- [ ] **Step 3: Implement**

Create `src/lib/components/workos/lib/overview.ts`:

```ts
// Overview page metrics — every number on the Overview derives from a pure
// function here so it can be unit-tested. Spec: docs/superpowers/specs/
// 2026-07-02-workos-overview-design.md §2–§3 (canonical definitions).
import type { Task } from './types';
import { dueDayStartLocal, dueDayEndLocal } from './progress';

const DAY = 86_400_000;

export const notCanceled = (t: Task): boolean => t.status !== 'canceled';
export const isOpen = (t: Task): boolean => t.status !== 'done' && t.status !== 'canceled';

export function startOfLocalDay(now: number): number {
	const d = new Date(now);
	return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

// DST-safe day stepping: goes through Date parts, not ms arithmetic.
export function addLocalDays(dayStart: number, n: number): number {
	const d = new Date(dayStart);
	return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n).getTime();
}

export function isOverdue(t: Pick<Task, 'status' | 'due_date'>, now: number): boolean {
	if (t.status === 'done' || t.status === 'canceled' || t.due_date == null) return false;
	return now > dueDayEndLocal(t.due_date);
}

export function daysLate(due: number, now: number): number {
	return Math.max(1, Math.ceil((now - dueDayEndLocal(due)) / DAY));
}

export function agoLabel(ts: number, now: number): string {
	const s = Math.max(0, Math.floor((now - ts) / 1000));
	if (s < 60) return `${s}s`;
	const m = Math.floor(s / 60);
	if (m < 60) return `${m}m`;
	const h = Math.floor(m / 60);
	if (h < 24) return `${h}h`;
	return `${Math.floor(h / 24)}d`;
}

export interface OverviewKpis {
	open: number; inProgress: number; inReview: number;
	dueThisWeek: number; dueTomorrow: number;
	overdue: number; oldestOverdueDays: number | null;
	completed7d: number; completedPrev7d: number;
	new7d: number;
}

export function computeKpis(all: Task[], now: number): OverviewKpis {
	const w = all.filter(notCanceled);
	const open = w.filter(isOpen);
	const startToday = startOfLocalDay(now);
	const endWindow = addLocalDays(startToday, 7); // exclusive → today + next 6 days
	const startTomorrow = addLocalDays(startToday, 1);
	const startAfterTomorrow = addLocalDays(startToday, 2);

	let dueThisWeek = 0, dueTomorrow = 0, overdue = 0;
	let oldest: number | null = null;
	for (const t of open) {
		if (t.due_date == null) continue;
		if (isOverdue(t, now)) {
			overdue += 1;
			const late = daysLate(t.due_date, now);
			oldest = oldest == null ? late : Math.max(oldest, late);
			continue;
		}
		const day = dueDayStartLocal(t.due_date);
		if (day >= startToday && day < endWindow) dueThisWeek += 1;
		if (day >= startTomorrow && day < startAfterTomorrow) dueTomorrow += 1;
	}

	const doneIn = (a: number, b: number): number =>
		w.filter((t) => t.status === 'done' && t.completed_at != null && t.completed_at > a && t.completed_at <= b).length;

	return {
		open: open.length,
		inProgress: open.filter((t) => t.status === 'in_progress').length,
		inReview: open.filter((t) => t.status === 'in_review').length,
		dueThisWeek, dueTomorrow, overdue, oldestOverdueDays: oldest,
		completed7d: doneIn(now - 7 * DAY, now),
		completedPrev7d: doneIn(now - 14 * DAY, now - 7 * DAY),
		new7d: w.filter((t) => t.created_at > now - 7 * DAY && t.created_at <= now).length
	};
}
```

- [ ] **Step 4: Run to verify pass**

Run: `npx vitest run src/lib/components/workos/lib/overview.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/overview.ts src/lib/components/workos/lib/overview.test.ts
git commit -m "feat(workos): overview KPI metrics as tested pure functions

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: `lib/overview.ts` — weekly momentum + completion time (TDD)

**Files:**
- Modify: `src/lib/components/workos/lib/overview.ts`
- Test: `src/lib/components/workos/lib/overview.test.ts` (append)

**Interfaces:**
- Consumes: Task 3 helpers.
- Produces (used by Tasks 9, 11):

```ts
export function localWeekStart(now: number): number; // Monday 00:00 local of now's week
export interface WeekBin { start: number; end: number; label: string; created: number; completed: number; current: boolean }
export function weeklyMomentum(all: Task[], now: number, weeks: number): WeekBin[]; // oldest → newest, length == weeks
export interface CompletionTime { avgDays: number | null; prevAvgDays: number | null }
export function completionTime(all: Task[], now: number, weeks: number): CompletionTime;
```

- [ ] **Step 1: Write the failing tests**

Append to `overview.test.ts` (extend the import from `./overview` with `localWeekStart, weeklyMomentum, completionTime`):

```ts
describe('weeklyMomentum', () => {
	// NOW is Wednesday 2026-06-17; its Monday is 2026-06-15 local.
	it('localWeekStart returns the local Monday', () => {
		expect(localWeekStart(NOW)).toBe(new Date(2026, 5, 15).getTime());
		// Sunday belongs to the week started the previous Monday
		expect(localWeekStart(new Date(2026, 5, 21, 10, 0).getTime())).toBe(new Date(2026, 5, 15).getTime());
	});

	it('bins created and completed into local Monday-start weeks, oldest first', () => {
		const mon = new Date(2026, 5, 15).getTime();
		const prevMon = new Date(2026, 5, 8).getTime();
		const bins = weeklyMomentum([
			task({ created_at: mon + 3_600_000 }),                                        // this week: created
			task({ created_at: prevMon + 3_600_000 }),                                    // last week: created
			task({ created_at: prevMon + 1, status: 'done', completed_at: mon + 1000 }),  // created last wk, done this wk
			task({ status: 'canceled', created_at: mon + 1 })                             // excluded
		], NOW, 2);
		expect(bins).toHaveLength(2);
		expect(bins[0].start).toBe(prevMon);
		expect(bins[0].created).toBe(2);
		expect(bins[0].completed).toBe(0);
		expect(bins[1].created).toBe(1);
		expect(bins[1].completed).toBe(1);
		expect(bins[1].current).toBe(true);
		expect(bins[0].current).toBe(false);
	});
});

describe('completionTime', () => {
	it('averages created→completed over the calendar window, 1 decimal, null when empty', () => {
		const windowStart = new Date(2026, 5, 15 - 7 * 5).getTime(); // 6-week window start
		const ct = completionTime([
			task({ status: 'done', created_at: NOW - 5 * 86_400_000, completed_at: NOW - 86_400_000 }),   // 4d
			task({ status: 'done', created_at: NOW - 3 * 86_400_000, completed_at: NOW - 86_400_000 }),   // 2d
			task({ status: 'done', created_at: windowStart - 20 * 86_400_000, completed_at: windowStart - 10 * 86_400_000 }) // prev window: 10d
		], NOW, 6);
		expect(ct.avgDays).toBe(3);
		expect(ct.prevAvgDays).toBe(10);
		expect(completionTime([], NOW, 6)).toEqual({ avgDays: null, prevAvgDays: null });
	});
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/lib/components/workos/lib/overview.test.ts`
Expected: FAIL — `localWeekStart is not defined`.

- [ ] **Step 3: Implement**

Append to `overview.ts`:

```ts
export function localWeekStart(now: number): number {
	const d = new Date(now);
	const dow = (d.getDay() + 6) % 7; // Monday = 0
	return new Date(d.getFullYear(), d.getMonth(), d.getDate() - dow).getTime();
}

export interface WeekBin {
	start: number; end: number; label: string;
	created: number; completed: number; current: boolean;
}

export function weeklyMomentum(all: Task[], now: number, weeks: number): WeekBin[] {
	const w = all.filter(notCanceled);
	const thisWeek = localWeekStart(now);
	const bins: WeekBin[] = [];
	for (let i = weeks - 1; i >= 0; i--) {
		const start = addLocalDays(thisWeek, -7 * i);
		const end = addLocalDays(start, 7);
		bins.push({
			start, end,
			label: new Date(start).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
			created: w.filter((t) => t.created_at >= start && t.created_at < end).length,
			completed: w.filter(
				(t) => t.status === 'done' && t.completed_at != null && t.completed_at >= start && t.completed_at < end
			).length,
			current: i === 0
		});
	}
	return bins;
}

export interface CompletionTime { avgDays: number | null; prevAvgDays: number | null }

// Average created→completed lead time over the chart's calendar window
// (labelled "avg completion time" in the UI — we do not measure in_progress→done).
export function completionTime(all: Task[], now: number, weeks: number): CompletionTime {
	const w = all.filter(notCanceled);
	const start = addLocalDays(localWeekStart(now), -7 * (weeks - 1));
	const prevStart = addLocalDays(start, -7 * weeks);
	const avg = (a: number, b: number): number | null => {
		const xs = w
			.filter((t) => t.status === 'done' && t.completed_at != null && t.completed_at >= a && t.completed_at < b)
			.map((t) => (t.completed_at as number) - t.created_at);
		if (!xs.length) return null;
		return Math.round((xs.reduce((s, x) => s + x, 0) / xs.length / DAY) * 10) / 10;
	};
	return { avgDays: avg(start, now + 1), prevAvgDays: avg(prevStart, start) };
}
```

- [ ] **Step 4: Run to verify pass**

Run: `npx vitest run src/lib/components/workos/lib/overview.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/overview.ts src/lib/components/workos/lib/overview.test.ts
git commit -m "feat(workos): overview momentum bins + completion-time metric

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: `lib/overview.ts` — distribution, team rows, attention list (TDD)

**Files:**
- Modify: `src/lib/components/workos/lib/overview.ts`
- Test: `src/lib/components/workos/lib/overview.test.ts` (append)

**Interfaces:**
- Consumes: Task 3 helpers; `taskHealth`, `plannedProgress`, `actualProgress` from `./progress`; `PRIORITY_ORDER`, `STATUS_ORDER` from `./types`.
- Produces (used by Tasks 9, 12, 13, 14):

```ts
export interface PriorityPair { key: TaskPriority | 'none'; label: string; n: number }
export function priorityPairs(all: Task[]): PriorityPair[]; // over OPEN; 'None' only when > 0; sums to |OPEN|
export interface StatusSlice { status: TaskStatus; n: number; pct: number }
export function statusMix(all: Task[]): { total: number; slices: StatusSlice[] }; // over non-canceled, STATUS_ORDER order
export type MemberHealth = 'needs_support' | 'watch' | 'on_track';
export interface TeamRow {
	userId: string | null; open: number; inProgress: number; inReview: number;
	overdue: number; load: number; health: MemberHealth | null;
}
export function teamRows(all: Task[], now: number, nameOf: (id: string) => string): TeamRow[];
export type AttentionClass = 'overdue' | 'behind' | 'at_risk' | 'due_soon';
export interface AttentionItem {
	task: Task; cls: AttentionClass;
	daysLate: number | null; gap: number | null; dueLabel: 'today' | 'tomorrow' | null;
}
export function attentionList(all: Task[], now: number): AttentionItem[];
```

- [ ] **Step 1: Write the failing tests**

Append to `overview.test.ts` (extend imports accordingly):

```ts
describe('priorityPairs / statusMix', () => {
	it('priority pairs cover OPEN and sum to open count; None only when present', () => {
		const list = [
			task({ priority: 'urgent' }), task({ priority: 'high' }), task({ priority: null }),
			task({ priority: 'urgent', status: 'done', completed_at: NOW })
		];
		const pairs = priorityPairs(list);
		expect(pairs.map((p) => p.key)).toEqual(['urgent', 'high', 'medium', 'low', 'none']);
		expect(pairs.reduce((s, p) => s + p.n, 0)).toBe(3);
		expect(priorityPairs([task({ priority: 'low' })]).some((p) => p.key === 'none')).toBe(false);
	});

	it('statusMix covers non-canceled tasks in STATUS_ORDER and pct sums to 100', () => {
		const mix = statusMix([
			task({ status: 'todo' }), task({ status: 'in_progress' }),
			task({ status: 'done', completed_at: NOW }), task({ status: 'canceled' })
		]);
		expect(mix.total).toBe(3);
		expect(mix.slices.map((s) => s.status)).toEqual(['backlog', 'todo', 'in_progress', 'in_review', 'done']);
		expect(Math.round(mix.slices.reduce((s, x) => s + x.pct, 0))).toBe(100);
	});
});

describe('teamRows', () => {
	const names: Record<string, string> = { a: 'Amal', b: 'Basel', c: 'Celine' };
	const nameOf = (id: string) => names[id] ?? id;

	it('counts a multi-assignee task fully for each assignee', () => {
		const rows = teamRows([task({ assignee_ids: ['a', 'b'] })], NOW, nameOf);
		expect(rows.filter((r) => r.userId).map((r) => r.open)).toEqual([1, 1]);
	});

	it('load is relative to the busiest member; unassigned row last, capped at 1', () => {
		const rows = teamRows([
			task({ assignee_ids: ['a'] }), task({ assignee_ids: ['a'] }), task({ assignee_ids: ['b'] }),
			task({}), task({}), task({})
		], NOW, nameOf);
		const a = rows.find((r) => r.userId === 'a')!;
		const b = rows.find((r) => r.userId === 'b')!;
		const un = rows[rows.length - 1];
		expect(a.load).toBe(1);
		expect(b.load).toBe(0.5);
		expect(un.userId).toBeNull();
		expect(un.open).toBe(3);
		expect(un.load).toBe(1); // 3/2 capped
		expect(un.health).toBeNull();
	});

	it('health: 2+ overdue/behind → needs_support; exactly 1 → watch; else on_track', () => {
		const overdue1 = task({ assignee_ids: ['a'], due_date: dueUtc(2026, 5, 10) });
		const overdue2 = task({ assignee_ids: ['a'], due_date: dueUtc(2026, 5, 11) });
		const fine = task({ assignee_ids: ['b'] });
		const oneLate = task({ assignee_ids: ['c'], due_date: dueUtc(2026, 5, 10) });
		const rows = teamRows([overdue1, overdue2, fine, oneLate], NOW, nameOf);
		expect(rows.find((r) => r.userId === 'a')!.health).toBe('needs_support');
		expect(rows.find((r) => r.userId === 'b')!.health).toBe('on_track');
		expect(rows.find((r) => r.userId === 'c')!.health).toBe('watch');
	});

	it('sorts by open desc then name', () => {
		const rows = teamRows([
			task({ assignee_ids: ['c'] }), task({ assignee_ids: ['b'] }), task({ assignee_ids: ['b'] }),
			task({ assignee_ids: ['a'] })
		], NOW, nameOf);
		expect(rows.map((r) => r.userId)).toEqual(['b', 'a', 'c']);
	});
});

describe('attentionList', () => {
	it('classifies once per task with severity ordering: overdue, behind, at_risk, due_soon', () => {
		const overdue = task({ due_date: dueUtc(2026, 5, 14) });
		const overdueWorse = task({ due_date: dueUtc(2026, 5, 10) });
		// behind: planned far ahead of actual (started 20d ago, due in 10d, 0% done → gap ≥ 25)
		const behind = task({ start_date: dueUtc(2026, 4, 28), due_date: dueUtc(2026, 5, 27), progress: 0 });
		// at risk: gap in [10, 25)
		const atRisk = task({ start_date: dueUtc(2026, 5, 7), due_date: dueUtc(2026, 6, 17), progress: 10 });
		const dueToday = task({ due_date: dueUtc(2026, 5, 17), progress: 100 });
		const calm = task({ due_date: dueUtc(2026, 6, 30) });
		const items = attentionList([calm, dueToday, atRisk, behind, overdue, overdueWorse], NOW);
		expect(items.map((i) => i.cls)).toEqual(['overdue', 'overdue', 'behind', 'at_risk', 'due_soon']);
		expect(items[0].task.id).toBe(overdueWorse.id); // most late first
		expect(items[0].daysLate).toBe(7);
		expect(items[4].dueLabel).toBe('today');
		expect(items.some((i) => i.task.id === calm.id)).toBe(false);
	});
});
```

Note for the `at_risk` fixture: verify the arithmetic before finalizing — `plannedProgress` from 2026-06-07 to 2026-07-17 at NOW (2026-06-17) ≈ 25%, actual 10 → gap ≈ 15 → `at_risk`. If the computed health differs, adjust `progress` (not the dates) until `taskHealth` returns `at_risk`, keeping the test's intent.

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/lib/components/workos/lib/overview.test.ts`
Expected: FAIL — `priorityPairs is not defined`.

- [ ] **Step 3: Implement**

Append to `overview.ts` (extend the imports at top: `import { dueDayStartLocal, dueDayEndLocal, taskHealth, plannedProgress, actualProgress } from './progress';` and `import { PRIORITY_ORDER, STATUS_ORDER } from './types';` plus types `TaskPriority, TaskStatus`):

```ts
export interface PriorityPair { key: TaskPriority | 'none'; label: string; n: number }

export function priorityPairs(all: Task[]): PriorityPair[] {
	const open = all.filter(isOpen);
	const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
	const pairs: PriorityPair[] = PRIORITY_ORDER.map((p) => ({
		key: p, label: cap(p), n: open.filter((t) => t.priority === p).length
	}));
	const none = open.filter((t) => !t.priority).length;
	if (none > 0) pairs.push({ key: 'none', label: 'None', n: none });
	return pairs;
}

export interface StatusSlice { status: TaskStatus; n: number; pct: number }

export function statusMix(all: Task[]): { total: number; slices: StatusSlice[] } {
	const w = all.filter(notCanceled);
	const slices = STATUS_ORDER.map((s) => {
		const n = w.filter((t) => t.status === s).length;
		return { status: s, n, pct: w.length ? (n / w.length) * 100 : 0 };
	});
	return { total: w.length, slices };
}

export type MemberHealth = 'needs_support' | 'watch' | 'on_track';
export interface TeamRow {
	userId: string | null; open: number; inProgress: number; inReview: number;
	overdue: number; load: number; health: MemberHealth | null;
}

// Multi-assignee rule (spec §3.4): a task counts fully for EACH assignee, so
// columns may sum past the global totals. Load is relative to the busiest member.
export function teamRows(all: Task[], now: number, nameOf: (id: string) => string): TeamRow[] {
	const open = all.filter(isOpen);
	const byUser = new Map<string, Task[]>();
	const unassigned: Task[] = [];
	for (const t of open) {
		const ids = t.assignee_ids ?? [];
		if (!ids.length) { unassigned.push(t); continue; }
		for (const id of ids) byUser.set(id, [...(byUser.get(id) ?? []), t]);
	}
	const rows: TeamRow[] = [...byUser.entries()].map(([userId, ts]) => {
		const overdueN = ts.filter((t) => isOverdue(t, now)).length;
		const behind = ts.filter((t) => taskHealth(t, now) === 'behind').length;
		const atRisk = ts.filter((t) => taskHealth(t, now) === 'at_risk').length;
		const riskHigh = overdueN + behind;
		const health: MemberHealth =
			riskHigh >= 2 ? 'needs_support' : riskHigh === 1 || atRisk >= 2 ? 'watch' : 'on_track';
		return {
			userId,
			open: ts.length,
			inProgress: ts.filter((t) => t.status === 'in_progress').length,
			inReview: ts.filter((t) => t.status === 'in_review').length,
			overdue: overdueN, load: 0, health
		};
	});
	rows.sort((a, b) => b.open - a.open || nameOf(a.userId as string).localeCompare(nameOf(b.userId as string)));
	const maxOpen = Math.max(1, ...rows.map((r) => r.open));
	for (const r of rows) r.load = r.open / maxOpen;
	if (unassigned.length) {
		rows.push({
			userId: null, open: unassigned.length, inProgress: 0, inReview: 0,
			overdue: 0, load: Math.min(1, unassigned.length / maxOpen), health: null
		});
	}
	return rows;
}

export type AttentionClass = 'overdue' | 'behind' | 'at_risk' | 'due_soon';
export interface AttentionItem {
	task: Task; cls: AttentionClass;
	daysLate: number | null; gap: number | null; dueLabel: 'today' | 'tomorrow' | null;
}

const CLS_RANK: Record<AttentionClass, number> = { overdue: 0, behind: 1, at_risk: 2, due_soon: 3 };

export function attentionList(all: Task[], now: number): AttentionItem[] {
	const open = all.filter(isOpen);
	const startToday = startOfLocalDay(now);
	const startTomorrow = addLocalDays(startToday, 1);
	const startAfter = addLocalDays(startToday, 2);
	const items: AttentionItem[] = [];
	for (const t of open) {
		if (isOverdue(t, now)) {
			items.push({ task: t, cls: 'overdue', daysLate: daysLate(t.due_date as number, now), gap: null, dueLabel: null });
			continue;
		}
		const h = taskHealth(t, now);
		if (h === 'behind' || h === 'at_risk') {
			const gap = (plannedProgress(t.start_date, t.due_date, now) ?? 0) - actualProgress(t);
			items.push({ task: t, cls: h, daysLate: null, gap, dueLabel: null });
			continue;
		}
		if (t.due_date != null) {
			const day = dueDayStartLocal(t.due_date);
			if (day >= startToday && day < startAfter) {
				items.push({
					task: t, cls: 'due_soon', daysLate: null, gap: null,
					dueLabel: day < startTomorrow ? 'today' : 'tomorrow'
				});
			}
		}
	}
	return items.sort((a, b) => {
		if (CLS_RANK[a.cls] !== CLS_RANK[b.cls]) return CLS_RANK[a.cls] - CLS_RANK[b.cls];
		if (a.cls === 'overdue' || a.cls === 'due_soon') return (a.task.due_date ?? 0) - (b.task.due_date ?? 0);
		return (b.gap ?? 0) - (a.gap ?? 0);
	});
}
```

- [ ] **Step 4: Run to verify pass**

Run: `npx vitest run src/lib/components/workos/lib/overview.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/overview.ts src/lib/components/workos/lib/overview.test.ts
git commit -m "feat(workos): overview distribution, team-row and attention metrics

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Backend — `GET /workstreams/{id}/activity` (TDD)

**Files:**
- Modify: `backend/open_webui/models/workos.py` (append two methods to `ActivityDao`, ~line 939)
- Modify: `backend/open_webui/routers/workos.py` (helper + endpoint near `list_activity`, ~line 1021)
- Create: `backend/open_webui/test/workos/test_router_workstream_activity.py`
- Modify: `docs/superpowers/specs/2026-06-26-workos-access-control.md` (§4 "Comments / activity" table — add the route row)

**Interfaces:**
- Consumes: `WorkosActivity`, `WorkosTask`, `ActivityModel`, `get_async_db_context` (models); `_require_workos`, `require_workstream_visible`, `Activity` singleton (router).
- Produces:
  - DAO: `Activity.list_for_workstream(workstream_id: str, limit: int = 30, db=None) -> list[dict]` (each dict = ActivityModel dump + `task_key`, `task_title`), `Activity.timestamps_for_workstream(workstream_id: str, since_ms: int, db=None) -> list[int]`
  - Router: `_daily_counts(timestamps: list, days: int, tz_offset_minutes: int, now_ms: int) -> list[dict]` (pure), endpoint `GET /workstreams/{workstream_id}/activity?limit=&days=&tz_offset_minutes=` → `{'items': [...], 'daily': [{'day': 'YYYY-MM-DD', 'n': int}]}`

- [ ] **Step 1: Write the failing tests**

Create `backend/open_webui/test/workos/test_router_workstream_activity.py`. First read `backend/open_webui/test/workos/test_router_access_leaks.py` to copy its exact second-user pattern; the code below assumes `U1` is exported from `test_router_teams` (it is — see `test_router_activity_notifications.py`) and mirrors the leak-test's outsider user. Adjust the outsider construction to match that file if it differs:

```python
import pytest

from open_webui.routers.workos import _daily_counts
from open_webui.test.workos.test_router_teams import _client, U1
from open_webui.test.workos.test_router_task import _stream


def test_daily_counts_buckets_by_viewer_local_day():
    # 2026-06-17T22:30Z; viewer at UTC+3 → local day is already 2026-06-18.
    now_ms = 1781735400000
    late_evening_utc = now_ms
    assert _daily_counts([late_evening_utc], days=2, tz_offset_minutes=180, now_ms=now_ms) == [
        {'day': '2026-06-17', 'n': 0},
        {'day': '2026-06-18', 'n': 1},
    ]
    # Same instant for a UTC viewer lands on the 17th.
    assert _daily_counts([late_evening_utc], days=2, tz_offset_minutes=0, now_ms=now_ms) == [
        {'day': '2026-06-16', 'n': 0},
        {'day': '2026-06-17', 'n': 1},
    ]


def test_daily_counts_window_length_and_order():
    now_ms = 1781735400000
    out = _daily_counts([], days=14, tz_offset_minutes=0, now_ms=now_ms)
    assert len(out) == 14
    assert out[-1]['day'] > out[0]['day']


@pytest.mark.asyncio
async def test_member_gets_items_with_task_join_and_daily(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        team, ws, s = await _stream(c)
        t = (await c.post(f"/api/v1/workos/workstreams/{s['id']}/tasks", json={'title': 'T'})).json()
        await c.patch(f"/api/v1/workos/tasks/{t['id']}", json={'status': 'in_progress'})
        r = await c.get(f"/api/v1/workos/workstreams/{s['id']}/activity")
        assert r.status_code == 200
        body = r.json()
        assert len(body['daily']) == 14
        assert body['items'], 'status change must produce activity'
        first = body['items'][0]
        assert first['task_key'] == t['key'] and first['task_title'] == 'T'
        # newest first
        times = [i['created_at'] for i in body['items']]
        assert times == sorted(times, reverse=True)


@pytest.mark.asyncio
async def test_clamps_do_not_error(monkeypatch):
    async with _client(monkeypatch, user=U1) as c:
        _, _, s = await _stream(c)
        r = await c.get(
            f"/api/v1/workos/workstreams/{s['id']}/activity?limit=99999&days=9999&tz_offset_minutes=99999"
        )
        assert r.status_code == 200
        assert len(r.json()['daily']) == 31


@pytest.mark.asyncio
async def test_non_member_gets_404(monkeypatch):
    # Mirror the outsider pattern from test_router_access_leaks.py: a second client
    # whose user has no membership row in the team.
    from open_webui.test.workos.test_router_access_leaks import U2  # adjust if named differently there
    async with _client(monkeypatch, user=U1) as c:
        _, _, s = await _stream(c)
        stream_id = s['id']
    async with _client(monkeypatch, user=U2) as c2:
        r = await c2.get(f'/api/v1/workos/workstreams/{stream_id}/activity')
        assert r.status_code == 404
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend; .venv/Scripts/python.exe -m pytest open_webui/test/workos/test_router_workstream_activity.py -q`
Expected: FAIL — `ImportError: cannot import name '_daily_counts'`.

- [ ] **Step 3: Implement the DAO methods**

In `backend/open_webui/models/workos.py`, append inside `ActivityDao` (after `list_for_task`):

```python
    async def list_for_workstream(
        self, workstream_id: str, limit: int = 30, db: Optional[AsyncSession] = None
    ) -> list:
        """Newest activities across the workstream's tasks, joined with task key/title."""
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosActivity, WorkosTask.key, WorkosTask.title)
                .join(WorkosTask, WorkosTask.id == WorkosActivity.task_id)
                .where(WorkosTask.workstream_id == workstream_id)
                .order_by(WorkosActivity.created_at.desc())
                .limit(limit)
            )
            out = []
            for row, task_key, task_title in res.all():
                item = ActivityModel.model_validate(row).model_dump()
                item['task_key'] = task_key
                item['task_title'] = task_title
                out.append(item)
            return out

    async def timestamps_for_workstream(
        self, workstream_id: str, since_ms: int, db: Optional[AsyncSession] = None
    ) -> list:
        async with get_async_db_context(db) as db:
            res = await db.execute(
                select(WorkosActivity.created_at)
                .join(WorkosTask, WorkosTask.id == WorkosActivity.task_id)
                .where(WorkosTask.workstream_id == workstream_id, WorkosActivity.created_at >= since_ms)
            )
            return [r[0] for r in res.all()]
```

- [ ] **Step 4: Implement the router helper + endpoint**

In `backend/open_webui/routers/workos.py`, below the existing `list_activity` endpoint (~line 1027), add (add `import time` and `from datetime import datetime, timedelta, timezone` to the module imports if not present):

```python
def _daily_counts(timestamps: list, days: int, tz_offset_minutes: int, now_ms: int) -> list:
    """Bucket epoch-ms timestamps into the viewer's last `days` local calendar days
    (oldest first). tz_offset_minutes is minutes AHEAD of UTC (JS: -getTimezoneOffset())."""
    tz = timezone(timedelta(minutes=tz_offset_minutes))
    today = datetime.fromtimestamp(now_ms / 1000, tz).date()
    ordered = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]
    counts = {d.isoformat(): 0 for d in ordered}
    for ts in timestamps:
        key = datetime.fromtimestamp(ts / 1000, tz).date().isoformat()
        if key in counts:
            counts[key] += 1
    return [{'day': k, 'n': v} for k, v in counts.items()]


@router.get('/workstreams/{workstream_id}/activity')
async def list_workstream_activity(
    request: Request, workstream_id: str, limit: int = 30, days: int = 14, tz_offset_minutes: int = 0,
    user=Depends(get_verified_user), db: AsyncSession = Depends(get_async_session)
):
    await _require_workos(request, user, db)
    await require_workstream_visible(user, workstream_id, db)
    limit = max(1, min(limit, 100))
    days = max(1, min(days, 31))
    tz_offset_minutes = max(-840, min(tz_offset_minutes, 840))
    now_ms = int(time.time() * 1000)
    since = now_ms - (days + 1) * 86_400_000  # one spare day so tz shifting never truncates
    items = await Activity.list_for_workstream(workstream_id, limit=limit, db=db)
    stamps = await Activity.timestamps_for_workstream(workstream_id, since, db=db)
    return {'items': items, 'daily': _daily_counts(stamps, days, tz_offset_minutes, now_ms)}
```

Check the top of the file: `Activity` is already imported from `open_webui.models.workos` (it is used by `create_comment`); `Request`, `Depends`, `AsyncSession`, `get_async_session`, `get_verified_user` all exist.

- [ ] **Step 5: Run the new tests, then the full backend workos suite**

Run: `cd backend; .venv/Scripts/python.exe -m pytest open_webui/test/workos/test_router_workstream_activity.py -q`
Expected: PASS.
Run: `cd backend; .venv/Scripts/python.exe -m pytest open_webui/test/workos -q`
Expected: PASS (all).

- [ ] **Step 6: Update the access-control reference doc (standing rule)**

In `docs/superpowers/specs/2026-06-26-workos-access-control.md`, §4 "Comments / activity" table, add a row after the `GET /tasks/{id}/activity` row:

```markdown
| `GET /workstreams/{id}/activity` | `_require_workos` + `require_workstream_visible` — workstream-scoped activity list (items joined w/ task key/title) + tz-aware daily histogram; `limit`≤100, `days`≤31 clamped | [workos.py](backend/open_webui/routers/workos.py) |
```

- [ ] **Step 7: Commit**

```bash
git add backend/open_webui/models/workos.py backend/open_webui/routers/workos.py backend/open_webui/test/workos/test_router_workstream_activity.py docs/superpowers/specs/2026-06-26-workos-access-control.md
git commit -m "feat(workos): workstream activity endpoint w/ tz-aware daily histogram

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: API client + store plumbing for workstream activity

**Files:**
- Modify: `src/lib/components/workos/lib/api.ts` (Activity section, ~line 136)
- Modify: `src/lib/components/workos/lib/store.ts`
- Test: `src/lib/components/workos/lib/store.test.ts` (append)

**Interfaces:**
- Consumes: Task 6 endpoint.
- Produces (used by Tasks 9, 12, 14):

```ts
// api.ts
export const getWorkstreamActivity: (token: string, workstreamId: string, opts?: { limit?: number; days?: number })
	=> Promise<{ items: WsActivityItem[]; daily: { day: string; n: number }[] }>;
// store.ts
export interface WsActivityItem extends Activity { task_key?: string; task_title?: string; workstream_id?: string }
export interface WsActivityState { items: WsActivityItem[]; daily: { day: string; n: number }[]; loaded: boolean; error: boolean }
export const wsActivity: Writable<WsActivityState>;
export async function loadWorkstreamActivity(id: string): Promise<void>;
export function applyOverviewActivityEvent(payload: any): void; // exported for tests
```

- [ ] **Step 1: Add the API client function**

In `api.ts`, Activity section:

```ts
// Workstream-scoped activity: newest items (joined w/ task key/title) + a daily
// histogram bucketed in the viewer's local days. JS getTimezoneOffset() is minutes
// BEHIND UTC, so minutes AHEAD = its negation (Amman UTC+3 → +180).
export const getWorkstreamActivity = (
	token: string, workstreamId: string, opts?: { limit?: number; days?: number }
) => {
	const tz = -new Date().getTimezoneOffset();
	return request<{
		items: (Activity & { task_key?: string; task_title?: string; workstream_id?: string })[];
		daily: { day: string; n: number }[];
	}>(
		token,
		`/workstreams/${workstreamId}/activity?limit=${opts?.limit ?? 30}&days=${opts?.days ?? 14}&tz_offset_minutes=${tz}`
	);
};
```

- [ ] **Step 2: Write the failing store test**

Read `src/lib/components/workos/lib/store.test.ts` first and follow its existing mocking/setup exactly (it already tests `applyTaskEvent`-style reducers). Append:

```ts
describe('applyOverviewActivityEvent', () => {
	it('prepends for the current workstream, dedupes, and bumps today bucket', () => {
		currentWorkstreamId.set('ws1');
		tasks.set([{ id: 'tsk', key: 'K-1', title: 'Task' } as any]);
		const d = new Date();
		const p = (n: number) => String(n).padStart(2, '0');
		const today = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
		wsActivity.set({ items: [], daily: [{ day: today, n: 0 }], loaded: true, error: false });
		const payload = { id: 'a1', task_id: 'tsk', team_id: 'tm', user_id: 'u1', type: 'status_changed', data: {}, created_at: Date.now(), workstream_id: 'ws1' };
		applyOverviewActivityEvent(payload);
		applyOverviewActivityEvent(payload); // duplicate → ignored
		const s = get(wsActivity);
		expect(s.items).toHaveLength(1);
		expect(s.items[0].task_key).toBe('K-1'); // resolved from tasks store
		expect(s.daily[0].n).toBe(1);
	});

	it('ignores events for other workstreams', () => {
		currentWorkstreamId.set('ws1');
		wsActivity.set({ items: [], daily: [], loaded: true, error: false });
		applyOverviewActivityEvent({ id: 'a2', task_id: 'x', workstream_id: 'other', type: 'created', created_at: 1 });
		expect(get(wsActivity).items).toHaveLength(0);
	});
});
```

Run: `npx vitest run src/lib/components/workos/lib/store.test.ts`
Expected: FAIL — `wsActivity` not exported.

- [ ] **Step 3: Implement the store additions**

In `store.ts`:

(a) Below the `notifications`/`unreadCount` declarations (~line 63):

```ts
export interface WsActivityItem extends Activity { task_key?: string; task_title?: string; workstream_id?: string }
export interface WsActivityState {
	items: WsActivityItem[]; daily: { day: string; n: number }[]; loaded: boolean; error: boolean;
}
export const wsActivity: Writable<WsActivityState> = writable({ items: [], daily: [], loaded: false, error: false });
```

(b) Near `loadNotifications` (~line 341):

```ts
export async function loadWorkstreamActivity(id: string): Promise<void> {
	wsActivity.set({ items: [], daily: [], loaded: false, error: false });
	try {
		const r = await api.getWorkstreamActivity(token(), id);
		if (get(currentWorkstreamId) !== id) return; // user moved on
		wsActivity.set({ items: r.items, daily: r.daily, loaded: true, error: false });
	} catch {
		wsActivity.set({ items: [], daily: [], loaded: true, error: true });
	}
}

function localDayKey(now: number): string {
	const d = new Date(now);
	const p = (n: number) => String(n).padStart(2, '0');
	return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** Fold a workstream-room activity event into the Overview pulse + today's histogram
 * bucket. task_key/title fall back to the tasks store (realtime payloads lack them). */
export function applyOverviewActivityEvent(payload: any): void {
	if (!payload || !payload.id || payload.workstream_id !== get(currentWorkstreamId)) return;
	const t = get(tasks).find((x) => x.id === payload.task_id);
	const item: WsActivityItem = {
		...payload,
		task_key: payload.task_key ?? t?.key,
		task_title: payload.task_title ?? t?.title
	};
	const todayKey = localDayKey(Date.now());
	wsActivity.update((s) => ({
		...s,
		items: s.items.some((a) => a.id === item.id) ? s.items : [item, ...s.items].slice(0, 30),
		daily: s.daily.map((d) => (d.day === todayKey ? { ...d, n: d.n + 1 } : d))
	}));
}
```

(c) In `connectRealtime`, the COLLAB_EVENTS loop currently binds every event to `applyCollabEvent` only. Change the loop body so `workos:activity.created` also feeds the Overview:

```ts
	for (const ev of COLLAB_EVENTS) {
		handlers[ev] = (payload: any) => {
			applyCollabEvent(ev, payload);
			if (ev === 'workos:activity.created') applyOverviewActivityEvent(payload);
		};
		s.on(ev, handlers[ev]);
	}
```

- [ ] **Step 4: Run the store tests**

Run: `npx vitest run src/lib/components/workos/lib/store.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/api.ts src/lib/components/workos/lib/store.ts src/lib/components/workos/lib/store.test.ts
git commit -m "feat(workos): wsActivity store + realtime fold-in for overview

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: Install the shadcn-svelte chart component (LayerChart)

**Files:**
- Create (via CLI): `src/lib/components/ui/chart/*`
- Modify (via CLI): `package.json`, `package-lock.json`

**Interfaces:**
- Produces (used by Task 11): `import * as Chart from '$lib/components/ui/chart';` (`Chart.Container`, `Chart.Tooltip`, `Chart.ChartConfig`), `import { BarChart } from 'layerchart';`, `import { scaleBand } from 'd3-scale';`

- [ ] **Step 1: Invoke the shadcn-svelte skill** for current CLI/docs context (the repo already has `components.json` with aliases `$lib/components` / `$lib/components/ui/utils`).

- [ ] **Step 2: Add the chart component**

Run: `npx shadcn-svelte@latest add chart --yes`
Expected: creates `src/lib/components/ui/chart/` and installs `layerchart` as a dependency. If `d3-scale` is not pulled in transitively as a direct import target, run: `npm i d3-scale` and `npm i -D @types/d3-scale`.

- [ ] **Step 3: Verify types**

Run: `npm run check`
Expected: no NEW errors (pre-existing count unchanged; note the baseline before installing).

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/ui/chart package.json package-lock.json components.json
git commit -m "feat(workos): add shadcn-svelte chart component (layerchart)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

(Only include `components.json` if the CLI actually modified it — check `git status` first.)

---

### Task 9: View wiring + `OverviewView` scaffold

**Files:**
- Modify: `src/lib/components/workos/lib/store.ts:18` (ViewKey union)
- Modify: `src/lib/components/workos/chrome/Topbar.svelte:11-20` (TABS + selectTab) — CAUTION: this file has pre-existing uncommitted user edits; edit on top of the current working-tree content and mention the inclusion in the commit body.
- Modify: `src/lib/components/workos/WorkOSApp.svelte` (import, Topbar condition, render branch)
- Create: `src/lib/components/workos/views/OverviewView.svelte`

**Interfaces:**
- Consumes: everything produced by Tasks 3–5, 7.
- Produces: `view.set('overview')` reachable from the Topbar; `OverviewView` computes and passes props to the (not-yet-created) child components — this task mounts placeholder `<div>`s where Tasks 10–14 will mount components.

- [ ] **Step 1: Extend the ViewKey union**

`store.ts` line 18:

```ts
export type ViewKey = 'board' | 'list' | 'admin' | 'inbox' | 'mywork' | 'calendar' | 'overview';
```

- [ ] **Step 2: Go live in the Topbar**

In `Topbar.svelte` (respect any pre-existing local edits): set the overview tab live and widen the cast:

```ts
	const TABS = [
		{ key: 'overview', label: 'Overview', icon: 'layers', live: true },
		{ key: 'list', label: 'List', icon: 'list', live: true },
		{ key: 'board', label: 'Board', icon: 'columns', live: true },
		{ key: 'calendar', label: 'Calendar', icon: 'calendar', live: true },
		{ key: 'files', label: 'Files', icon: 'paperclip', live: false }
	];
	function selectTab(t: (typeof TABS)[number]) {
		if (t.live) view.set(t.key as 'board' | 'list' | 'calendar' | 'overview');
	}
```

- [ ] **Step 3: Render the view in WorkOSApp**

In `WorkOSApp.svelte`: add `import OverviewView from './views/OverviewView.svelte';`; extend the Topbar condition to `{#if $view === 'board' || $view === 'list' || $view === 'calendar' || $view === 'overview'}`; add a render branch before the ListView branch:

```svelte
				{:else if $view === 'overview'}
					<OverviewView />
```

- [ ] **Step 4: Create the scaffold**

Create `src/lib/components/workos/views/OverviewView.svelte`:

```svelte
<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import {
		tasks, currentWorkstream, workspaces, wsActivity,
		loadWorkstreamActivity, displayName
	} from '../lib/store';
	import {
		computeKpis, weeklyMomentum, completionTime, priorityPairs, statusMix,
		teamRows, attentionList, isOpen
	} from '../lib/overview';

	// Live clock so overdue/day buckets roll over without a reload (spec §2).
	let now = Date.now();
	let timer: ReturnType<typeof setInterval>;
	onMount(() => { timer = setInterval(() => (now = Date.now()), 60_000); });
	onDestroy(() => clearInterval(timer));

	// Momentum window (weeks); KPI tiles stay on rolling 7-day windows by design.
	let weeks: 4 | 6 | 12 = 6;

	$: ws = $currentWorkstream;
	$: parentWorkspace = ws ? $workspaces.find((w) => w.id === ws.workspace_id) : null;

	let loadedFor: string | null = null;
	$: if (ws && loadedFor !== ws.id) { loadedFor = ws.id; void loadWorkstreamActivity(ws.id); }

	$: kpis = computeKpis($tasks, now);
	$: bins = weeklyMomentum($tasks, now, weeks);
	$: completion = completionTime($tasks, now, weeks);
	$: pairs = priorityPairs($tasks);
	$: mix = statusMix($tasks);
	$: rows = teamRows($tasks, now, displayName);
	$: attention = attentionList($tasks, now);
	$: peopleCount = new Set($tasks.filter(isOpen).flatMap((t) => t.assignee_ids ?? [])).size;
</script>

<div class="h-full overflow-auto bg-gray-50 dark:bg-gray-900">
	<div class="max-w-[1240px] mx-auto p-4 flex flex-col gap-3">
		{#if !mix.total}
			<div class="h-64 flex flex-col items-center justify-center gap-2 text-center">
				<div class="text-lg font-medium">No tasks here yet</div>
				<div class="text-sm text-gray-500">Add tasks on the board and this overview fills itself in.</div>
			</div>
		{:else}
			<!-- Task 10 mounts KpiBand here -->
			<div data-slot="kpi"></div>
			<div class="grid grid-cols-1 xl:grid-cols-[1.6fr_1fr] gap-3 items-start">
				<!-- Task 11 mounts MomentumCard -->
				<div data-slot="momentum"></div>
				<!-- Task 12 mounts DistributionCard -->
				<div data-slot="distribution"></div>
			</div>
			<!-- Task 13 mounts TeamTable -->
			<div data-slot="team"></div>
			<div class="grid grid-cols-1 xl:grid-cols-[1.35fr_1fr] gap-3 items-start">
				<!-- Task 14 mounts AttentionList + PulseCard -->
				<div data-slot="attention"></div>
				<div data-slot="pulse"></div>
			</div>
		{/if}
	</div>
</div>
```

(The `$:` computed values are intentionally unused until Tasks 10–14 consume them; if `svelte-check` flags unused vars as errors — it normally does not for `$:` bindings — prefix nothing, just proceed; warnings are acceptable at this task.)

- [ ] **Step 5: Type-check and commit**

Run: `npm run check`
Expected: no NEW errors.

```bash
git add src/lib/components/workos/lib/store.ts src/lib/components/workos/chrome/Topbar.svelte src/lib/components/workos/WorkOSApp.svelte src/lib/components/workos/views/OverviewView.svelte
git commit -m "feat(workos): overview tab goes live with view scaffold

Includes pre-existing local Topbar edits already in the working tree.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: `KpiBand` — ink hero + 5 KPI tiles + range selector

**Files:**
- Create: `src/lib/components/workos/views/overview/KpiBand.svelte`
- Modify: `src/lib/components/workos/views/OverviewView.svelte` (mount)

**Interfaces:**
- Consumes: `OverviewKpis` (Task 3).
- Produces: `<KpiBand kpis weeks onWeeks workspaceName workstreamName taskCount peopleCount />`

- [ ] **Step 1: Create the component**

The ink palette is deliberately constant across themes (spec §6). Create `KpiBand.svelte`:

```svelte
<script lang="ts">
	import type { OverviewKpis } from '../../lib/overview';

	export let kpis: OverviewKpis;
	export let weeks: 4 | 6 | 12;
	export let onWeeks: (w: 4 | 6 | 12) => void;
	export let workspaceName = '';
	export let workstreamName = '';
	export let taskCount = 0;
	export let peopleCount = 0;

	const WEEK_OPTIONS: (4 | 6 | 12)[] = [4, 6, 12];

	type Tile = { dot: string; label: string; value: string; delta?: { up: boolean; text: string } | null; caption: string };
	$: tiles = [
		{ dot: '#00a5ba', label: 'Open tasks', value: String(kpis.open),
			caption: `${kpis.inProgress} in progress · ${kpis.inReview} in review` },
		{ dot: '#f0b47a', label: 'Due this week', value: String(kpis.dueThisWeek),
			caption: kpis.dueTomorrow ? `${kpis.dueTomorrow} due tomorrow` : 'none tomorrow' },
		{ dot: '#f27d72', label: 'Overdue', value: String(kpis.overdue),
			caption: kpis.oldestOverdueDays != null ? `oldest ${kpis.oldestOverdueDays}d late` : 'all clear' },
		{ dot: '#5DCAA5', label: 'Completed', value: String(kpis.completed7d),
			delta: kpis.completed7d === kpis.completedPrev7d ? null
				: { up: kpis.completed7d > kpis.completedPrev7d, text: `vs ${kpis.completedPrev7d}` },
			caption: 'last 7 days vs prior 7' },
		{ dot: '#8fa3ff', label: 'New tasks', value: String(kpis.new7d), caption: 'added in last 7 days' }
	] satisfies Tile[];
</script>

<section class="rounded-2xl p-4 sm:p-5" style="background:#101623" aria-label="Workstream key figures">
	<div class="flex items-center gap-3 mb-4">
		<div class="min-w-0">
			<div class="text-[11px]" style="color:#7e8aa0">{workspaceName ? `${workspaceName} / ` : ''}{workstreamName}</div>
			<h2 class="text-[17px] font-medium mt-0.5" style="color:#eef2f8">Overview</h2>
		</div>
		<div class="ml-auto text-[11px]" style="color:#7e8aa0">{taskCount} tasks · {peopleCount} people</div>
		<div class="flex rounded-full border p-0.5" style="border-color:#2a3651" role="group" aria-label="Momentum window">
			{#each WEEK_OPTIONS as w (w)}
				<button
					type="button"
					class="px-2.5 py-1 rounded-full text-[11px] font-medium transition-colors"
					style="color:{weeks === w ? '#101623' : '#aab5c8'}; background:{weeks === w ? '#aab5c8' : 'transparent'}"
					aria-pressed={weeks === w}
					onclick={() => onWeeks(w)}
				>{w}w</button>
			{/each}
		</div>
	</div>
	<div class="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-2">
		{#each tiles as t (t.label)}
			<div class="rounded-xl px-3 py-2.5 border" style="background:#1b2434;border-color:#232f45"
				aria-label="{t.label}: {t.value}">
				<div class="text-[11px]" style="color:#9aa6ba"><span style="color:{t.dot}">●</span> {t.label}</div>
				<div class="mt-1 text-[22px] font-medium tabular-nums" style="color:#ffffff">
					{t.value}
					{#if t.delta}
						<span class="align-[3px] text-[10.5px] rounded-full px-1.5 py-0.5"
							style="background:{t.delta.up ? '#123c2c' : '#3c1a1a'};color:{t.delta.up ? '#5DCAA5' : '#f27d72'}">
							{t.delta.up ? '↑' : '↓'} {t.delta.text}
						</span>
					{/if}
				</div>
				<div class="mt-1 text-[10.5px]" style="color:#7e8aa0">{t.caption}</div>
			</div>
		{/each}
	</div>
</section>
```

- [ ] **Step 2: Mount it**

In `OverviewView.svelte`: `import KpiBand from './overview/KpiBand.svelte';` and replace `<div data-slot="kpi"></div>` with:

```svelte
			<KpiBand
				{kpis} {weeks} onWeeks={(w) => (weeks = w)}
				workspaceName={parentWorkspace?.name ?? ''} workstreamName={ws?.name ?? ''}
				taskCount={mix.total} {peopleCount}
			/>
```

- [ ] **Step 3: Type-check**

Run: `npm run check`
Expected: no NEW errors.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/overview/KpiBand.svelte src/lib/components/workos/views/OverviewView.svelte
git commit -m "feat(workos): overview ink hero KPI band

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 11: `MomentumCard` — LayerChart grouped bars + completion-time footnote

**Files:**
- Create: `src/lib/components/workos/views/overview/MomentumCard.svelte`
- Modify: `src/lib/components/workos/views/OverviewView.svelte` (mount)

**Interfaces:**
- Consumes: `WeekBin[]`, `CompletionTime` (Task 4); `Chart` component (Task 8).
- Produces: `<MomentumCard bins completion />`

- [ ] **Step 1: Invoke the shadcn-svelte skill** and read the chart component's bar-chart example (grouped/"multiple" variant) to confirm current LayerChart prop names before writing code.

- [ ] **Step 2: Create the component**

```svelte
<script lang="ts">
	import * as Chart from '$lib/components/ui/chart';
	import { BarChart } from 'layerchart';
	import { scaleBand } from 'd3-scale';
	import type { WeekBin, CompletionTime } from '../../lib/overview';

	export let bins: WeekBin[];
	export let completion: CompletionTime;

	const config = {
		created: { label: 'Created', color: '#c5e8ee' },
		completed: { label: 'Completed', color: '#00a5ba' }
	} satisfies Chart.ChartConfig;

	$: data = bins.map((b) => ({
		week: b.current ? `${b.label} (this week)` : b.label,
		created: b.created,
		completed: b.completed
	}));

	// Completion-time delta: lower is better → ▾ green when faster, ▴ red when slower.
	$: delta =
		completion.avgDays != null && completion.prevAvgDays != null && completion.avgDays !== completion.prevAvgDays
			? { faster: completion.avgDays < completion.prevAvgDays,
				text: Math.abs(Math.round((completion.avgDays - completion.prevAvgDays) * 10) / 10).toFixed(1) }
			: null;
</script>

<section class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 min-w-0">
	<div class="flex items-start gap-2 mb-2">
		<div>
			<h3 class="text-[13.5px] font-medium">Weekly momentum</h3>
			<p class="text-[11px] text-gray-400 mt-0.5">Tasks created vs completed per week.</p>
		</div>
	</div>
	<Chart.Container {config} class="h-[190px] w-full" aria-label="Created versus completed tasks per week">
		<BarChart
			{data}
			x="week"
			xScale={scaleBand().padding(0.3)}
			axis="x"
			seriesLayout="group"
			series={[
				{ key: 'created', label: 'Created', color: config.created.color },
				{ key: 'completed', label: 'Completed', color: config.completed.color }
			]}
			props={{ bars: { radius: 4, 'stroke-width': 0 }, xAxis: { format: (v: string) => v.replace(' (this week)', ' ·') } }}
		>
			{#snippet tooltip()}
				<Chart.Tooltip />
			{/snippet}
		</BarChart>
	</Chart.Container>
	<div class="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-[11px] text-gray-500 dark:text-gray-400">
		<span><span style="color:#c5e8ee">●</span> Created</span>
		<span><span style="color:#00a5ba">●</span> Completed</span>
		<span class="ml-auto">
			avg completion time
			<b class="font-medium text-gray-900 dark:text-gray-100">{completion.avgDays != null ? `${completion.avgDays}d` : '—'}</b>
			{#if delta}
				<span class={delta.faster ? 'text-green-700 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
					{delta.faster ? '▾' : '▴'}{delta.text}
				</span>
			{/if}
		</span>
	</div>
</section>
```

If the installed LayerChart version's `BarChart` API differs from the above (prop names move between minor versions), follow the shadcn-svelte chart example verbatim and keep: grouped layout, the two series with these exact colors, band x-scale, rounded bars, `Chart.Tooltip`.

- [ ] **Step 3: Mount it**

In `OverviewView.svelte`: `import MomentumCard from './overview/MomentumCard.svelte';`, replace `<div data-slot="momentum"></div>` with `<MomentumCard {bins} {completion} />`.

- [ ] **Step 4: Type-check and commit**

Run: `npm run check` — expected: no NEW errors.

```bash
git add src/lib/components/workos/views/overview/MomentumCard.svelte src/lib/components/workos/views/OverviewView.svelte
git commit -m "feat(workos): overview weekly momentum chart (layerchart)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 12: `DistributionCard` — priority pairs + status bar + activity strip

**Files:**
- Create: `src/lib/components/workos/views/overview/DistributionCard.svelte`
- Modify: `src/lib/components/workos/views/OverviewView.svelte` (mount)

**Interfaces:**
- Consumes: `PriorityPair[]`, `statusMix` result (Task 5); `daily`/`loaded`/`error` from `wsActivity` (Task 7); `STATUS_COLOR`, `PRIORITY_COLOR` from `../../lib/colors`; `STATUS_LABEL` from `../../lib/types`.
- Produces: `<DistributionCard pairs mix daily loaded error />`

- [ ] **Step 1: Create the component**

```svelte
<script lang="ts">
	import { STATUS_COLOR, PRIORITY_COLOR } from '../../lib/colors';
	import { STATUS_LABEL } from '../../lib/types';
	import type { PriorityPair, StatusSlice } from '../../lib/overview';

	export let pairs: PriorityPair[];
	export let mix: { total: number; slices: StatusSlice[] };
	export let daily: { day: string; n: number }[];
	export let loaded = false;
	export let error = false;

	$: maxDaily = Math.max(1, ...daily.map((d) => d.n));
	// Intensity: quiet base for zero, then three teal steps by share of the busiest day.
	function stripColor(n: number): string {
		if (n === 0) return 'rgb(0 165 186 / 0.12)';
		const r = n / maxDaily;
		return r > 0.66 ? '#00a5ba' : r > 0.33 ? '#49b9c8' : '#8fd2dd';
	}
	function stripHeight(n: number): number {
		return n === 0 ? 4 : Math.max(8, Math.round((n / maxDaily) * 34));
	}
	const pairColor = (p: PriorityPair): string =>
		p.key === 'urgent' || p.key === 'high' ? PRIORITY_COLOR[p.key] : 'inherit';
</script>

<section class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 min-w-0">
	<h3 class="text-[13.5px] font-medium">Distribution</h3>
	<p class="text-[11px] text-gray-400 mt-0.5">Open tasks by priority and status.</p>

	<div class="grid grid-cols-2 gap-x-3 gap-y-2 mt-3 text-[11px] text-gray-500 dark:text-gray-400">
		{#each pairs as p (p.key)}
			<div>
				{p.label}
				<div class="text-[16px] font-medium tabular-nums text-gray-900 dark:text-gray-100" style="color:{pairColor(p)}">{p.n}</div>
			</div>
		{/each}
	</div>

	<div class="flex h-[9px] rounded-full overflow-hidden mt-4 bg-gray-100 dark:bg-gray-800" role="img"
		aria-label="Status mix: {mix.slices.map((s) => `${STATUS_LABEL[s.status]} ${s.n}`).join(', ')}">
		{#each mix.slices as s (s.status)}
			{#if s.n > 0}<div style="width:{s.pct}%;background:{STATUS_COLOR[s.status]}"></div>{/if}
		{/each}
	</div>
	<div class="flex gap-x-2.5 gap-y-1 flex-wrap mt-2 text-[10.5px] text-gray-500 dark:text-gray-400">
		{#each mix.slices as s (s.status)}
			{#if s.n > 0}<span><span style="color:{STATUS_COLOR[s.status]}">●</span> {STATUS_LABEL[s.status]} {s.n}</span>{/if}
		{/each}
	</div>

	<div class="text-[11px] text-gray-400 mt-4">Activity · last 14 days</div>
	{#if error}
		<div class="text-[11px] text-gray-400 mt-2">Couldn't load activity.</div>
	{:else if !loaded}
		<div class="h-[34px] mt-1.5 rounded bg-gray-100 dark:bg-gray-800 animate-pulse"></div>
	{:else}
		<div class="flex items-end gap-[5px] mt-1.5 h-[34px]" role="img"
			aria-label="Daily activity, busiest day {maxDaily} events">
			{#each daily as d (d.day)}
				<div class="w-2 rounded" title="{d.day} · {d.n}" style="height:{stripHeight(d.n)}px;background:{stripColor(d.n)}"></div>
			{/each}
		</div>
	{/if}
</section>
```

- [ ] **Step 2: Mount it**

In `OverviewView.svelte`: `import DistributionCard from './overview/DistributionCard.svelte';`, replace `<div data-slot="distribution"></div>` with:

```svelte
				<DistributionCard {pairs} {mix} daily={$wsActivity.daily} loaded={$wsActivity.loaded} error={$wsActivity.error} />
```

- [ ] **Step 3: Type-check and commit**

Run: `npm run check` — expected: no NEW errors.

```bash
git add src/lib/components/workos/views/overview/DistributionCard.svelte src/lib/components/workos/views/OverviewView.svelte
git commit -m "feat(workos): overview distribution card w/ activity strip

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 13: `TeamTable` — per-member load and health

**Files:**
- Create: `src/lib/components/workos/views/overview/TeamTable.svelte`
- Modify: `src/lib/components/workos/views/OverviewView.svelte` (mount)

**Interfaces:**
- Consumes: `TeamRow[]`, `MemberHealth` (Task 5); `displayName`, `initials` from `../../lib/store`.
- Produces: `<TeamTable rows />`

- [ ] **Step 1: Create the component**

```svelte
<script lang="ts">
	import { displayName, initials } from '../../lib/store';
	import type { TeamRow, MemberHealth } from '../../lib/overview';

	export let rows: TeamRow[];

	const HEALTH_PILL: Record<MemberHealth, { label: string; cls: string }> = {
		on_track: { label: 'On track', cls: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300' },
		watch: { label: 'Watch', cls: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300' },
		needs_support: { label: 'Needs support', cls: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300' }
	};
	const HEALTH_RULE =
		'Needs support: 2+ tasks overdue or behind · Watch: 1 overdue/behind or 2+ at risk · On track: otherwise';
	const GRID = 'grid-template-columns:minmax(150px,1.4fr) repeat(4,minmax(58px,.7fr)) minmax(110px,1.1fr) minmax(104px,.9fr)';
	// Deterministic avatar tint per user id (same trick as elsewhere: hash → palette).
	const AVATAR = ['#007a8a', '#769a4a', '#d97706', '#7c3aed', '#db2777', '#0ea5e9'];
	function avatarColor(id: string): string {
		let h = 0;
		for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
		return AVATAR[h % AVATAR.length];
	}
</script>

<section class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 min-w-0">
	<h3 class="text-[13.5px] font-medium">Team performance</h3>
	<p class="text-[11px] text-gray-400 mt-0.5">
		Assignments and workload across this workstream. A task counts for each of its assignees.
	</p>
	{#if !rows.length}
		<div class="py-6 text-center text-sm text-gray-400">No open tasks assigned yet.</div>
	{:else}
		<div class="grid items-center gap-x-3 gap-y-1 mt-3 text-[10.5px] text-gray-400" style={GRID}>
			<span>Member</span><span class="text-right">Open</span><span class="text-right">In progress</span>
			<span class="text-right">In review</span><span class="text-right">Overdue</span>
			<span title="Relative to the busiest member">Load</span>
			<span title={HEALTH_RULE}>Health</span>
		</div>
		{#each rows as r (r.userId ?? '∅')}
			<div class="grid items-center gap-x-3 py-2 border-t border-gray-100 dark:border-gray-800 text-[12px]" style={GRID}>
				{#if r.userId}
					<span class="flex items-center gap-2 min-w-0">
						<span class="w-6 h-6 rounded-full text-white text-[10px] inline-flex items-center justify-center flex-none"
							style="background:{avatarColor(r.userId)}">{initials(r.userId)}</span>
						<span class="truncate">{displayName(r.userId)}</span>
					</span>
				{:else}
					<span class="flex items-center gap-2 text-gray-400">
						<span class="w-6 h-6 rounded-full bg-gray-100 dark:bg-gray-800 text-[10px] inline-flex items-center justify-center flex-none">—</span>
						Unassigned
					</span>
				{/if}
				<span class="text-right tabular-nums">{r.open}</span>
				<span class="text-right tabular-nums {r.userId ? '' : 'text-gray-300 dark:text-gray-600'}">{r.userId ? r.inProgress : '–'}</span>
				<span class="text-right tabular-nums {r.userId ? '' : 'text-gray-300 dark:text-gray-600'}">{r.userId ? r.inReview : '–'}</span>
				<span class="text-right tabular-nums {r.overdue ? 'text-red-600 dark:text-red-400' : 'text-gray-400'}">{r.userId ? r.overdue : '–'}</span>
				<span class="block h-[7px] rounded-full bg-gray-100 dark:bg-gray-800">
					<span class="block h-[7px] rounded-full" style="width:{Math.round(r.load * 100)}%;background:{r.userId ? '#00a5ba' : '#c9cfd7'}"></span>
				</span>
				<span>
					{#if r.health}
						<span class="text-[11px] rounded-full px-2 py-0.5 {HEALTH_PILL[r.health].cls}" title={HEALTH_RULE}>{HEALTH_PILL[r.health].label}</span>
					{:else}
						<span class="text-[11px] rounded-full px-2 py-0.5 bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400">Backlog pool</span>
					{/if}
				</span>
			</div>
		{/each}
	{/if}
</section>
```

- [ ] **Step 2: Mount it**

In `OverviewView.svelte`: `import TeamTable from './overview/TeamTable.svelte';`, replace `<div data-slot="team"></div>` with `<TeamTable {rows} />`.

- [ ] **Step 3: Type-check and commit**

Run: `npm run check` — expected: no NEW errors.

```bash
git add src/lib/components/workos/views/overview/TeamTable.svelte src/lib/components/workos/views/OverviewView.svelte
git commit -m "feat(workos): overview team performance table

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 14: `AttentionList` + `PulseCard`

**Files:**
- Create: `src/lib/components/workos/views/overview/AttentionList.svelte`
- Create: `src/lib/components/workos/views/overview/PulseCard.svelte`
- Modify: `src/lib/components/workos/views/OverviewView.svelte` (mount both)

**Interfaces:**
- Consumes: `AttentionItem[]` (Task 5); `WsActivityItem[]` (Task 7); `openTask`, `displayName`, `initials` from `../../lib/store`; `activityLabel(a, nameOf)` from `../../lib/activity`; `agoLabel` from `../../lib/overview`.
- Produces: `<AttentionList items />`, `<PulseCard items loaded error now />`

- [ ] **Step 1: Create `AttentionList.svelte`**

```svelte
<script lang="ts">
	import { openTask } from '../../lib/store';
	import type { AttentionItem, AttentionClass } from '../../lib/overview';

	export let items: AttentionItem[];

	let expanded = false;
	$: shown = expanded ? items : items.slice(0, 6);

	const DOT: Record<AttentionClass, string> = {
		overdue: '#dc2626', behind: '#ea580c', at_risk: '#f59e0b', due_soon: '#f59e0b'
	};
	function label(i: AttentionItem): { text: string; cls: string; title?: string } {
		if (i.cls === 'overdue') return { text: `${i.daysLate}d late`, cls: 'text-red-600 dark:text-red-400' };
		if (i.cls === 'behind')
			return { text: 'behind plan', cls: 'text-orange-600 dark:text-orange-400', title: `${Math.round(i.gap ?? 0)} points behind planned progress` };
		if (i.cls === 'at_risk')
			return { text: 'at risk', cls: 'text-amber-600 dark:text-amber-500', title: `${Math.round(i.gap ?? 0)} points behind planned progress` };
		return { text: `due ${i.dueLabel}`, cls: 'text-amber-700 dark:text-amber-500' };
	}
</script>

<section class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 min-w-0">
	<h3 class="text-[13.5px] font-medium">Needs attention</h3>
	<p class="text-[11px] text-gray-400 mt-0.5">Overdue and slipping tasks, most urgent first.</p>
	{#if !items.length}
		<div class="py-6 text-center text-sm text-gray-400">Nothing needs attention.</div>
	{:else}
		<div class="mt-2.5 flex flex-col gap-0.5">
			{#each shown as i (i.task.id)}
				{@const l = label(i)}
				<button
					type="button"
					onclick={() => openTask(i.task.id)}
					class="flex items-center gap-2.5 w-full text-left px-2 py-1.5 rounded-lg text-[12.5px] hover:bg-gray-50 dark:hover:bg-gray-800/60
						{i.cls === 'overdue' ? 'bg-red-50/60 dark:bg-red-950/20' : ''}"
				>
					<span class="w-[7px] h-[7px] rounded-full flex-none" style="background:{DOT[i.cls]}"></span>
					<span class="min-w-0 flex-1 truncate">{i.task.title} <span class="text-gray-400">· {i.task.key}</span></span>
					<span class="flex-none text-[11.5px] tabular-nums {l.cls}" title={l.title}>{l.text}</span>
				</button>
			{/each}
		</div>
		{#if items.length > 6}
			<button type="button" class="mt-2 text-[12px] text-primary font-medium hover:opacity-80" onclick={() => (expanded = !expanded)}>
				{expanded ? 'Show fewer' : `Show all ${items.length}`}
			</button>
		{/if}
	{/if}
</section>
```

- [ ] **Step 2: Create `PulseCard.svelte`**

```svelte
<script lang="ts">
	import { openTask, displayName, initials } from '../../lib/store';
	import { activityLabel } from '../../lib/activity';
	import { agoLabel } from '../../lib/overview';
	import type { WsActivityItem } from '../../lib/store';

	export let items: WsActivityItem[];
	export let loaded = false;
	export let error = false;
	export let now: number;

	$: shown = items.slice(0, 8);
</script>

<section class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 min-w-0">
	<h3 class="text-[13.5px] font-medium">Pulse</h3>
	<p class="text-[11px] text-gray-400 mt-0.5">Latest activity in this workstream.</p>
	{#if error}
		<div class="py-6 text-center text-sm text-gray-400">Couldn't load activity.</div>
	{:else if !loaded}
		<div class="mt-3 flex flex-col gap-2">
			{#each Array(4) as _, i (i)}<div class="h-5 rounded bg-gray-100 dark:bg-gray-800 animate-pulse"></div>{/each}
		</div>
	{:else if !shown.length}
		<div class="py-6 text-center text-sm text-gray-400">No activity yet.</div>
	{:else}
		<div class="mt-2.5 flex flex-col gap-2">
			{#each shown as a (a.id)}
				<button type="button" class="flex items-start gap-2.5 text-left w-full" onclick={() => openTask(a.task_id)}>
					<span class="w-[22px] h-[22px] rounded-full bg-brand-100 text-brand-700 dark:bg-brand-900 dark:text-brand-200 text-[10px] inline-flex items-center justify-center flex-none">{initials(a.user_id)}</span>
					<span class="min-w-0 flex-1 text-[12px] text-gray-600 dark:text-gray-300 leading-snug">
						{activityLabel(a, displayName)}
						{#if a.task_key}<span class="text-primary tabular-nums"> · {a.task_key}</span>{/if}
					</span>
					<span class="flex-none text-[11px] text-gray-400">{agoLabel(a.created_at, now)}</span>
				</button>
			{/each}
		</div>
	{/if}
</section>
```

Before finalizing, read `src/lib/components/workos/lib/activity.ts` — `activityLabel(a: Activity, nameOf)` returns the full human line (it may already include the actor's name). Render exactly one name: if `activityLabel` includes it, drop any extra name prefix in the markup (the code above assumes it does).

- [ ] **Step 3: Mount both**

In `OverviewView.svelte`: import both; replace `<div data-slot="attention"></div>` with `<AttentionList items={attention} />` and `<div data-slot="pulse"></div>` with:

```svelte
				<PulseCard items={$wsActivity.items} loaded={$wsActivity.loaded} error={$wsActivity.error} {now} />
```

- [ ] **Step 4: Type-check and commit**

Run: `npm run check` — expected: no NEW errors.

```bash
git add src/lib/components/workos/views/overview/AttentionList.svelte src/lib/components/workos/views/overview/PulseCard.svelte src/lib/components/workos/views/OverviewView.svelte
git commit -m "feat(workos): overview attention list + activity pulse

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 15: Final verification sweep

**Files:** none new.

- [ ] **Step 1: Full frontend workos test run**

Run: `npx vitest run src/lib/components/workos`
Expected: PASS (all suites, including the pre-existing ones).

- [ ] **Step 2: Full backend workos test run**

Run: `cd backend; .venv/Scripts/python.exe -m pytest open_webui/test/workos -q`
Expected: PASS.

- [ ] **Step 3: Type check**

Run: `npm run check`
Expected: no NEW errors vs the pre-plan baseline.

- [ ] **Step 4: Spec coverage sweep**

Re-read `docs/superpowers/specs/2026-07-02-workos-overview-design.md` §2–§7 and confirm each definition maps to shipped code + a test. Confirm the access-control doc row landed (Task 6 Step 6). Fix anything missed, commit as `fix(workos): overview spec-coverage follow-ups`.

- [ ] **Step 5: Manual browser smoke (user-driven)**

Do NOT start a Vite dev server without asking the user first (standing rule — they run their own hot-reload server + Docker backend). Report readiness and ask the user to verify in their browser:
1. Overview tab appears next to List/Board/Calendar and renders for a workstream with tasks.
2. KPI numbers reconcile with the Board columns (open counts, overdue).
3. Momentum tooltip works; 4w/6w/12w selector redraws; footnote shows avg completion time.
4. Editing a task on the Board in another tab live-updates the Overview (KPIs, table).
5. Adding a comment/status change live-prepends into Pulse and bumps today's strip bar.
6. Dark mode: ink hero stays ink; cards flip correctly.

---

## Self-Review (completed at plan-writing time)

- **Spec coverage:** §2 definitions → Tasks 1, 3–5; §3.1 → 3+10; §3.2 → 4+11; §3.3 → 5+12 (+7 for strip data); §3.4 → 5+13; §3.5 → 5+14; §3.6 → 6+7+14; §4 → 6; §5.1 → 1; §5.2 → 2; §6 wiring → 8–9; §7 → per-task tests + Task 15. No gaps.
- **Type consistency:** `OverviewKpis`/`WeekBin`/`CompletionTime`/`PriorityPair`/`StatusSlice`/`TeamRow`/`MemberHealth`/`AttentionItem`/`AttentionClass`/`WsActivityItem`/`WsActivityState` names match across producing and consuming tasks.
- **Placeholders:** none; two deliberate verify-against-source steps (LayerChart prop names in Task 11, `activityLabel` signature in Task 14) include concrete fallback instructions.
