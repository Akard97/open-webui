# WorkOS Timeline View (Gantt) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an interactive planning Gantt ("Timeline" tab) to WorkOS: bold status-colored bars per task, drag to move/resize dates, unscheduled rail with drag-to-schedule, Week/Month/Quarter zoom, view-only on mobile.

**Architecture:** Hand-rolled Svelte view (`TimelineView` + small `views/timeline/*` components) over a pure, unit-tested date-math module `lib/timeline.ts`. Tasks come from the existing `filteredTasks` derived store; all edits go through the existing optimistic `editTask`/`addTask` store actions, so filters and realtime work with zero new wiring. No backend changes.

**Tech Stack:** Svelte 5 (runes syntax like the rest of WorkOS: `onclick=`, `$:` reactive statements), Tailwind utility classes inline, vitest for the lib, existing WorkOS primitives (`FilterBar`, `Icon`, `StatusDot`, `AssigneeAvatars`, `TaskHoverCard`, shadcn `HoverCard`).

**Spec:** `docs/superpowers/specs/2026-07-09-workos-timeline-view-design.md`

## Global Constraints

- **Never start a Vite dev server** — browser smoke is a manual follow-up done by the user (standing project rule).
- **Date storage convention (load-bearing):** `Task.start_date`/`due_date` are ms timestamps at **UTC midnight of the picked calendar date** (`DueDateCell` commits `new Date('YYYY-MM-DD').getTime()`; see the comment in `src/lib/components/workos/lib/progress.ts:28-30`). All timeline math uses integer **UTC day indexes** (`Math.floor(ts / 86_400_000)`); writing back is `dayIndex * 86_400_000`. Header labels use `getUTC*` / `timeZone: 'UTC'` formatting. Today's index encodes the viewer's **local** calendar date as UTC (`Date.UTC(localY, localM, localD) / DAY_MS`), matching what the date picker writes for "today".
- **Canceled tasks are excluded** from the chart and the unscheduled rail (Board/List parity).
- **No client-side permission gating on drags** — existing precedent (List cells, Board/Calendar drag). Attempt optimistically; on server 403 `editTask` rolls back and we toast.
- Accent color is the Osool teal `--primary` (`bg-primary`, `text-primary`); status colors from `STATUS_COLOR`, priority colors from `PRIORITY_COLOR` (`lib/colors.ts`). Every new surface needs `dark:` variants.
- Commit style: `feat(workos): …` / `test(workos): …` subjects, imperative.
- Verification commands: `npm run test:frontend -- run <file>` (vitest single file), `npm run check` (svelte-check). Both must be clean before each commit that touches their scope.
- All new files live under `src/lib/components/workos/` (components) — paths below are relative to repo root.

---

### Task 1: `lib/timeline.ts` — day encoding, classification, sort, window

**Files:**
- Create: `src/lib/components/workos/lib/timeline.ts`
- Create: `src/lib/components/workos/lib/timeline.test.ts`

**Interfaces:**
- Consumes: `Task` type from `./types`.
- Produces (used by Tasks 2, 3, 5, 6, 7):
  - `DAY_MS: number` (86_400_000)
  - `tsToDay(ts: number): number`, `dayToTs(day: number): number`, `todayDay(now: number): number`
  - `type TimelineKind = 'bar' | 'milestone' | 'unscheduled'`
  - `interface TimelineItem { task: Task; kind: 'bar' | 'milestone'; startDay: number; endDay: number }` (day indexes, **inclusive** ends)
  - `classifyTask(t: Task): TimelineKind`
  - `timelineItems(tasks: Task[]): TimelineItem[]` (excludes canceled + unscheduled; sorted)
  - `unscheduledTasks(tasks: Task[]): Task[]` (excludes canceled)
  - `interface TimelineWindow { startDay: number; endDay: number; days: number }`, `MIN_WINDOW_DAYS = 42`, `computeWindow(items: TimelineItem[], today: number): TimelineWindow`

- [ ] **Step 1: Write the failing tests**

Create `src/lib/components/workos/lib/timeline.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import type { Task } from './types';
import {
	DAY_MS, tsToDay, dayToTs, todayDay,
	classifyTask, timelineItems, unscheduledTasks,
	computeWindow, MIN_WINDOW_DAYS
} from './timeline';

// Minimal task factory — only the fields the timeline math reads.
export function makeTask(over: Partial<Task> = {}): Task {
	return {
		id: over.id ?? 't1', workstream_id: 'ws1', team_id: 'tm1', number: 1, key: 'T-1',
		title: 'Task', status: 'todo', priority: null, assignee_ids: [],
		start_date: null, due_date: null, progress: 0, labels: [], sort_key: 0,
		created_by_id: null, completed_at: null, created_at: 0, updated_at: 0,
		...over
	} as Task;
}

// Day index for an ISO date (tests use exact UTC midnights, like storage).
const D = (iso: string) => {
	const [y, m, d] = iso.split('-').map(Number);
	return Date.UTC(y, m - 1, d) / DAY_MS;
};

describe('day encoding', () => {
	it('round-trips UTC midnights', () => {
		const ts = Date.UTC(2026, 6, 9); // 2026-07-09T00:00Z
		expect(tsToDay(ts)).toBe(ts / DAY_MS);
		expect(dayToTs(tsToDay(ts))).toBe(ts);
	});
	it('floors timestamps that carry a time component', () => {
		const noon = Date.UTC(2026, 6, 9, 12, 30);
		expect(tsToDay(noon)).toBe(Date.UTC(2026, 6, 9) / DAY_MS);
	});
	it('todayDay encodes the LOCAL calendar date as a UTC day index', () => {
		const now = new Date(2026, 6, 9, 23, 30).getTime(); // 11:30pm local, July 9
		expect(todayDay(now)).toBe(Date.UTC(2026, 6, 9) / DAY_MS);
	});
});

describe('classifyTask', () => {
	it('start+due → bar', () => {
		expect(classifyTask(makeTask({ start_date: dayToTs(D('2026-07-01')), due_date: dayToTs(D('2026-07-05')) }))).toBe('bar');
	});
	it('start-only → bar (1-day)', () => {
		expect(classifyTask(makeTask({ start_date: dayToTs(D('2026-07-01')) }))).toBe('bar');
	});
	it('due-only → milestone', () => {
		expect(classifyTask(makeTask({ due_date: dayToTs(D('2026-07-05')) }))).toBe('milestone');
	});
	it('dateless → unscheduled', () => {
		expect(classifyTask(makeTask())).toBe('unscheduled');
	});
});

describe('timelineItems', () => {
	const s = D('2026-07-01'), e = D('2026-07-05');
	it('builds inclusive day ranges and drops canceled + unscheduled', () => {
		const items = timelineItems([
			makeTask({ id: 'a', start_date: dayToTs(s), due_date: dayToTs(e) }),
			makeTask({ id: 'b' }), // unscheduled
			makeTask({ id: 'c', status: 'canceled', start_date: dayToTs(s), due_date: dayToTs(e) })
		]);
		expect(items.map((i) => i.task.id)).toEqual(['a']);
		expect(items[0]).toMatchObject({ kind: 'bar', startDay: s, endDay: e });
	});
	it('start-only → 1-day bar; due-only → milestone on its day', () => {
		const items = timelineItems([
			makeTask({ id: 'a', start_date: dayToTs(s) }),
			makeTask({ id: 'b', due_date: dayToTs(e) })
		]);
		expect(items.find((i) => i.task.id === 'a')).toMatchObject({ kind: 'bar', startDay: s, endDay: s });
		expect(items.find((i) => i.task.id === 'b')).toMatchObject({ kind: 'milestone', startDay: e, endDay: e });
	});
	it('clamps due-before-start to a 1-day bar at start', () => {
		const items = timelineItems([makeTask({ start_date: dayToTs(e), due_date: dayToTs(s) })]);
		expect(items[0]).toMatchObject({ startDay: e, endDay: e });
	});
	it('sorts by startDay, then endDay, then title', () => {
		const items = timelineItems([
			makeTask({ id: 'late', title: 'B', start_date: dayToTs(s + 2), due_date: dayToTs(e) }),
			makeTask({ id: 'longer', title: 'Z', start_date: dayToTs(s), due_date: dayToTs(e + 1) }),
			makeTask({ id: 'first', title: 'A', start_date: dayToTs(s), due_date: dayToTs(e) })
		]);
		expect(items.map((i) => i.task.id)).toEqual(['first', 'longer', 'late']);
	});
});

describe('unscheduledTasks', () => {
	it('returns dateless, non-canceled tasks only', () => {
		const out = unscheduledTasks([
			makeTask({ id: 'a' }),
			makeTask({ id: 'b', status: 'canceled' }),
			makeTask({ id: 'c', due_date: dayToTs(D('2026-07-05')) })
		]);
		expect(out.map((t) => t.id)).toEqual(['a']);
	});
});

describe('computeWindow', () => {
	const today = D('2026-07-09');
	it('pads 7 days before the min and 14 after the max', () => {
		const items = timelineItems([
			makeTask({ start_date: dayToTs(D('2026-07-01')), due_date: dayToTs(D('2026-08-20')) })
		]);
		const w = computeWindow(items, today);
		expect(w.startDay).toBe(D('2026-07-01') - 7);
		expect(w.endDay).toBe(D('2026-08-20') + 14);
		expect(w.days).toBe(w.endDay - w.startDay + 1);
	});
	it('always contains today and enforces the minimum width', () => {
		const w = computeWindow([], today);
		expect(w.startDay).toBeLessThanOrEqual(today);
		expect(w.endDay).toBeGreaterThanOrEqual(today);
		expect(w.days).toBeGreaterThanOrEqual(MIN_WINDOW_DAYS);
	});
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm run test:frontend -- run src/lib/components/workos/lib/timeline.test.ts`
Expected: FAIL — `Cannot find module './timeline'` (or equivalent resolve error).

- [ ] **Step 3: Write the implementation**

Create `src/lib/components/workos/lib/timeline.ts`:

```ts
import type { Task } from './types';

// ── Day encoding ────────────────────────────────────────────────────────────
// start_date/due_date are stored as UTC midnight of the picked calendar date
// (see progress.ts). A "day" here is the integer UTC day index ts / DAY_MS.
export const DAY_MS = 86_400_000;

export function tsToDay(ts: number): number {
	return Math.floor(ts / DAY_MS);
}
export function dayToTs(day: number): number {
	return day * DAY_MS;
}
/** The viewer's local calendar date, encoded as a UTC day index — the same
 * value the date picker would store for "today". */
export function todayDay(now: number): number {
	const d = new Date(now);
	return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / DAY_MS;
}

// ── Classification ──────────────────────────────────────────────────────────
export type TimelineKind = 'bar' | 'milestone' | 'unscheduled';

export interface TimelineItem {
	task: Task;
	kind: 'bar' | 'milestone';
	startDay: number; // inclusive
	endDay: number; // inclusive; === startDay for milestones and 1-day bars
}

export function classifyTask(t: Task): TimelineKind {
	if (t.start_date != null) return 'bar';
	if (t.due_date != null) return 'milestone';
	return 'unscheduled';
}

/** Chart rows: scheduled, non-canceled tasks as inclusive day ranges, sorted
 * by start, then end, then title. */
export function timelineItems(tasks: Task[]): TimelineItem[] {
	const items: TimelineItem[] = [];
	for (const t of tasks) {
		if (t.status === 'canceled') continue;
		const kind = classifyTask(t);
		if (kind === 'unscheduled') continue;
		if (kind === 'milestone') {
			const d = tsToDay(t.due_date as number);
			items.push({ task: t, kind, startDay: d, endDay: d });
		} else {
			const s = tsToDay(t.start_date as number);
			const e = t.due_date != null ? Math.max(s, tsToDay(t.due_date)) : s;
			items.push({ task: t, kind: 'bar', startDay: s, endDay: e });
		}
	}
	return items.sort(
		(a, b) =>
			a.startDay - b.startDay || a.endDay - b.endDay || a.task.title.localeCompare(b.task.title)
	);
}

export function unscheduledTasks(tasks: Task[]): Task[] {
	return tasks.filter((t) => t.status !== 'canceled' && classifyTask(t) === 'unscheduled');
}

// ── Window ──────────────────────────────────────────────────────────────────
export interface TimelineWindow {
	startDay: number;
	endDay: number;
	days: number;
}

export const MIN_WINDOW_DAYS = 42;

/** [min − 7d, max + 14d], always containing today, at least MIN_WINDOW_DAYS wide. */
export function computeWindow(items: TimelineItem[], today: number): TimelineWindow {
	let lo = today;
	let hi = today;
	for (const it of items) {
		lo = Math.min(lo, it.startDay);
		hi = Math.max(hi, it.endDay);
	}
	lo -= 7;
	hi += 14;
	if (hi - lo + 1 < MIN_WINDOW_DAYS) hi = lo + MIN_WINDOW_DAYS - 1;
	return { startDay: lo, endDay: hi, days: hi - lo + 1 };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:frontend -- run src/lib/components/workos/lib/timeline.test.ts`
Expected: PASS (all tests green).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/timeline.ts src/lib/components/workos/lib/timeline.test.ts
git commit -m "feat(workos): timeline day math - encoding, classification, window"
```

---

### Task 2: `lib/timeline.ts` — zoom scale, geometry, header helpers

**Files:**
- Modify: `src/lib/components/workos/lib/timeline.ts` (append)
- Modify: `src/lib/components/workos/lib/timeline.test.ts` (append)

**Interfaces:**
- Consumes: Task 1's `TimelineItem`, `TimelineWindow`, `DAY_MS`.
- Produces (used by Tasks 4, 5, 6, 7):
  - `type ZoomKey = 'week' | 'month' | 'quarter'`, `ZOOM_ORDER: ZoomKey[]`, `ZOOM_DAY_WIDTH: Record<ZoomKey, number>` (`{ week: 48, month: 24, quarter: 8 }`)
  - `parseZoom(raw: string | null): ZoomKey` (invalid → `'month'`)
  - `dayToX(day, win, dayWidth): number`, `xToDay(x, win, dayWidth): number`, `todayLineX(today, win, dayWidth): number`
  - `interface BarGeom { left: number; width: number; slipWidth: number }`, `barGeometry(item, win, dayWidth, today): BarGeom`
  - `utcDate(day): Date`, `isWeekend(day): boolean`, `isWeekStart(day): boolean` (Monday), `dayNumber(day): number`, `weekdayShort(day): string`
  - `interface MonthSpan { label: string; startDay: number; days: number }`, `monthSpans(win): MonthSpan[]`

- [ ] **Step 1: Append the failing tests**

Append to `src/lib/components/workos/lib/timeline.test.ts` (add the new imports to the existing import statement from `./timeline`: `ZOOM_DAY_WIDTH, parseZoom, dayToX, xToDay, todayLineX, barGeometry, isWeekend, isWeekStart, dayNumber, monthSpans`):

```ts
describe('zoom + scale', () => {
	it('parseZoom accepts the three presets and defaults to month', () => {
		expect(parseZoom('week')).toBe('week');
		expect(parseZoom('quarter')).toBe('quarter');
		expect(parseZoom(null)).toBe('month');
		expect(parseZoom('bogus')).toBe('month');
	});
	it('dayToX/xToDay round-trip at every preset width', () => {
		const win = { startDay: 100, endDay: 199, days: 100 };
		for (const w of Object.values(ZOOM_DAY_WIDTH)) {
			expect(dayToX(107, win, w)).toBe(7 * w);
			expect(xToDay(7 * w, win, w)).toBe(107);
			expect(xToDay(7 * w + w - 1, win, w)).toBe(107); // anywhere in the column
		}
	});
	it('todayLineX sits mid-column', () => {
		const win = { startDay: 100, endDay: 199, days: 100 };
		expect(todayLineX(107, win, 24)).toBe(7 * 24 + 12);
	});
});

describe('barGeometry', () => {
	const win = { startDay: 100, endDay: 199, days: 100 };
	const w = 24;
	it('bar spans inclusive days', () => {
		const item = { task: makeTask({ status: 'in_progress' }), kind: 'bar' as const, startDay: 110, endDay: 114 };
		const g = barGeometry(item, win, w, 120);
		expect(g.left).toBe(10 * w);
		expect(g.width).toBe(5 * w); // 5 inclusive days
	});
	it('open + past-due grows a slip tail up to the today line', () => {
		const item = { task: makeTask({ status: 'in_progress' }), kind: 'bar' as const, startDay: 110, endDay: 114 };
		const g = barGeometry(item, win, w, 120);
		// tail: from bar end (day 115 boundary) to mid-column of day 120
		expect(g.slipWidth).toBe(todayLineX(120, win, w) - (g.left + g.width));
		expect(g.slipWidth).toBeGreaterThan(0);
	});
	it('done tasks and future tasks have no slip', () => {
		const done = { task: makeTask({ status: 'done' }), kind: 'bar' as const, startDay: 110, endDay: 114 };
		expect(barGeometry(done, win, w, 120).slipWidth).toBe(0);
		const future = { task: makeTask({ status: 'todo' }), kind: 'bar' as const, startDay: 130, endDay: 134 };
		expect(barGeometry(future, win, w, 120).slipWidth).toBe(0);
	});
	it('due today → no slip (the due day is not overdue)', () => {
		const item = { task: makeTask({ status: 'todo' }), kind: 'bar' as const, startDay: 118, endDay: 120 };
		expect(barGeometry(item, win, w, 120).slipWidth).toBe(0);
	});
});

describe('header helpers', () => {
	it('weekend/week-start use UTC weekdays', () => {
		const sat = Date.UTC(2026, 6, 11) / DAY_MS; // 2026-07-11 = Saturday
		expect(isWeekend(sat)).toBe(true);
		expect(isWeekend(sat + 1)).toBe(true); // Sunday
		expect(isWeekend(sat + 2)).toBe(false); // Monday
		expect(isWeekStart(sat + 2)).toBe(true);
	});
	it('dayNumber reads the UTC date', () => {
		expect(dayNumber(Date.UTC(2026, 6, 9) / DAY_MS)).toBe(9);
	});
	it('monthSpans groups the window by UTC month with day counts', () => {
		const start = Date.UTC(2026, 5, 28) / DAY_MS; // Jun 28
		const win = { startDay: start, endDay: start + 9, days: 10 }; // Jun 28 – Jul 7
		const spans = monthSpans(win);
		expect(spans).toEqual([
			{ label: 'June 2026', startDay: start, days: 3 },
			{ label: 'July 2026', startDay: start + 3, days: 7 }
		]);
	});
});
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `npm run test:frontend -- run src/lib/components/workos/lib/timeline.test.ts`
Expected: FAIL — new symbols not exported (`parseZoom is not a function` or import error). Task 1 tests still pass.

- [ ] **Step 3: Append the implementation**

Append to `src/lib/components/workos/lib/timeline.ts`:

```ts
// ── Zoom ────────────────────────────────────────────────────────────────────
export type ZoomKey = 'week' | 'month' | 'quarter';
export const ZOOM_ORDER: ZoomKey[] = ['week', 'month', 'quarter'];
export const ZOOM_DAY_WIDTH: Record<ZoomKey, number> = { week: 48, month: 24, quarter: 8 };

export function parseZoom(raw: string | null): ZoomKey {
	return raw === 'week' || raw === 'month' || raw === 'quarter' ? raw : 'month';
}

// ── Scale ───────────────────────────────────────────────────────────────────
export function dayToX(day: number, win: TimelineWindow, dayWidth: number): number {
	return (day - win.startDay) * dayWidth;
}
export function xToDay(x: number, win: TimelineWindow, dayWidth: number): number {
	return win.startDay + Math.floor(x / dayWidth);
}
/** The today marker sits mid-column of today's day. */
export function todayLineX(today: number, win: TimelineWindow, dayWidth: number): number {
	return dayToX(today, win, dayWidth) + dayWidth / 2;
}

// ── Geometry ────────────────────────────────────────────────────────────────
export interface BarGeom {
	left: number;
	width: number;
	/** Hatched overdue tail after the bar, 0 when not overdue. */
	slipWidth: number;
}

export function barGeometry(
	item: TimelineItem,
	win: TimelineWindow,
	dayWidth: number,
	today: number
): BarGeom {
	const left = dayToX(item.startDay, win, dayWidth);
	const width = (item.endDay - item.startDay + 1) * dayWidth;
	const open = item.task.status !== 'done' && item.task.status !== 'canceled';
	const slipWidth =
		open && item.endDay < today
			? Math.max(0, todayLineX(today, win, dayWidth) - (left + width))
			: 0;
	return { left, width, slipWidth };
}

// ── Header helpers (all UTC — matches the storage convention) ───────────────
export function utcDate(day: number): Date {
	return new Date(day * DAY_MS);
}
export function isWeekend(day: number): boolean {
	const wd = utcDate(day).getUTCDay();
	return wd === 0 || wd === 6;
}
export function isWeekStart(day: number): boolean {
	return utcDate(day).getUTCDay() === 1; // Monday
}
export function dayNumber(day: number): number {
	return utcDate(day).getUTCDate();
}
export function weekdayShort(day: number): string {
	return utcDate(day).toLocaleDateString('en-US', { weekday: 'short', timeZone: 'UTC' });
}

export interface MonthSpan {
	label: string;
	startDay: number;
	days: number;
}
export function monthSpans(win: TimelineWindow): MonthSpan[] {
	const spans: MonthSpan[] = [];
	for (let d = win.startDay; d <= win.endDay; d++) {
		const label = utcDate(d).toLocaleDateString('en-US', {
			month: 'long',
			year: 'numeric',
			timeZone: 'UTC'
		});
		const last = spans[spans.length - 1];
		if (last && last.label === label) last.days += 1;
		else spans.push({ label, startDay: d, days: 1 });
	}
	return spans;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:frontend -- run src/lib/components/workos/lib/timeline.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/timeline.ts src/lib/components/workos/lib/timeline.test.ts
git commit -m "feat(workos): timeline zoom scale, bar geometry, header helpers"
```

---

### Task 3: `lib/timeline.ts` — drag edit helpers (`applyMove` / `applyResize`)

**Files:**
- Modify: `src/lib/components/workos/lib/timeline.ts` (append)
- Modify: `src/lib/components/workos/lib/timeline.test.ts` (append)

**Interfaces:**
- Consumes: Task 1's `TimelineItem`, `tsToDay`, `dayToTs`.
- Produces (used by Task 6):
  - `interface DatePatch { start_date?: number | null; due_date?: number | null }`
  - `applyMove(item: TimelineItem, dayDelta: number): DatePatch` — shifts whichever of the two dates exist; absent dates stay absent.
  - `applyResize(item: TimelineItem, edge: 'start' | 'end', dayDelta: number): DatePatch` — moves one edge, clamped so start ≤ end (1-day minimum). `edge:'start'` on a milestone **creates** a `start_date`; `edge:'end'` on a start-only bar **creates** a `due_date`.

- [ ] **Step 1: Append the failing tests**

Append to `src/lib/components/workos/lib/timeline.test.ts` (extend the `./timeline` import with `applyMove, applyResize`):

```ts
describe('applyMove', () => {
	const s = D('2026-07-01'), e = D('2026-07-05');
	it('shifts both dates of a full bar', () => {
		const item = timelineItems([makeTask({ start_date: dayToTs(s), due_date: dayToTs(e) })])[0];
		expect(applyMove(item, 3)).toEqual({ start_date: dayToTs(s + 3), due_date: dayToTs(e + 3) });
		expect(applyMove(item, -2)).toEqual({ start_date: dayToTs(s - 2), due_date: dayToTs(e - 2) });
	});
	it('start-only bar moves only start_date', () => {
		const item = timelineItems([makeTask({ start_date: dayToTs(s) })])[0];
		expect(applyMove(item, 4)).toEqual({ start_date: dayToTs(s + 4) });
	});
	it('milestone moves only due_date', () => {
		const item = timelineItems([makeTask({ due_date: dayToTs(e) })])[0];
		expect(applyMove(item, -1)).toEqual({ due_date: dayToTs(e - 1) });
	});
});

describe('applyResize', () => {
	const s = D('2026-07-01'), e = D('2026-07-05');
	const bar = () => timelineItems([makeTask({ start_date: dayToTs(s), due_date: dayToTs(e) })])[0];
	it('start edge moves start_date only', () => {
		expect(applyResize(bar(), 'start', 2)).toEqual({ start_date: dayToTs(s + 2) });
	});
	it('end edge moves due_date only', () => {
		expect(applyResize(bar(), 'end', -1)).toEqual({ due_date: dayToTs(e - 1) });
	});
	it('clamps to a 1-day minimum (start cannot pass end, end cannot pass start)', () => {
		expect(applyResize(bar(), 'start', 99)).toEqual({ start_date: dayToTs(e) });
		expect(applyResize(bar(), 'end', -99)).toEqual({ due_date: dayToTs(s) });
	});
	it('end edge on a start-only bar creates a due_date ≥ start', () => {
		const item = timelineItems([makeTask({ start_date: dayToTs(s) })])[0];
		expect(applyResize(item, 'end', 3)).toEqual({ due_date: dayToTs(s + 3) });
		expect(applyResize(item, 'end', -5)).toEqual({ due_date: dayToTs(s) });
	});
	it('start edge on a milestone creates a start_date ≤ due', () => {
		const item = timelineItems([makeTask({ due_date: dayToTs(e) })])[0];
		expect(applyResize(item, 'start', -3)).toEqual({ start_date: dayToTs(e - 3) });
		expect(applyResize(item, 'start', 4)).toEqual({ start_date: dayToTs(e) });
	});
});
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `npm run test:frontend -- run src/lib/components/workos/lib/timeline.test.ts`
Expected: FAIL — `applyMove is not a function` (import error). Earlier tests pass.

- [ ] **Step 3: Append the implementation**

Append to `src/lib/components/workos/lib/timeline.ts`:

```ts
// ── Drag edits ──────────────────────────────────────────────────────────────
export interface DatePatch {
	start_date?: number | null;
	due_date?: number | null;
}

/** Shift the whole item by dayDelta. Only fields the task actually has are
 * returned, so a start-only bar never gains a due date from a move. */
export function applyMove(item: TimelineItem, dayDelta: number): DatePatch {
	const p: DatePatch = {};
	if (item.task.start_date != null) p.start_date = dayToTs(tsToDay(item.task.start_date) + dayDelta);
	if (item.task.due_date != null) p.due_date = dayToTs(tsToDay(item.task.due_date) + dayDelta);
	return p;
}

/** Move one edge by dayDelta, clamped so the item never inverts (1-day min).
 * Creates the missing date when resizing the open side of a one-sided item. */
export function applyResize(item: TimelineItem, edge: 'start' | 'end', dayDelta: number): DatePatch {
	if (edge === 'start') {
		return { start_date: dayToTs(Math.min(item.startDay + dayDelta, item.endDay)) };
	}
	return { due_date: dayToTs(Math.max(item.endDay + dayDelta, item.startDay)) };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm run test:frontend -- run src/lib/components/workos/lib/timeline.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/timeline.ts src/lib/components/workos/lib/timeline.test.ts
git commit -m "feat(workos): timeline drag edit helpers (applyMove/applyResize)"
```

---

### Task 4: Plumbing — view key, zoom store, icon, Topbar tab, route + placeholder view

**Files:**
- Modify: `src/lib/components/workos/lib/store.ts` (two edits)
- Modify: `src/lib/components/workos/ui/Icon.svelte` (one glyph)
- Modify: `src/lib/components/workos/chrome/Topbar.svelte` (tab list)
- Modify: `src/lib/components/workos/WorkOSApp.svelte` (route)
- Create: `src/lib/components/workos/views/TimelineView.svelte` (placeholder — replaced in Task 5)

**Interfaces:**
- Consumes: `parseZoom`, `ZoomKey` from Task 2.
- Produces (used by Tasks 5–8):
  - `ViewKey` union includes `'timeline'`.
  - `timelineZoom: Writable<ZoomKey>` exported from `lib/store.ts`, persisted under `localStorage['workos:timeline-zoom']`.
  - Icon name `'chart-gantt'` renders.
  - Topbar shows a live Timeline tab; `WorkOSApp` renders `TimelineView` for `$view === 'timeline'` and shows the `Topbar` for it.

- [ ] **Step 1: Extend the store**

In `src/lib/components/workos/lib/store.ts`:

(a) Change the `ViewKey` union (line ~18):

```ts
export type ViewKey = 'board' | 'list' | 'admin' | 'inbox' | 'mywork' | 'calendar' | 'overview' | 'timeline';
```

(b) Add the import at the top, next to the `./columns` import:

```ts
import { parseZoom, type ZoomKey } from './timeline';
```

(c) Add the persisted zoom store directly below the `listColumns` block (line ~80), mirroring its pattern:

```ts
// Timeline zoom preset, persisted per browser like the list columns.
const TIMELINE_ZOOM_KEY = 'workos:timeline-zoom';
export const timelineZoom: Writable<ZoomKey> = writable(
	browser ? parseZoom(localStorage.getItem(TIMELINE_ZOOM_KEY)) : 'month'
);
if (browser) timelineZoom.subscribe((v) => localStorage.setItem(TIMELINE_ZOOM_KEY, v));
```

- [ ] **Step 2: Add the gantt glyph**

In `src/lib/components/workos/ui/Icon.svelte`, add to the `LUCIDE` record (e.g. after `columns`):

```ts
'chart-gantt': '<path d="M10 6h8"/><path d="M12 16h6"/><path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="M8 11h7"/>',
```

- [ ] **Step 3: Add the Topbar tab**

In `src/lib/components/workos/chrome/Topbar.svelte`, insert the Timeline entry into `TABS` between Board and Calendar, and widen the `selectTab` cast:

```ts
const TABS = [
	{ key: 'overview', label: 'Overview', icon: 'layers', live: true },
	{ key: 'list', label: 'List', icon: 'list', live: true },
	{ key: 'board', label: 'Board', icon: 'columns', live: true },
	{ key: 'timeline', label: 'Timeline', icon: 'chart-gantt', live: true },
	{ key: 'calendar', label: 'Calendar', icon: 'calendar', live: true },
	{ key: 'files', label: 'Files', icon: 'paperclip', live: false }
];
function selectTab(t: (typeof TABS)[number]) {
	if (t.live) view.set(t.key as 'board' | 'list' | 'calendar' | 'overview' | 'timeline');
}
```

- [ ] **Step 4: Create the placeholder view and route it**

Create `src/lib/components/workos/views/TimelineView.svelte`:

```svelte
<script lang="ts">
	import FilterBar from '../chrome/FilterBar.svelte';
	import { boardFilter } from '../lib/store';
</script>

<div class="h-full flex flex-col min-h-0">
	<FilterBar filter={boardFilter} />
	<div class="flex-1 flex items-center justify-center text-sm text-gray-400">Timeline</div>
</div>
```

In `src/lib/components/workos/WorkOSApp.svelte`:

(a) Add the import next to `CalendarView`:

```ts
import TimelineView from './views/TimelineView.svelte';
```

(b) Extend the Topbar condition (line ~50):

```svelte
{#if $view === 'board' || $view === 'list' || $view === 'calendar' || $view === 'overview' || $view === 'timeline'}
```

(c) Add the view branch next to the calendar branch:

```svelte
{:else if $view === 'timeline'}
	<TimelineView />
```

- [ ] **Step 5: Verify types and existing tests**

Run: `npm run check`
Expected: no new errors (same baseline as before the change).
Run: `npm run test:frontend -- run src/lib/components/workos/lib/store.test.ts`
Expected: PASS (store suite unaffected).

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/lib/store.ts src/lib/components/workos/ui/Icon.svelte src/lib/components/workos/chrome/Topbar.svelte src/lib/components/workos/WorkOSApp.svelte src/lib/components/workos/views/TimelineView.svelte
git commit -m "feat(workos): timeline tab, view routing, persisted zoom store"
```

---

### Task 5: Static chart — header, rail, read-only bars

**Files:**
- Create: `src/lib/components/workos/views/timeline/TimelineHeader.svelte`
- Create: `src/lib/components/workos/views/timeline/TimelineRail.svelte`
- Create: `src/lib/components/workos/views/timeline/TimelineBar.svelte` (read-only; drag added in Task 6)
- Modify: `src/lib/components/workos/views/TimelineView.svelte` (replace placeholder)

**Interfaces:**
- Consumes: everything from Tasks 1–2 and 4; `STATUS_COLOR`, `statusShape` (`lib/colors`), `actualProgress` (`lib/progress`), `formatDateRange`, `formatDateShort` (`lib/format`), `STATUS_LABEL` (`lib/types`), `initials`, `openTask` (`lib/store`), `AssigneeAvatars`, `TaskHoverCard`, shadcn `HoverCard`.
- Produces (consumed by Tasks 6–8):
  - `TimelineHeader` props: `win: TimelineWindow`, `dayWidth: number`, `zoom: ZoomKey`, `today: number`, `railW: number`.
  - `TimelineRail` props: `item: TimelineItem`, `today: number`, `compact = false` (mobile single-line, used in Task 8).
  - `TimelineBar` props: `item: TimelineItem`, `win: TimelineWindow`, `dayWidth: number`, `today: number` (Task 6 adds `scroller`, `disabled`).
  - `TimelineView` exposes the layout constants `RAIL_W = 260`, `ROW_H = 46` and renders rows from `timelineItems($filteredTasks)`.

- [ ] **Step 1: Create `TimelineHeader.svelte`**

`src/lib/components/workos/views/timeline/TimelineHeader.svelte`:

```svelte
<script lang="ts">
	import {
		monthSpans, dayNumber, weekdayShort, isWeekend, isWeekStart,
		type TimelineWindow, type ZoomKey
	} from '../../lib/timeline';

	export let win: TimelineWindow;
	export let dayWidth: number;
	export let zoom: ZoomKey;
	export let today: number;
	export let railW: number;

	$: spans = monthSpans(win);
	$: days = Array.from({ length: win.days }, (_, i) => win.startDay + i);
</script>

<!-- Sticky under the toolbar while the rows scroll vertically. z-30 keeps it
     above the rows' sticky rail cells (z-20), which are later in the DOM. -->
<div class="sticky top-0 z-30 flex bg-gray-50 dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800" style="width: {railW + win.days * dayWidth}px;">
	<!-- Corner cell: sticky on the horizontal axis too -->
	<div class="sticky left-0 z-10 flex-none flex items-end px-3 pb-1.5 bg-gray-50 dark:bg-gray-900 border-r border-gray-200 dark:border-gray-800 text-[10px] font-semibold tracking-wider text-gray-400 uppercase" style="width: {railW}px;">
		Task
	</div>
	<div class="flex-none">
		<!-- Month band -->
		<div class="flex h-5">
			{#each spans as s (s.startDay)}
				<div class="flex-none px-2 text-[10px] font-bold tracking-wide text-gray-500 dark:text-gray-400 uppercase overflow-hidden whitespace-nowrap border-r border-gray-200/60 dark:border-gray-800/60" style="width: {s.days * dayWidth}px;">
					{s.label}
				</div>
			{/each}
		</div>
		<!-- Day row -->
		<div class="flex h-6">
			{#each days as d (d)}
				{@const showLabel = zoom === 'quarter' ? isWeekStart(d) : true}
				<div
					class="flex-none flex items-center justify-center text-[10px] font-semibold {isWeekend(d) ? 'text-gray-300 dark:text-gray-600' : 'text-gray-500 dark:text-gray-400'}"
					style="width: {dayWidth}px;"
				>
					{#if d === today}
						<span class="inline-flex items-center justify-center min-w-[18px] h-[16px] px-1 rounded-full bg-primary text-primary-foreground">{dayNumber(d)}</span>
					{:else if showLabel}
						<span class="truncate">{zoom === 'week' ? `${weekdayShort(d)} ${dayNumber(d)}` : dayNumber(d)}</span>
					{/if}
				</div>
			{/each}
		</div>
	</div>
</div>
```

- [ ] **Step 2: Create `TimelineRail.svelte`**

`src/lib/components/workos/views/timeline/TimelineRail.svelte`:

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { STATUS_COLOR, PRIORITY_COLOR } from '../../lib/colors';
	import { formatDateRange } from '../../lib/format';
	import { openTask } from '../../lib/store';
	import type { TimelineItem } from '../../lib/timeline';

	export let item: TimelineItem;
	export let today: number;
	export let compact = false; // mobile: single line, no meta row

	$: t = item.task;
	$: daysLate =
		t.status !== 'done' && t.status !== 'canceled' && item.endDay < today
			? today - item.endDay
			: 0;
	$: range = formatDateRange(t.start_date, t.due_date);
</script>

<div class="h-full min-w-0 px-3 flex flex-col justify-center gap-0.5">
	<span class="flex items-center gap-2 min-w-0">
		<span class="flex-none w-2 h-2 rounded-full" style="background:{STATUS_COLOR[t.status]}"></span>
		<button
			class="text-[13px] font-semibold text-gray-900 dark:text-gray-100 truncate text-left hover:text-primary"
			onclick={() => openTask(t.id)}
		>{t.title}</button>
	</span>
	{#if !compact}
		<span class="pl-4 flex items-center gap-1.5 text-[11px] {daysLate ? 'text-red-600 dark:text-red-400 font-medium' : 'text-gray-400 dark:text-gray-500'} whitespace-nowrap overflow-hidden">
			{#if range}<span class="truncate">{range}</span>{/if}
			{#if daysLate}<span class="flex-none">· {daysLate}d overdue</span>{/if}
			{#if t.priority}
				<span class="flex-none inline-flex items-center gap-0.5" style="color:{PRIORITY_COLOR[t.priority]}">
					<Icon name="flag" size={11} /> {t.priority[0].toUpperCase() + t.priority.slice(1)}
				</span>
			{/if}
		</span>
	{/if}
</div>
```

- [ ] **Step 3: Create the read-only `TimelineBar.svelte`**

`src/lib/components/workos/views/timeline/TimelineBar.svelte`:

```svelte
<script lang="ts">
	import { STATUS_COLOR } from '../../lib/colors';
	import { STATUS_LABEL } from '../../lib/types';
	import { actualProgress } from '../../lib/progress';
	import { barGeometry, type TimelineItem, type TimelineWindow } from '../../lib/timeline';
	import { openTask, initials, currentWorkstream } from '../../lib/store';
	import * as HoverCard from '$lib/components/ui/hover-card';
	import TaskHoverCard from '../TaskHoverCard.svelte';

	export let item: TimelineItem;
	export let win: TimelineWindow;
	export let dayWidth: number;
	export let today: number;

	$: t = item.task;
	$: color = STATUS_COLOR[t.status];
	$: geom = barGeometry(item, win, dayWidth, today);
	$: pct = actualProgress(t);
	$: daysLate = today - item.endDay;
	$: stateText =
		t.status === 'done' ? '✓ Done' : t.status === 'in_progress' && pct > 0 ? `${pct}%` : STATUS_LABEL[t.status];
</script>

<HoverCard.Root openDelay={300} closeDelay={80}>
	<HoverCard.Trigger>
		{#snippet child({ props }: { props: Record<string, any> })}
			{#if item.kind === 'milestone'}
				<button
					{...props}
					type="button"
					class="absolute top-1/2 -translate-y-1/2 z-10"
					style="left: {geom.left + geom.width / 2 - 8}px;"
					title={t.title}
					onclick={() => openTask(t.id)}
				>
					<span class="block w-4 h-4 rotate-45 rounded-[3px]" style="background:{color}; box-shadow: 0 1px 4px {color}66;"></span>
				</button>
			{:else}
				<button
					{...props}
					type="button"
					class="absolute top-1/2 -translate-y-1/2 h-6 rounded-md z-10 flex items-center px-2 gap-1.5 text-[10px] font-semibold text-white whitespace-nowrap overflow-hidden"
					style="left: {geom.left}px; width: {geom.width}px; background: {t.status === 'done'
						? color
						: `linear-gradient(to right, ${color} ${pct}%, ${color}42 ${pct}%)`}; box-shadow: 0 1px 3px {color}55;"
					onclick={() => openTask(t.id)}
				>
					{#if geom.width >= 64}<span class="flex-none">{stateText}</span>{/if}
					{#if geom.width >= 48 && t.assignee_ids?.length}
						<span class="ml-auto flex-none w-[18px] h-[18px] rounded-full bg-white text-[8px] font-bold inline-flex items-center justify-center" style="color:{color}">
							{initials(t.assignee_ids[0])}
						</span>
					{/if}
				</button>
			{/if}
		{/snippet}
	</HoverCard.Trigger>
	<HoverCard.Content
		side="top"
		align="start"
		sideOffset={8}
		class="w-[340px] p-0 overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-xl select-none"
	>
		<TaskHoverCard task={t} workstreamName={$currentWorkstream?.name ?? ''} />
	</HoverCard.Content>
</HoverCard.Root>

{#if geom.slipWidth > 0}
	<!-- Overdue slip tail: hatched red from the bar/milestone end to the today line -->
	<span
		class="absolute top-1/2 -translate-y-1/2 h-6 rounded-r-md z-[9] flex items-center justify-end pr-1.5 text-[9px] font-bold text-white pointer-events-none"
		style="left: {geom.left + geom.width}px; width: {geom.slipWidth}px; background: repeating-linear-gradient(-45deg, #dc2626, #dc2626 4px, #ef4444 4px, #ef4444 8px);"
	>
		{#if geom.slipWidth >= 40}⚠ {daysLate}d{/if}
	</span>
{/if}
```

- [ ] **Step 4: Rewrite `TimelineView.svelte` (static chart)**

Replace `src/lib/components/workos/views/TimelineView.svelte` entirely:

```svelte
<script lang="ts">
	import { tick } from 'svelte';
	import Icon from '../ui/Icon.svelte';
	import FilterBar from '../chrome/FilterBar.svelte';
	import TimelineHeader from './timeline/TimelineHeader.svelte';
	import TimelineRail from './timeline/TimelineRail.svelte';
	import TimelineBar from './timeline/TimelineBar.svelte';
	import {
		boardFilter, filteredTasks, currentWorkstream, timelineZoom, addTask
	} from '../lib/store';
	import {
		timelineItems, computeWindow, todayDay, todayLineX, dayToX, isWeekend, dayToTs,
		ZOOM_ORDER, ZOOM_DAY_WIDTH
	} from '../lib/timeline';

	const RAIL_W = 260;
	const ROW_H = 46;
	$: railW = RAIL_W;

	// `now` refreshes when the workstream changes so the today line/slip tails
	// stay correct in long-lived sessions.
	let now = Date.now();
	$: today = todayDay(now);
	$: items = timelineItems($filteredTasks);
	$: win = computeWindow(items, today);
	$: dayWidth = ZOOM_DAY_WIDTH[$timelineZoom];
	$: chartW = win.days * dayWidth;
	$: tlx = todayLineX(today, win, dayWidth);
	$: weekendDays = Array.from({ length: win.days }, (_, i) => win.startDay + i).filter(isWeekend);
	// Vertical gridline period: per-day when readable, per-week at quarter zoom.
	$: gridPeriod = dayWidth >= 16 ? dayWidth : dayWidth * 7;
	// Weekly gridlines must land on Mondays: UTC day 0 (1970-01-01) is a Thursday,
	// so a day index d is a Monday when d % 7 === 4. Shift the gradient accordingly.
	$: gridOffset = dayWidth >= 16 ? 0 : ((4 - (win.startDay % 7) + 7) % 7) * dayWidth;

	let scroller: HTMLElement | null = null;
	function scrollToToday() {
		if (!scroller) return;
		scroller.scrollLeft = Math.max(0, railW + tlx - scroller.clientWidth * 0.3);
	}
	// Initial scroll per workstream + zoom (re-anchors today after either changes).
	let scrolledFor = '';
	$: {
		const key = `${$currentWorkstream?.id ?? ''}:${$timelineZoom}`;
		if (scroller && scrolledFor !== key) {
			scrolledFor = key;
			now = Date.now();
			tick().then(scrollToToday);
		}
	}

	// Toolbar quick-add: schedules for today so the task appears on the chart.
	let creatingNew = false;
	let newTitle = '';
	async function submitNew() {
		const ws = $currentWorkstream;
		const title = newTitle.trim();
		if (!title || !ws) return;
		newTitle = '';
		creatingNew = false;
		const ts = dayToTs(todayDay(Date.now()));
		await addTask(ws.id, { title, start_date: ts, due_date: ts });
	}
</script>

<div class="h-full flex flex-col min-h-0">
	<FilterBar filter={boardFilter}>
		<!-- Zoom presets -->
		<div class="inline-flex items-center gap-0.5 rounded-full bg-gray-100 dark:bg-gray-900 p-0.5 text-sm">
			{#each ZOOM_ORDER as z (z)}
				<button
					type="button"
					aria-pressed={$timelineZoom === z}
					class="px-3 py-1 rounded-full transition capitalize {$timelineZoom === z ? 'bg-primary text-primary-foreground shadow-sm' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}"
					onclick={() => timelineZoom.set(z)}
				>{z}</button>
			{/each}
		</div>
		<button
			type="button"
			class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 hover:bg-gray-100 dark:hover:bg-gray-900 transition"
			onclick={() => { now = Date.now(); scrollToToday(); }}
		>Today</button>
		{#if creatingNew}
			<!-- svelte-ignore a11y_autofocus -->
			<input
				class="text-sm px-2 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent w-48"
				placeholder="Task title…"
				bind:value={newTitle}
				onkeydown={(e) => { if (e.key === 'Enter') submitNew(); if (e.key === 'Escape') { creatingNew = false; newTitle = ''; } }}
				autofocus
			/>
		{:else}
			<button class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground text-sm font-medium" onclick={() => { creatingNew = true; newTitle = ''; }}>
				<Icon name="plus" size={15} /> Add new
			</button>
		{/if}
	</FilterBar>

	<div class="flex-1 flex min-h-0 bg-white dark:bg-gray-950">
		<!-- Chart: one scroller for both axes; header sticky top, rail cells sticky left -->
		<div bind:this={scroller} class="flex-1 overflow-auto min-w-0">
			<TimelineHeader {win} {dayWidth} zoom={$timelineZoom} {today} {railW} />

			<div class="relative" style="width: {railW + chartW}px;">
				<!-- Background layer: weekends, gridlines, today line -->
				<div class="absolute top-0 bottom-0 pointer-events-none" style="left: {railW}px; width: {chartW}px;">
					{#each weekendDays as d (d)}
						<div class="absolute top-0 bottom-0 bg-gray-50 dark:bg-gray-900/40" style="left: {dayToX(d, win, dayWidth)}px; width: {dayWidth}px; background-image: repeating-linear-gradient(-45deg, rgb(0 0 0 / 0.025), rgb(0 0 0 / 0.025) 4px, transparent 4px, transparent 8px);"></div>
					{/each}
					<div class="absolute inset-0" style="background: repeating-linear-gradient(to right, transparent, transparent {gridPeriod - 1}px, rgb(0 0 0 / 0.05) {gridPeriod - 1}px, rgb(0 0 0 / 0.05) {gridPeriod}px); background-position: {gridOffset}px 0;"></div>
					<div class="absolute top-0 bottom-0 w-0.5 bg-primary z-10" style="left: {tlx}px;">
						<span class="absolute top-0 -left-[17px] px-1 py-px rounded bg-primary text-primary-foreground text-[8px] font-bold tracking-wide">TODAY</span>
					</div>
				</div>

				<!-- Rows -->
				{#if items.length}
					{#each items as item (item.task.id)}
						<div class="flex border-b border-gray-100 dark:border-gray-900" style="height: {ROW_H}px;">
							<div class="sticky left-0 z-20 flex-none bg-white dark:bg-gray-950 border-r border-gray-100 dark:border-gray-900" style="width: {railW}px;">
								<TimelineRail {item} {today} />
							</div>
							<div class="relative flex-none" style="width: {chartW}px;">
								<TimelineBar {item} {win} {dayWidth} {today} />
							</div>
						</div>
					{/each}
				{:else}
					<div class="flex flex-col items-center justify-center gap-2 py-16 text-center" style="width: {railW + chartW}px;">
						<span class="sticky left-0 flex flex-col items-center gap-2 text-gray-400 dark:text-gray-500" style="max-width: 100vw;">
							<Icon name="chart-gantt" size={28} />
							<span class="text-sm">Nothing scheduled yet — add dates to tasks or create one with “Add new”.</span>
						</span>
					</div>
				{/if}
			</div>
		</div>
	</div>
</div>
```

- [ ] **Step 5: Verify**

Run: `npm run check`
Expected: no new errors.
Run: `npm run test:frontend -- run src/lib/components/workos/lib/timeline.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/views/TimelineView.svelte src/lib/components/workos/views/timeline/
git commit -m "feat(workos): timeline static chart - header, rail, bold bars, slip tails"
```

---

### Task 6: Drag interactions — move, resize, tooltip, cancel, auto-scroll

**Files:**
- Modify: `src/lib/components/workos/views/timeline/TimelineBar.svelte` (full rewrite below)
- Modify: `src/lib/components/workos/views/TimelineView.svelte` (pass `scroller`)

**Interfaces:**
- Consumes: `applyMove`, `applyResize`, `DatePatch` from Task 3; `editTask` from the store; `formatDateShort` from `lib/format`; `toast` from `svelte-sonner`.
- Produces: `TimelineBar` gains props `scroller: HTMLElement | null = null` and `disabled = false` (Task 8 sets `disabled` on mobile). Click ≤ 4px still opens the drawer.

**Behavior contract:**
- `pointerdown` on the bar body starts a **move**; on the left/right grip a **resize** (`start`/`end`). Pointer capture on the bar root. `dayDelta = Math.round(dx / dayWidth)`.
- While dragging: bar renders at the preview position (recompute geometry from a shifted preview item), a dark tooltip above the bar shows `formatDateShort(start) – formatDateShort(due)` of the preview, and when the pointer is within 40px of the scroller's left/right edge the scroller pans by 16px per `pointermove`.
- `pointerup`: movement ≤ 4px → `openTask`; else `editTask(task.id, patch)` where `patch` is `applyMove`/`applyResize` output; `.catch` → `toast.error('Could not update the dates')` (the store already rolled back).
- `Escape` during a drag cancels it (no edit, no click).
- Milestones: draggable (move), plus a left grip that creates a `start_date` (per `applyResize`). No right grip.

- [ ] **Step 1: Rewrite `TimelineBar.svelte` with drag support**

Replace the file with:

```svelte
<script lang="ts">
	import { STATUS_COLOR } from '../../lib/colors';
	import { STATUS_LABEL } from '../../lib/types';
	import { actualProgress } from '../../lib/progress';
	import { formatDateShort } from '../../lib/format';
	import {
		barGeometry, applyMove, applyResize, dayToTs,
		type TimelineItem, type TimelineWindow
	} from '../../lib/timeline';
	import { openTask, editTask, initials, currentWorkstream } from '../../lib/store';
	import * as HoverCard from '$lib/components/ui/hover-card';
	import TaskHoverCard from '../TaskHoverCard.svelte';
	import { toast } from 'svelte-sonner';

	export let item: TimelineItem;
	export let win: TimelineWindow;
	export let dayWidth: number;
	export let today: number;
	export let scroller: HTMLElement | null = null;
	export let disabled = false;

	$: t = item.task;
	$: color = STATUS_COLOR[t.status];
	$: pct = actualProgress(t);
	$: daysLate = today - item.endDay;
	$: stateText =
		t.status === 'done' ? '✓ Done' : t.status === 'in_progress' && pct > 0 ? `${pct}%` : STATUS_LABEL[t.status];

	// ── Drag state ──
	type Mode = 'move' | 'start' | 'end';
	let mode: Mode | null = null;
	let x0 = 0;
	let dx = 0;
	let canceled = false;

	$: delta = mode ? Math.round(dx / dayWidth) : 0;
	// Preview range under the current drag (clamped like applyResize will clamp).
	$: pStart =
		mode === 'move' ? item.startDay + delta
		: mode === 'start' ? Math.min(item.startDay + delta, item.endDay)
		: item.startDay;
	$: pEnd =
		mode === 'move' ? item.endDay + delta
		: mode === 'end' ? Math.max(item.endDay + delta, item.startDay)
		: item.endDay;
	$: geom = barGeometry({ ...item, startDay: pStart, endDay: pEnd }, win, dayWidth, today);

	function down(e: PointerEvent, m: Mode) {
		if (disabled || e.button !== 0) return;
		e.stopPropagation();
		mode = m;
		x0 = e.clientX;
		dx = 0;
		canceled = false;
		(e.currentTarget as Element).setPointerCapture(e.pointerId);
	}
	function move(e: PointerEvent) {
		if (!mode || canceled) return;
		dx = e.clientX - x0;
		// Edge auto-pan: keep dragging usable past the viewport.
		if (scroller) {
			const r = scroller.getBoundingClientRect();
			if (e.clientX > r.right - 40) scroller.scrollLeft += 16;
			else if (e.clientX < r.left + 40) scroller.scrollLeft -= 16;
		}
	}
	async function up() {
		if (!mode) return;
		const m = mode;
		const moved = Math.abs(dx) > 4;
		const d = delta;
		mode = null;
		dx = 0;
		if (canceled) return;
		if (!moved) {
			openTask(t.id);
			return;
		}
		if (d === 0) return;
		const patch = m === 'move' ? applyMove(item, d) : applyResize(item, m, d);
		try {
			await editTask(t.id, patch);
		} catch {
			toast.error('Could not update the dates'); // editTask already rolled back
		}
	}
	function key(e: KeyboardEvent) {
		if (e.key === 'Escape' && mode) {
			canceled = true;
			mode = null;
			dx = 0;
		}
	}

	const GRIP =
		'absolute top-[3px] bottom-[3px] w-[6px] rounded-[3px] bg-white border-[1.5px] border-primary opacity-0 group-hover:opacity-100 cursor-ew-resize';
</script>

<svelte:window onkeydown={key} />

<HoverCard.Root openDelay={300} closeDelay={80}>
	<HoverCard.Trigger>
		{#snippet child({ props }: { props: Record<string, any> })}
			{#if item.kind === 'milestone'}
				<span
					{...props}
					role="button"
					tabindex="0"
					class="group absolute top-1/2 -translate-y-1/2 z-10 touch-none {disabled ? '' : 'cursor-grab'} {mode ? 'cursor-grabbing' : ''}"
					style="left: {geom.left + geom.width / 2 - 8}px;"
					title={t.title}
					aria-label={t.title}
					onpointerdown={(e) => down(e, 'move')}
					onpointermove={move}
					onpointerup={up}
					onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') openTask(t.id); }}
				>
					<span class="block w-4 h-4 rotate-45 rounded-[3px]" style="background:{color}; box-shadow: 0 1px 4px {color}66;"></span>
					{#if !disabled}
						<span class="{GRIP} -left-2.5" onpointerdown={(e) => down(e, 'start')} onpointermove={move} onpointerup={up}></span>
					{/if}
					{#if mode}
						<span class="absolute -top-7 left-0 px-2 py-0.5 rounded-md bg-gray-900 text-white text-[10px] font-medium whitespace-nowrap z-30">
							{pStart !== pEnd ? `${formatDateShort(dayToTs(pStart))} – ` : ''}{formatDateShort(dayToTs(pEnd))}
						</span>
					{/if}
				</span>
			{:else}
				<span
					{...props}
					role="button"
					tabindex="0"
					class="group absolute top-1/2 -translate-y-1/2 h-6 rounded-md z-10 flex items-center px-2 gap-1.5 text-[10px] font-semibold text-white whitespace-nowrap touch-none select-none {disabled ? '' : 'cursor-grab'} {mode ? 'cursor-grabbing' : ''}"
					title={t.title}
					aria-label={t.title}
					style="left: {geom.left}px; width: {geom.width}px; background: {t.status === 'done' || pct <= 0 || pct >= 100
						? color
						: `linear-gradient(to right, ${color} ${pct}%, ${color}42 ${pct}%)`}; box-shadow: 0 1px 3px {color}55;"
					onpointerdown={(e) => down(e, 'move')}
					onpointermove={move}
					onpointerup={up}
					onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') openTask(t.id); }}
				>
					{#if geom.width >= 64}<span class="flex-none overflow-hidden">{stateText}</span>{/if}
					{#if geom.width >= 48 && t.assignee_ids?.length}
						<span class="ml-auto flex-none w-[18px] h-[18px] rounded-full bg-white text-[8px] font-bold inline-flex items-center justify-center" style="color:{color}">
							{initials(t.assignee_ids[0])}
						</span>
					{/if}
					{#if !disabled}
						<span class="{GRIP} -left-[3px]" onpointerdown={(e) => down(e, 'start')} onpointermove={move} onpointerup={up}></span>
						<span class="{GRIP} -right-[3px]" onpointerdown={(e) => down(e, 'end')} onpointermove={move} onpointerup={up}></span>
					{/if}
					{#if mode}
						<span class="absolute -top-7 left-0 px-2 py-0.5 rounded-md bg-gray-900 text-white text-[10px] font-medium whitespace-nowrap z-30">
							{formatDateShort(dayToTs(pStart))} – {formatDateShort(dayToTs(pEnd))}
						</span>
					{/if}
				</span>
			{/if}
		{/snippet}
	</HoverCard.Trigger>
	<HoverCard.Content
		side="top"
		align="start"
		sideOffset={8}
		class="w-[340px] p-0 overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-xl select-none"
	>
		<TaskHoverCard task={t} workstreamName={$currentWorkstream?.name ?? ''} />
	</HoverCard.Content>
</HoverCard.Root>

{#if geom.slipWidth > 0 && !mode}
	<span
		class="absolute top-1/2 -translate-y-1/2 h-6 rounded-r-md z-[9] flex items-center justify-end pr-1.5 text-[9px] font-bold text-white pointer-events-none"
		style="left: {geom.left + geom.width}px; width: {geom.slipWidth}px; background: repeating-linear-gradient(-45deg, #dc2626, #dc2626 4px, #ef4444 4px, #ef4444 8px);"
	>
		{#if geom.slipWidth >= 40}⚠ {daysLate}d{/if}
	</span>
{/if}
```

Notes for the implementer:
- The bar became a `<span role="button">` (not `<button>`) so the grip spans nested inside it don't produce invalid button-in-button markup.
- The click-to-open path now lives in `up()` (≤4px movement) and the keyboard handler — the old `onclick` is gone.
- The slip tail hides while dragging (`!mode`) so the preview reads clean.

- [ ] **Step 2: Pass the scroller from `TimelineView.svelte`**

In `src/lib/components/workos/views/TimelineView.svelte`, change the bar usage inside the row loop to:

```svelte
<TimelineBar {item} {win} {dayWidth} {today} {scroller} />
```

- [ ] **Step 3: Verify**

Run: `npm run check`
Expected: no new errors.
Run: `npm run test:frontend -- run src/lib/components/workos/lib/timeline.test.ts`
Expected: PASS (lib untouched, sanity).

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/timeline/TimelineBar.svelte src/lib/components/workos/views/TimelineView.svelte
git commit -m "feat(workos): timeline drag move/resize with snap, tooltip, cancel"
```

---

### Task 7: Unscheduled panel — drag-to-schedule + per-chart add row

**Files:**
- Create: `src/lib/components/workos/views/timeline/UnscheduledPanel.svelte`
- Modify: `src/lib/components/workos/views/TimelineView.svelte`

**Interfaces:**
- Consumes: `unscheduledTasks` (Task 1), `xToDay`, `dayToTs` (Tasks 1–2), `editTask`, `addTask`, `openTask` from the store.
- Produces: `UnscheduledPanel` props: `tasks: Task[]`, `collapsed: boolean` (bindable). Drag payload: `e.dataTransfer.setData('text/workos-task', task.id)`, `effectAllowed = 'move'`.

**Behavior contract:**
- Panel cards are HTML5-draggable. Dropping on the chart lanes sets `start_date = due_date = dayToTs(dropDay)`.
- While dragging over the lanes, a teal dashed drop indicator line renders at the hovered day.
- A "+ Add task" row under the last chart row reveals an inline title input; Enter creates via `addTask(ws.id, { title, start_date: todayTs, due_date: todayTs })`, Escape cancels (same pattern as the toolbar add).

- [ ] **Step 1: Create `UnscheduledPanel.svelte`**

`src/lib/components/workos/views/timeline/UnscheduledPanel.svelte`:

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { STATUS_COLOR, PRIORITY_COLOR } from '../../lib/colors';
	import { openTask } from '../../lib/store';
	import type { Task } from '../../lib/types';

	export let tasks: Task[] = [];
	export let collapsed = false;

	function dragStart(e: DragEvent, t: Task) {
		e.dataTransfer?.setData('text/workos-task', t.id);
		if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move';
	}
</script>

{#if collapsed}
	<button
		class="flex-none w-9 border-l border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 flex flex-col items-center gap-2 py-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
		title="Show unscheduled"
		onclick={() => (collapsed = false)}
	>
		<Icon name="chevron-left" size={14} />
		<span class="text-[10px] font-bold [writing-mode:vertical-rl]">UNSCHEDULED · {tasks.length}</span>
	</button>
{:else}
	<div class="flex-none w-52 border-l border-gray-200 dark:border-gray-800 bg-gray-50/60 dark:bg-gray-900/40 p-2.5 flex flex-col gap-2 overflow-y-auto">
		<div class="flex items-center gap-1.5">
			<span class="text-[10px] font-bold tracking-wider text-gray-500 dark:text-gray-400">UNSCHEDULED</span>
			<span class="text-[10px] px-1.5 rounded-full bg-gray-200 dark:bg-gray-800 text-gray-500">{tasks.length}</span>
			<span class="flex-1"></span>
			<button class="text-gray-400 hover:text-gray-600" title="Collapse" onclick={() => (collapsed = true)}>
				<Icon name="chevron-right" size={14} />
			</button>
		</div>
		<p class="text-[11px] text-gray-400 leading-snug">Drag a task onto the chart to schedule it.</p>
		{#each tasks as t (t.id)}
			<div
				role="button"
				tabindex="0"
				draggable="true"
				ondragstart={(e) => dragStart(e, t)}
				class="rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 px-2.5 py-2 cursor-grab shadow-sm"
				onclick={() => openTask(t.id)}
				onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') openTask(t.id); }}
			>
				<span class="flex items-center gap-1.5 min-w-0">
					<span class="flex-none text-gray-300 dark:text-gray-600"><Icon name="grip-vertical" size={12} /></span>
					<span class="flex-none w-2 h-2 rounded-full" style="background:{STATUS_COLOR[t.status]}"></span>
					<span class="text-[12px] font-medium truncate text-gray-800 dark:text-gray-100">{t.title}</span>
				</span>
				{#if t.priority}
					<span class="mt-0.5 pl-[26px] flex items-center gap-1 text-[10px]" style="color:{PRIORITY_COLOR[t.priority]}">
						<Icon name="flag" size={10} /> {t.priority[0].toUpperCase() + t.priority.slice(1)}
					</span>
				{/if}
			</div>
		{/each}
		{#if !tasks.length}
			<div class="text-[11px] text-gray-300 dark:text-gray-600 py-2 text-center">Nothing unscheduled</div>
		{/if}
	</div>
{/if}
```

- [ ] **Step 2: Wire the panel, drop handling, and the add row into `TimelineView.svelte`**

(a) Extend the script imports/state:

```ts
import UnscheduledPanel from './timeline/UnscheduledPanel.svelte';
import { unscheduledTasks, xToDay } from '../lib/timeline'; // merge into the existing ../lib/timeline import
import { editTask } from '../lib/store'; // merge into the existing store import
import { toast } from 'svelte-sonner';

$: unscheduled = unscheduledTasks($filteredTasks);
let railCollapsed = false;

// HTML5 drop target state: the hovered chart day while a rail card is dragged.
let rowsEl: HTMLElement | null = null;
let hoverDay: number | null = null;
function laneDay(e: DragEvent): number | null {
	if (!rowsEl) return null;
	const x = e.clientX - rowsEl.getBoundingClientRect().left - railW;
	return x < 0 ? null : xToDay(x, win, dayWidth);
}
function dragOver(e: DragEvent) {
	if (!e.dataTransfer?.types.includes('text/workos-task')) return;
	e.preventDefault(); // allow drop
	hoverDay = laneDay(e);
}
async function drop(e: DragEvent) {
	const id = e.dataTransfer?.getData('text/workos-task');
	const day = laneDay(e);
	hoverDay = null;
	if (!id || day == null) return;
	e.preventDefault();
	try {
		await editTask(id, { start_date: dayToTs(day), due_date: dayToTs(day) });
	} catch {
		toast.error('Could not schedule the task');
	}
}

// Per-chart quick add (bottom row).
let addingRow = false;
let rowTitle = '';
async function submitRow() {
	const ws = $currentWorkstream;
	const title = rowTitle.trim();
	if (!title || !ws) return;
	rowTitle = '';
	addingRow = false;
	const ts = dayToTs(todayDay(Date.now()));
	await addTask(ws.id, { title, start_date: ts, due_date: ts });
}
```

(b) Wrap the rows block as a drop target and add the drop indicator + add row. The `<div class="relative" style="width: …">` wrapper from Task 5 becomes:

```svelte
<div
	bind:this={rowsEl}
	role="list"
	class="relative"
	style="width: {railW + chartW}px;"
	ondragover={dragOver}
	ondragleave={() => (hoverDay = null)}
	ondrop={drop}
>
	<!-- (background layer unchanged) -->

	{#if hoverDay != null}
		<div class="absolute top-0 bottom-0 z-30 border-l-2 border-dashed border-primary pointer-events-none" style="left: {railW + dayToX(hoverDay, win, dayWidth)}px;">
			<span class="absolute top-1 left-1 px-1.5 py-0.5 rounded bg-primary text-primary-foreground text-[9px] font-bold whitespace-nowrap">Schedule here</span>
		</div>
	{/if}

	<!-- (rows / empty state unchanged) -->

	<!-- Add-task row -->
	<div class="flex" style="height: {ROW_H}px;">
		<div class="sticky left-0 z-20 flex-none bg-white dark:bg-gray-950 flex items-center px-3" style="width: {railW}px;">
			{#if addingRow}
				<!-- svelte-ignore a11y_autofocus -->
				<input
					class="text-sm px-2 py-1 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent w-full"
					placeholder="Task title…"
					bind:value={rowTitle}
					onkeydown={(e) => { if (e.key === 'Enter') submitRow(); if (e.key === 'Escape') { addingRow = false; rowTitle = ''; } }}
					autofocus
				/>
			{:else}
				<button class="inline-flex items-center gap-1.5 text-sm text-primary font-medium hover:opacity-80" onclick={() => { addingRow = true; rowTitle = ''; }}>
					<Icon name="plus" size={15} /> Add task
				</button>
			{/if}
		</div>
	</div>
</div>
```

(c) Mount the panel as the right sibling of the scroller (inside the `flex-1 flex min-h-0` wrapper, after the scroller div):

```svelte
<UnscheduledPanel tasks={unscheduled} bind:collapsed={railCollapsed} />
```

- [ ] **Step 3: Verify**

Run: `npm run check`
Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/timeline/UnscheduledPanel.svelte src/lib/components/workos/views/TimelineView.svelte
git commit -m "feat(workos): timeline unscheduled rail with drag-to-schedule + add row"
```

---

### Task 8: Mobile pass + final verification

**Files:**
- Modify: `src/lib/components/workos/views/TimelineView.svelte`
- Modify: `src/lib/components/workos/views/timeline/TimelineRail.svelte` (no change expected — `compact` prop exists; verify)

**Interfaces:**
- Consumes: `mobile` store from `$lib/stores` (same source ListView/CalendarView use).
- Produces: final view. Mobile = view-only: no bar drags (`disabled`), no grips, no HTML5 drag-in, rail 150px single-line, row height 40px, unscheduled as a collapsible section above the chart, side panel hidden.

- [ ] **Step 1: Apply the mobile adaptations in `TimelineView.svelte`**

(a) Import the mobile store and derive the responsive constants (replace the fixed `railW` line from Task 5):

```ts
import { mobile } from '$lib/stores';

const RAIL_W = 260;
$: railW = $mobile ? 150 : RAIL_W;
$: rowH = $mobile ? 40 : 46;
```

Replace every `ROW_H` usage in the markup with `rowH` (row loop and the add-task row) and delete the `const ROW_H = 46;` line.

(b) Pass view-only state down in the row loop:

```svelte
<TimelineRail {item} {today} compact={$mobile} />
…
<TimelineBar {item} {win} {dayWidth} {today} {scroller} disabled={$mobile} />
```

(c) Gate the desktop-only pieces:
- The side panel mounts only on desktop:

```svelte
{#if !$mobile}
	<UnscheduledPanel tasks={unscheduled} bind:collapsed={railCollapsed} />
{/if}
```

- The lanes' `ondragover/ondragleave/ondrop` handlers stay attached (HTML5 DnD simply never starts on mobile since the cards render in the tap list below), and the add-task row keeps working on mobile.

(d) Add the mobile unscheduled section between the `FilterBar` and the chart wrapper (mirrors CalendarView's mobile pattern):

```svelte
{#if $mobile && unscheduled.length}
	<div class="flex-none px-3 pt-3 bg-white dark:bg-gray-950">
		<button
			class="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-800 text-sm font-medium"
			onclick={() => (showUnscheduled = !showUnscheduled)}
		>
			Unscheduled <span class="text-xs text-gray-400">{unscheduled.length}</span>
			<span class="flex-1"></span>
			<Icon name={showUnscheduled ? 'chevron-up' : 'chevron-down'} size={14} />
		</button>
		{#if showUnscheduled}
			<div class="mt-2 rounded-lg border border-gray-200 dark:border-gray-800 divide-y divide-gray-100 dark:divide-gray-900">
				{#each unscheduled as t (t.id)}
					<button class="w-full flex items-center gap-2.5 px-3 py-2.5 text-left" onclick={() => openTask(t.id)}>
						<span class="flex-none w-2 h-2 rounded-full" style="background:{STATUS_COLOR[t.status]}"></span>
						<span class="flex-1 min-w-0 text-sm truncate">{t.title}</span>
					</button>
				{/each}
			</div>
		{/if}
	</div>
{/if}
```

with the supporting script additions:

```ts
import { STATUS_COLOR } from '../lib/colors';
import { openTask } from '../lib/store'; // merge into the existing store import
let showUnscheduled = false;
```

- [ ] **Step 2: Full verification**

Run: `npm run test:frontend -- run`
Expected: PASS — full frontend suite green (timeline + all existing suites).
Run: `npm run check`
Expected: no new errors versus the pre-branch baseline.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/workos/views/TimelineView.svelte src/lib/components/workos/views/timeline/
git commit -m "feat(workos): timeline mobile view-only pass"
```

- [ ] **Step 4: Report for manual browser smoke (do NOT start Vite)**

Tell the user the feature is built and list the smoke checklist from the spec:
tab appears/routes · bars per status incl. progress split, slip tail, milestone · drag move/resize persists + survives reload · rail drag-in schedules · filters/search narrow rows · zoom presets re-scale + persist · Today button scrolls · drawer opens from title/bar click · dark mode · mobile pan + tap.

---

## Self-review notes (already applied)

- Spec's "hover on bar → TaskHoverCard" is implemented via shadcn `HoverCard` on the bar trigger (openDelay 300); if hover-during-drag glitches surface in smoke, drop the HoverCard from the bar and keep it available from the rail title (one-line change).
- Spec's write-gating bullet was amended (2026-07-09) to the codebase's optimistic + rollback/toast precedent — implemented in Tasks 6–7.
- `xToDay` on drop uses the lanes' bounding rect minus `railW`, which is correct because the rows wrapper starts at the rail's left edge and the rail is `railW` wide.
- Bars are `<span role="button">` (not `<button>`) so resize grips can nest without invalid HTML.
