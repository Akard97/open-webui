# WorkOS Calendar View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a due-date Month/Week calendar as the 4th workstream tab in WorkOS, with drag-to-schedule, empty-day quick-add, and an unscheduled-tasks rail.

**Architecture:** Frontend-only. A new `CalendarView` reads the existing task store filtered by the shared `boardFilter`, groups tasks by their `due_date` calendar day, and renders them as chips in a CSS-grid month/week layout. Reschedule and schedule reuse SortableJS (already powering the board) and the existing `editTask`/`addTask` store actions. `createTask` and the task PATCH already accept `due_date`, so there are no backend, DB, or API changes.

**Tech Stack:** SvelteKit (Svelte 5, legacy `$:` reactivity as used in `BoardView.svelte`), TypeScript, Tailwind, SortableJS, Vitest.

## Global Constraints

- All new files live under `src/lib/components/workos/`. Tool-local; do not touch global app styles.
- Match the existing WorkOS design system: Tailwind utilities, `bg-white dark:bg-gray-950` surfaces, `border-gray-200 dark:border-gray-800`, status colors from `lib/colors.ts` (`STATUS_COLOR`, `statusShape`), `StatusDot` + `Icon` components, `text-primary`/`bg-primary` brand tokens. Osool teal is `#00a5ba`.
- Week starts **Sunday**.
- Tasks are positioned by `due_date` only. Tasks with `due_date == null` go to the unscheduled rail.
- Month view caps at 3 chips per cell (`+N more`); week view renders all chips uncapped.
- Overdue = `due_date` calendar-day < today AND status not `done`/`canceled`.
- Reuse existing store actions only: `editTask(id, { due_date })`, `addTask(wsId, { title, due_date })`, `openTask(id)`. No new endpoints.
- Verification commands (run from repo root `C:\Projects\open-webui`):
  - Type check: `npm run check`
  - Frontend unit tests (single file): `npx vitest run <path>`
- **Do not start a Vite dev server.** The user runs their own hot-reload server; "verify in browser" means asking the user to confirm in their already-running app. Frontend edits are live on save (no Docker rebuild).

---

### Task 1: Date helpers (`lib/calendar.ts`)

Pure, dependency-free date math for the grid. Full TDD — this is the only non-trivial logic in the feature.

**Files:**
- Create: `src/lib/components/workos/lib/calendar.ts`
- Test: `src/lib/components/workos/lib/calendar.test.ts`

**Interfaces:**
- Consumes: `Task` from `./types`.
- Produces:
  - `dayKey(ms: number): number` — local start-of-day epoch.
  - `sameDay(a: number, b: number): boolean`
  - `isToday(ms: number, now: number): boolean`
  - `monthGrid(cursor: Date): Date[]` — whole-week, Sunday-first grid covering the cursor's month (35 or 42 days).
  - `weekDays(cursor: Date): Date[]` — the 7 days (Sun..Sat) of the cursor's week.
  - `isOverdue(task: Task, now: number): boolean`

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/workos/lib/calendar.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { dayKey, sameDay, isToday, monthGrid, weekDays, isOverdue } from './calendar';
import type { Task } from './types';

const mk = (over: Partial<Task>): Task => ({
	id: 't', workstream_id: 'w', team_id: 'tm', number: 1, key: 'OSL-1', title: 't',
	status: 'todo', assignee_ids: [], progress: 0, labels: [], sort_key: 1,
	created_by_id: 'u', due_date: null, created_at: 0, updated_at: 0, ...over
});

describe('dayKey / sameDay / isToday', () => {
	it('strips the time component', () => {
		const noon = new Date(2026, 5, 29, 12, 30).getTime();
		const midnight = new Date(2026, 5, 29, 0, 0).getTime();
		expect(dayKey(noon)).toBe(dayKey(midnight));
		expect(sameDay(noon, midnight)).toBe(true);
		expect(sameDay(noon, new Date(2026, 5, 30, 12).getTime())).toBe(false);
	});
	it('isToday compares calendar days', () => {
		const now = new Date(2026, 5, 29, 9).getTime();
		expect(isToday(new Date(2026, 5, 29, 23).getTime(), now)).toBe(true);
		expect(isToday(new Date(2026, 5, 28, 23).getTime(), now)).toBe(false);
	});
});

describe('monthGrid', () => {
	it('June 2026 is a 5-week grid, Sunday-first, May 31 → Jul 4', () => {
		const g = monthGrid(new Date(2026, 5, 15));
		expect(g.length).toBe(35);
		expect(g[0].getDay()).toBe(0);            // Sunday
		expect(g[0].getMonth()).toBe(4);          // May
		expect(g[0].getDate()).toBe(31);
		expect(g[34].getMonth()).toBe(6);         // July
		expect(g[34].getDate()).toBe(4);
		for (let i = 0; i < g.length; i += 7) expect(g[i].getDay()).toBe(0);
	});
	it('May 2026 needs 6 weeks (42 days)', () => {
		const g = monthGrid(new Date(2026, 4, 10));
		expect(g.length).toBe(42);
		expect(g[0].getDay()).toBe(0);
	});
});

describe('weekDays', () => {
	it('Mon 2026-06-29 → Sun Jun 28 .. Sat Jul 4', () => {
		const w = weekDays(new Date(2026, 5, 29));
		expect(w.length).toBe(7);
		expect(w[0].getDay()).toBe(0);
		expect(w[0].getDate()).toBe(28);
		expect(w[6].getMonth()).toBe(6);
		expect(w[6].getDate()).toBe(4);
	});
});

describe('isOverdue', () => {
	const now = new Date(2026, 5, 29, 9).getTime();
	it('past-due open task is overdue', () => {
		expect(isOverdue(mk({ due_date: new Date(2026, 5, 28).getTime() }), now)).toBe(true);
	});
	it('done / canceled are never overdue', () => {
		expect(isOverdue(mk({ due_date: new Date(2026, 5, 28).getTime(), status: 'done' }), now)).toBe(false);
		expect(isOverdue(mk({ due_date: new Date(2026, 5, 28).getTime(), status: 'canceled' }), now)).toBe(false);
	});
	it('today, future, and null are not overdue', () => {
		expect(isOverdue(mk({ due_date: new Date(2026, 5, 29, 23).getTime() }), now)).toBe(false);
		expect(isOverdue(mk({ due_date: new Date(2026, 5, 30).getTime() }), now)).toBe(false);
		expect(isOverdue(mk({ due_date: null }), now)).toBe(false);
	});
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npx vitest run src/lib/components/workos/lib/calendar.test.ts`
Expected: FAIL — `Failed to resolve import "./calendar"` (file does not exist yet).

- [ ] **Step 3: Write the implementation**

Create `src/lib/components/workos/lib/calendar.ts`:

```ts
import type { Task } from './types';

// Local start-of-day epoch (ms). The calendar groups and compares tasks by
// local calendar day, ignoring the time component of a due date.
export function dayKey(ms: number): number {
	const d = new Date(ms);
	return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

export function sameDay(a: number, b: number): boolean {
	return dayKey(a) === dayKey(b);
}

export function isToday(ms: number, now: number): boolean {
	return dayKey(ms) === dayKey(now);
}

// Whole-week, Sunday-first grid covering the cursor's month: leading days from
// the prior month back to the Sunday on/before the 1st, the full month, and
// trailing days forward to the Saturday on/after the last. 35 or 42 days.
export function monthGrid(cursor: Date): Date[] {
	const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
	const start = new Date(first);
	start.setDate(1 - first.getDay());
	const last = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0);
	const end = new Date(last);
	end.setDate(last.getDate() + (6 - last.getDay()));
	const days: Date[] = [];
	for (const d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) days.push(new Date(d));
	return days;
}

// The 7 days (Sun..Sat) of the week containing the cursor.
export function weekDays(cursor: Date): Date[] {
	const start = new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() - cursor.getDay());
	return Array.from({ length: 7 }, (_, i) => {
		const d = new Date(start);
		d.setDate(start.getDate() + i);
		return d;
	});
}

export function isOverdue(task: Task, now: number): boolean {
	if (task.due_date == null) return false;
	if (task.status === 'done' || task.status === 'canceled') return false;
	return dayKey(task.due_date) < dayKey(now);
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `npx vitest run src/lib/components/workos/lib/calendar.test.ts`
Expected: PASS (all assertions green).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/calendar.ts src/lib/components/workos/lib/calendar.test.ts
git commit -m "feat(workos): calendar date helpers (month/week grid, overdue)"
```

---

### Task 2: Calendar tab + empty navigable grid

Wire the stubbed Calendar tab to a real view that renders an empty, navigable Month/Week grid. No tasks yet — this proves routing, the toolbar, and the grid layout.

**Files:**
- Modify: `src/lib/components/workos/lib/store.ts:18` (`ViewKey` union)
- Modify: `src/lib/components/workos/chrome/Topbar.svelte:15,18-20` (tab `live`, `selectTab` type)
- Modify: `src/lib/components/workos/WorkOSApp.svelte:34,51-55` (Topbar guard + view switch)
- Modify: `src/lib/components/workos/ui/Icon.svelte:3` (add `chevron-left` to the icon map)
- Create: `src/lib/components/workos/views/CalendarView.svelte`
- Create: `src/lib/components/workos/views/calendar/DayCell.svelte`

**Interfaces:**
- Consumes: `monthGrid`, `weekDays`, `isToday` (Task 1); `view`, `currentWorkstream` (store).
- Produces:
  - `CalendarView.svelte` — default-exported component, no props.
  - `DayCell.svelte` — props `{ date: Date; dimmed: boolean; today: boolean }` (extended in later tasks).

- [ ] **Step 1: Add `'calendar'` to the view union**

In `src/lib/components/workos/lib/store.ts`, line 18:

```ts
export type ViewKey = 'board' | 'list' | 'admin' | 'inbox' | 'mywork' | 'calendar';
```

- [ ] **Step 2: Make the Topbar Calendar tab live**

In `src/lib/components/workos/chrome/Topbar.svelte`, change the calendar tab (line 15) to `live: true`:

```ts
		{ key: 'calendar', label: 'Calendar', icon: 'calendar', live: true },
```

And widen `selectTab`'s cast (lines 18-20) so `'calendar'` is allowed:

```ts
	function selectTab(t: (typeof TABS)[number]) {
		if (t.live) view.set(t.key as 'board' | 'list' | 'calendar');
	}
```

- [ ] **Step 3: Mount CalendarView in WorkOSApp**

In `src/lib/components/workos/WorkOSApp.svelte`:

Add the import near the other view imports (after the `ListView` import, line 8):

```svelte
	import CalendarView from './views/CalendarView.svelte';
```

Show the Topbar for the calendar view (line 34) — extend the guard:

```svelte
		{#if $view === 'board' || $view === 'list' || $view === 'calendar'}
```

Add the calendar branch to the view switch. Change the tail of the switch (currently `{:else if $view === 'list'}` → `{:else}` board) to insert calendar before the board fallback:

```svelte
				{:else if $view === 'list'}
					<ListView />
				{:else if $view === 'calendar'}
					<CalendarView />
				{:else}
					<BoardView />
				{/if}
```

- [ ] **Step 4: Create the DayCell shell**

Create `src/lib/components/workos/views/calendar/DayCell.svelte`:

```svelte
<script lang="ts">
	export let date: Date;
	export let dimmed = false;
	export let today = false;
</script>

<div class="flex flex-col min-h-[88px] p-1.5 border-r border-b border-gray-100 dark:border-gray-900">
	{#if today}
		<span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-primary text-primary-foreground text-xs font-medium">{date.getDate()}</span>
	{:else}
		<span class="text-xs {dimmed ? 'text-gray-300 dark:text-gray-700' : 'text-gray-500 dark:text-gray-400'}">{date.getDate()}</span>
	{/if}
</div>
```

- [ ] **Step 5: Add the `chevron-left` icon**

The toolbar's "previous" button needs `chevron-left`, which is not in the map (only `chevron-right`). In `src/lib/components/workos/ui/Icon.svelte`, add this entry to the `LUCIDE` record (e.g. right after the `chevron-right` line, line 6):

```ts
		'chevron-left': '<path d="m15 18-6-6 6-6"/>',
```

- [ ] **Step 6: Create the CalendarView shell (toolbar + grid)**

Create `src/lib/components/workos/views/CalendarView.svelte`:

```svelte
<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import FilterBar from '../chrome/FilterBar.svelte';
	import DayCell from './calendar/DayCell.svelte';
	import { monthGrid, weekDays, isToday } from '../lib/calendar';
	import { boardFilter } from '../lib/store';

	const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

	let mode: 'month' | 'week' = 'month';
	// Anchor date for the visible period; ephemeral (resets on remount).
	let cursor = new Date();

	$: days = mode === 'month' ? monthGrid(cursor) : weekDays(cursor);
	$: cursorMonth = cursor.getMonth();
	$: label =
		mode === 'month'
			? cursor.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
			: rangeLabel(weekDays(cursor));

	function rangeLabel(w: Date[]): string {
		const f = w[0], l = w[6];
		const opts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
		return `${f.toLocaleDateString(undefined, opts)} – ${l.toLocaleDateString(undefined, opts)}, ${l.getFullYear()}`;
	}

	function step(dir: 1 | -1) {
		const c = new Date(cursor);
		if (mode === 'month') c.setMonth(c.getMonth() + dir);
		else c.setDate(c.getDate() + dir * 7);
		cursor = c;
	}
	function today() {
		cursor = new Date();
	}
</script>

<div class="h-full flex flex-col min-h-0">
	<FilterBar filter={boardFilter} />

	<!-- Toolbar -->
	<div class="flex-none flex items-center gap-3 px-4 py-2.5 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
		<div class="flex items-center gap-1">
			<button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-900" title="Previous" onclick={() => step(-1)}><Icon name="chevron-left" size={16} /></button>
			<button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-900" title="Next" onclick={() => step(1)}><Icon name="chevron-right" size={16} /></button>
		</div>
		<div class="text-base font-semibold">{label}</div>
		<button class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 hover:bg-gray-100 dark:hover:bg-gray-900" onclick={today}>Today</button>
		<div class="flex-1"></div>
		<div class="inline-flex rounded-lg border border-gray-200 dark:border-gray-800 overflow-hidden text-sm">
			<button class="px-3 py-1.5 {mode === 'month' ? 'bg-primary text-primary-foreground' : 'hover:bg-gray-100 dark:hover:bg-gray-900'}" onclick={() => (mode = 'month')}>Month</button>
			<button class="px-3 py-1.5 {mode === 'week' ? 'bg-primary text-primary-foreground' : 'hover:bg-gray-100 dark:hover:bg-gray-900'}" onclick={() => (mode = 'week')}>Week</button>
		</div>
	</div>

	<!-- Grid -->
	<div class="flex-1 overflow-auto p-4 bg-white dark:bg-gray-900">
		<div class="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
			<div class="grid grid-cols-7 bg-gray-50 dark:bg-gray-950">
				{#each WEEKDAYS as w (w)}
					<div class="px-2 py-1.5 text-xs text-gray-400 border-b border-gray-100 dark:border-gray-900">{w}</div>
				{/each}
			</div>
			<div class="grid grid-cols-7">
				{#each days as d (d.getTime())}
					<DayCell date={d} dimmed={mode === 'month' && d.getMonth() !== cursorMonth} today={isToday(d.getTime(), Date.now())} />
				{/each}
			</div>
		</div>
	</div>
</div>
```

- [ ] **Step 7: Type-check**

Run: `npm run check`
Expected: PASS (no new type errors). If `primary-foreground` utility is unknown to your Tailwind setup, it is the same token the board's "Add New" button uses (`bg-primary text-primary-foreground` in `BoardView.svelte`), so it resolves.

- [ ] **Step 8: Verify in browser (ask the user)**

Ask the user to confirm in their running app: open a workstream, click the **Calendar** tab — it is no longer greyed out and shows the FilterBar, a toolbar (‹ ›, month label, Today, Month/Week toggle), the weekday header, and an empty grid. `‹`/`›` move by month (or week), **Today** returns to the current period, and the **Month/Week** toggle switches layout. Today's date shows a teal badge.

- [ ] **Step 9: Commit**

```bash
git add src/lib/components/workos/lib/store.ts src/lib/components/workos/chrome/Topbar.svelte src/lib/components/workos/WorkOSApp.svelte src/lib/components/workos/ui/Icon.svelte src/lib/components/workos/views/CalendarView.svelte src/lib/components/workos/views/calendar/DayCell.svelte
git commit -m "feat(workos): calendar tab + navigable month/week grid"
```

---

### Task 3: Render task chips on their due day

Add the `filteredTasks` store source, the `CalChip` component, and group filtered tasks onto day cells (with `+N more` overflow in month view, uncapped in week view). Clicking a chip opens the task detail drawer.

**Files:**
- Modify: `src/lib/components/workos/lib/store.ts` (add `filteredTasks` derived near `tasksByStatus`, ~line 99)
- Create: `src/lib/components/workos/views/calendar/CalChip.svelte`
- Modify: `src/lib/components/workos/views/calendar/DayCell.svelte`
- Modify: `src/lib/components/workos/views/CalendarView.svelte`

**Interfaces:**
- Consumes: `filteredTasks` (new), `dayKey`, `isOverdue`, `STATUS_COLOR`, `statusShape`, `openTask`.
- Produces:
  - `filteredTasks: Readable<Task[]>` — `tasks` filtered by `boardFilter` (flat; the same predicate `tasksByStatus` uses).
  - `CalChip.svelte` — props `{ task: Task }`.
  - `DayCell.svelte` — now also `{ tasks: Task[]; cap: number }`.

- [ ] **Step 1: Add the `filteredTasks` derived store**

In `src/lib/components/workos/lib/store.ts`, immediately after the `tasksByStatus` derived (after its closing `});`, ~line 99), add:

```ts
// Flat, filtered task list — the single source for the calendar grid + rail.
// Mirrors tasksByStatus' filtering (same applyFilters predicate), ungrouped.
export const filteredTasks = derived([tasks, boardFilter], ([$tasks, $filter]) =>
	applyFilters($tasks, $filter)
);
```

(`derived` and `applyFilters` are already imported in this file.)

- [ ] **Step 2: Type-check the store change**

Run: `npm run check`
Expected: PASS.

- [ ] **Step 3: Create the CalChip component**

Create `src/lib/components/workos/views/calendar/CalChip.svelte`:

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import type { Task } from '../../lib/types';
	import { STATUS_COLOR } from '../../lib/colors';
	import { isOverdue } from '../../lib/calendar';
	import { openTask } from '../../lib/store';

	export let task: Task;

	$: overdue = isOverdue(task, Date.now());
	$: done = task.status === 'done';
	$: color = STATUS_COLOR[task.status];
</script>

<button
	data-task-id={task.id}
	class="w-full flex items-center gap-1.5 rounded-md px-1.5 py-1 text-left text-[11px] leading-tight"
	style={overdue ? 'background:#dc26261f' : `background:${color}1f`}
	title={task.title}
	onclick={() => openTask(task.id)}
>
	{#if overdue}
		<Icon name="alert-triangle" size={11} />
	{:else if task.priority === 'urgent'}
		<span class="flex-none text-red-600"><Icon name="flag" size={11} /></span>
	{:else if done}
		<span class="flex-none" style="color:{color}"><Icon name="check" size={11} /></span>
	{:else}
		<span class="flex-none w-[7px] h-[7px] rounded-full" style="background:{color}"></span>
	{/if}
	<span
		class="truncate {overdue ? 'text-red-600' : done ? 'text-gray-400 line-through' : 'text-gray-800 dark:text-gray-100'}"
	>{task.title}</span>
</button>
```

- [ ] **Step 4: Render chips + overflow in DayCell**

Replace `src/lib/components/workos/views/calendar/DayCell.svelte` with:

```svelte
<script lang="ts">
	import CalChip from './CalChip.svelte';
	import type { Task } from '../../lib/types';

	export let date: Date;
	export let dimmed = false;
	export let today = false;
	export let tasks: Task[] = [];
	export let cap = Infinity;

	$: visible = tasks.slice(0, cap);
	$: overflow = Math.max(0, tasks.length - visible.length);
</script>

<div class="flex flex-col gap-1 min-h-[88px] p-1.5 border-r border-b border-gray-100 dark:border-gray-900">
	<div class="flex-none">
		{#if today}
			<span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-primary text-primary-foreground text-xs font-medium">{date.getDate()}</span>
		{:else}
			<span class="text-xs {dimmed ? 'text-gray-300 dark:text-gray-700' : 'text-gray-500 dark:text-gray-400'}">{date.getDate()}</span>
		{/if}
	</div>

	<div class="flex flex-col gap-1">
		{#each visible as t (t.id)}
			<CalChip task={t} />
		{/each}
		{#if overflow > 0}
			<div class="text-[11px] text-gray-400 pl-1.5">+{overflow} more</div>
		{/if}
	</div>
</div>
```

- [ ] **Step 5: Group tasks by day in CalendarView and pass to cells**

In `src/lib/components/workos/views/CalendarView.svelte`:

Extend the imports — add `filteredTasks` to the store import and import `dayKey`:

```svelte
	import { monthGrid, weekDays, isToday, dayKey } from '../lib/calendar';
	import { boardFilter, filteredTasks } from '../lib/store';
```

Add the grouping derivation after the `days` reactive line:

```svelte
	import type { Task } from '../lib/types';
	$: scheduled = $filteredTasks.filter((t) => t.due_date != null);
	$: byDay = scheduled.reduce<Map<number, Task[]>>((m, t) => {
		const k = dayKey(t.due_date as number);
		(m.get(k) ?? m.set(k, []).get(k)!).push(t);
		return m;
	}, new Map());
	$: cap = mode === 'month' ? 3 : Infinity;
```

Pass the day's tasks and cap into `DayCell`:

```svelte
				{#each days as d (d.getTime())}
					<DayCell
						date={d}
						dimmed={mode === 'month' && d.getMonth() !== cursorMonth}
						today={isToday(d.getTime(), Date.now())}
						tasks={byDay.get(dayKey(d.getTime())) ?? []}
						{cap}
					/>
				{/each}
```

- [ ] **Step 6: Type-check**

Run: `npm run check`
Expected: PASS.

- [ ] **Step 7: Verify in browser (ask the user)**

Ask the user to confirm: tasks with a due date now appear as chips on the correct day. A status dot + tinted background matches the task's status color; overdue open tasks are red with a warning glyph; urgent tasks show a red flag; done tasks are struck through. A day with >3 tasks (month view) shows "+N more"; week view shows all. Clicking a chip opens the task detail drawer. Changing a FilterBar facet (e.g. Status) adds/removes chips live.

- [ ] **Step 8: Commit**

```bash
git add src/lib/components/workos/lib/store.ts src/lib/components/workos/views/calendar/CalChip.svelte src/lib/components/workos/views/calendar/DayCell.svelte src/lib/components/workos/views/CalendarView.svelte
git commit -m "feat(workos): render tasks as chips on their due day"
```

---

### Task 4: Empty-day quick-add

Click a day's empty space to add a task due that day, mirroring the board/list inline quick-add. Requires threading `due_date` through `addTask`.

**Files:**
- Modify: `src/lib/components/workos/lib/store.ts:182-202` (`addTask` signature + optimistic + create body)
- Modify: `src/lib/components/workos/views/calendar/DayCell.svelte`

**Interfaces:**
- Consumes: `addTask`, `currentWorkstream` (store); `dayKey` (Task 1).
- Produces: `addTask(workstreamId, { title, status?, priority?, assignee_ids?, start_date?, due_date? })` — now accepts `start_date`/`due_date`.

- [ ] **Step 1: Thread `due_date` (and `start_date`) through `addTask`**

In `src/lib/components/workos/lib/store.ts`, update `addTask` (lines 182-193). Change the `fields` type and the optimistic `due_date`:

```ts
export async function addTask(
	workstreamId: string,
	fields: {
		title: string; status?: TaskStatus; priority?: TaskPriority | null;
		assignee_ids?: string[]; start_date?: number | null; due_date?: number | null;
	}
): Promise<void> {
	const tempId = `temp-${Date.now()}-${Math.round(performance.now())}`;
	const optimistic: Task = {
		id: tempId, workstream_id: workstreamId, team_id: get(currentTeam)?.id ?? '', number: 0, key: '…',
		title: fields.title, status: fields.status ?? 'backlog', priority: fields.priority ?? null,
		assignee_ids: fields.assignee_ids ?? [], start_date: fields.start_date ?? null,
		due_date: fields.due_date ?? null, progress: 0, labels: [],
		sort_key: Date.now(), created_by_id: get(user)?.id ?? null, completed_at: null,
		created_at: Date.now(), updated_at: Date.now()
	};
```

The existing `api.createTask(token(), workstreamId, fields)` call (line 196) needs no change — `createTask`'s body type already accepts `start_date`/`due_date`, and `fields` now carries them.

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: PASS. (Existing `addTask` callers pass a subset of fields, so the wider optional type stays compatible.)

- [ ] **Step 3: Add inline quick-add to DayCell**

In `src/lib/components/workos/views/calendar/DayCell.svelte`, extend the script:

```svelte
<script lang="ts">
	import CalChip from './CalChip.svelte';
	import type { Task } from '../../lib/types';
	import { addTask, currentWorkstream } from '../../lib/store';
	import { dayKey } from '../../lib/calendar';

	export let date: Date;
	export let dimmed = false;
	export let today = false;
	export let tasks: Task[] = [];
	export let cap = Infinity;

	$: visible = tasks.slice(0, cap);
	$: overflow = Math.max(0, tasks.length - visible.length);

	let adding = false;
	let title = '';

	async function submit() {
		const ws = $currentWorkstream;
		if (!title.trim() || !ws) return;
		await addTask(ws.id, { title: title.trim(), due_date: dayKey(date.getTime()) });
		title = '';
		adding = false;
	}
</script>
```

Then replace the cell body so the empty area below the chips opens the quick-add on click:

```svelte
<div class="group flex flex-col gap-1 min-h-[88px] p-1.5 border-r border-b border-gray-100 dark:border-gray-900">
	<div class="flex-none">
		{#if today}
			<span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-primary text-primary-foreground text-xs font-medium">{date.getDate()}</span>
		{:else}
			<span class="text-xs {dimmed ? 'text-gray-300 dark:text-gray-700' : 'text-gray-500 dark:text-gray-400'}">{date.getDate()}</span>
		{/if}
	</div>

	<div class="flex flex-col gap-1">
		{#each visible as t (t.id)}
			<CalChip task={t} />
		{/each}
		{#if overflow > 0}
			<div class="text-[11px] text-gray-400 pl-1.5">+{overflow} more</div>
		{/if}
	</div>

	{#if adding}
		<!-- svelte-ignore a11y_autofocus -->
		<input
			class="mt-1 text-[11px] px-1.5 py-1 rounded border border-gray-300 dark:border-gray-700 bg-transparent"
			placeholder="Task title…"
			bind:value={title}
			onkeydown={(e) => { if (e.key === 'Enter') submit(); if (e.key === 'Escape') { adding = false; title = ''; } }}
			onblur={() => { adding = false; title = ''; }}
			autofocus
		/>
	{:else}
		<button
			class="flex-1 min-h-[16px] rounded text-left opacity-0 group-hover:opacity-100 transition"
			title="Add task on this day"
			aria-label="Add task on {date.toDateString()}"
			onclick={() => (adding = true)}
		></button>
	{/if}
</div>
```

- [ ] **Step 4: Type-check**

Run: `npm run check`
Expected: PASS.

- [ ] **Step 5: Verify in browser (ask the user)**

Ask the user to confirm: hovering a day reveals a clickable empty area; clicking it shows an inline input; typing a title and pressing Enter creates a task that immediately appears as a chip on that day (Escape/blur cancels). The new task carries that day as its due date (open it and check the due date).

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/lib/store.ts src/lib/components/workos/views/calendar/DayCell.svelte
git commit -m "feat(workos): quick-add a task on a calendar day"
```

---

### Task 5: Unscheduled rail

Add the right rail listing tasks with no due date. (Drag interactions come in Task 6; this task renders the rail and its rows.)

**Files:**
- Modify: `src/lib/components/workos/ui/Icon.svelte:3` (add `inbox`, `grip-vertical`)
- Create: `src/lib/components/workos/views/calendar/UnscheduledRail.svelte`
- Modify: `src/lib/components/workos/views/CalendarView.svelte`

**Interfaces:**
- Consumes: `filteredTasks`, `STATUS_COLOR`, `openTask`.
- Produces: `UnscheduledRail.svelte` — props `{ tasks: Task[] }`.

- [ ] **Step 1: Add the `inbox` and `grip-vertical` icons**

The rail uses both, which are not in the map. In `src/lib/components/workos/ui/Icon.svelte`, add to the `LUCIDE` record:

```ts
		inbox: '<polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.45-6.89A2 2 0 0 0 16.76 4H7.24a2 2 0 0 0-1.79 1.11z"/>',
		'grip-vertical': '<circle cx="9" cy="12" r="1"/><circle cx="9" cy="5" r="1"/><circle cx="9" cy="19" r="1"/><circle cx="15" cy="12" r="1"/><circle cx="15" cy="5" r="1"/><circle cx="15" cy="19" r="1"/>',
```

- [ ] **Step 2: Create the rail component**

Create `src/lib/components/workos/views/calendar/UnscheduledRail.svelte`:

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import type { Task } from '../../lib/types';
	import { STATUS_COLOR } from '../../lib/colors';
	import { openTask } from '../../lib/store';

	export let tasks: Task[] = [];
</script>

<div class="w-44 flex-none border border-gray-200 dark:border-gray-800 rounded-xl p-2.5 flex flex-col gap-2 bg-white dark:bg-gray-950">
	<div class="flex items-center gap-1.5">
		<Icon name="inbox" size={14} />
		<span class="text-xs font-medium">Unscheduled</span>
		<span class="text-[11px] text-gray-400">{tasks.length}</span>
	</div>
	<p class="text-[11px] text-gray-400 leading-snug">Drag a task onto a day to set its due date.</p>

	<div data-cal-rail class="flex flex-col gap-1.5 min-h-[24px]">
		{#each tasks as t (t.id)}
			<button
				data-task-id={t.id}
				class="flex items-center gap-1.5 rounded-md border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 px-2 py-1.5 text-left text-[11px] cursor-grab"
				title={t.title}
				onclick={() => openTask(t.id)}
			>
				<span class="flex-none text-gray-300 dark:text-gray-600"><Icon name="grip-vertical" size={12} /></span>
				<span class="flex-none w-[7px] h-[7px] rounded-full" style="background:{STATUS_COLOR[t.status]}"></span>
				<span class="truncate text-gray-800 dark:text-gray-100">{t.title}</span>
			</button>
		{/each}
		{#if !tasks.length}
			<div class="text-[11px] text-gray-300 dark:text-gray-600 py-2 text-center">Nothing unscheduled</div>
		{/if}
	</div>
</div>
```

- [ ] **Step 3: Place the rail beside the grid in CalendarView**

In `src/lib/components/workos/views/CalendarView.svelte`:

Add the import:

```svelte
	import UnscheduledRail from './calendar/UnscheduledRail.svelte';
```

Add the unscheduled derivation next to `scheduled`:

```svelte
	$: unscheduled = $filteredTasks.filter((t) => t.due_date == null);
```

Wrap the grid and rail in a flex row. Replace the grid container `<div class="flex-1 overflow-auto p-4 bg-white dark:bg-gray-900"> … </div>` with:

```svelte
	<div class="flex-1 overflow-auto p-4 bg-white dark:bg-gray-900 flex gap-4 items-start">
		<div class="flex-1 min-w-0 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
			<div class="grid grid-cols-7 bg-gray-50 dark:bg-gray-950">
				{#each WEEKDAYS as w (w)}
					<div class="px-2 py-1.5 text-xs text-gray-400 border-b border-gray-100 dark:border-gray-900">{w}</div>
				{/each}
			</div>
			<div class="grid grid-cols-7">
				{#each days as d (d.getTime())}
					<DayCell
						date={d}
						dimmed={mode === 'month' && d.getMonth() !== cursorMonth}
						today={isToday(d.getTime(), Date.now())}
						tasks={byDay.get(dayKey(d.getTime())) ?? []}
						{cap}
					/>
				{/each}
			</div>
		</div>
		<UnscheduledRail tasks={unscheduled} />
	</div>
```

- [ ] **Step 4: Type-check**

Run: `npm run check`
Expected: PASS.

- [ ] **Step 5: Verify in browser (ask the user)**

Ask the user to confirm: a right rail appears beside the calendar listing tasks that have no due date, each with a status dot and grip handle; the count matches; an empty rail shows "Nothing unscheduled". Clicking a rail row opens the task detail. Filtering hides matching rail rows too.

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/ui/Icon.svelte src/lib/components/workos/views/calendar/UnscheduledRail.svelte src/lib/components/workos/views/CalendarView.svelte
git commit -m "feat(workos): unscheduled tasks rail on the calendar"
```

---

### Task 6: Drag to schedule / reschedule (SortableJS)

Wire SortableJS across all day cells and the rail as one group. Dragging a chip to another day reschedules it; dragging a rail row to a day schedules it; dragging a chip back to the rail unschedules it. Mirrors the board's "remove the dragged node, re-render from the store" pattern to avoid SortableJS/Svelte reconciliation conflicts.

**Files:**
- Modify: `src/lib/components/workos/views/calendar/DayCell.svelte` (mark the chip container as a drop list)
- Modify: `src/lib/components/workos/views/CalendarView.svelte` (Sortable init + `onEnd` + grid epoch)

**Interfaces:**
- Consumes: `Sortable` (`sortablejs`), `editTask`, `tasks` store, `dayKey`.
- Produces: drag-driven `editTask(id, { due_date })` (or `{ due_date: null }` for rail drops).

- [ ] **Step 1: Mark DayCell's chip container as a droppable day list**

In `src/lib/components/workos/views/calendar/DayCell.svelte`, give the chips container the drop-target attributes (`data-cal-list` + `data-day`). Change:

```svelte
	<div class="flex flex-col gap-1">
		{#each visible as t (t.id)}
			<CalChip task={t} />
		{/each}
```

to:

```svelte
	<div class="flex flex-col gap-1 min-h-[20px]" data-cal-list data-day={dayKey(date.getTime())}>
		{#each visible as t (t.id)}
			<CalChip task={t} />
		{/each}
```

(The `+N more` indicator and the quick-add stay outside this container so only chips — `[data-task-id]` — are draggable. `dayKey` is already imported from Task 4.)

- [ ] **Step 2: Add Sortable wiring to CalendarView**

In `src/lib/components/workos/views/CalendarView.svelte`:

Add imports:

```svelte
	import Sortable from 'sortablejs';
	import { onDestroy, tick } from 'svelte';
	import { get } from 'svelte/store';
	import { editTask, tasks as tasksStore } from '../lib/store';
```

Add state + the SortableJS lifecycle. Place this in the `<script>` after the existing reactive derivations:

```svelte
	let gridEl: HTMLElement;
	// Bumped after each drop to re-key the grid + rail, discarding SortableJS's
	// DOM mutation and rebuilding every cell from the store (the source of truth).
	let epoch = 0;
	let sortables: Sortable[] = [];

	function destroySortables() {
		sortables.forEach((s) => s.destroy());
		sortables = [];
	}

	async function initSortables() {
		destroySortables();
		await tick();
		if (!gridEl) return;
		const lists = gridEl.querySelectorAll<HTMLElement>('[data-cal-list], [data-cal-rail]');
		lists.forEach((el) =>
			sortables.push(
				new Sortable(el, {
					group: 'workos-calendar',
					animation: 150,
					ghostClass: 'opacity-40',
					draggable: '[data-task-id]',
					onEnd: handleEnd
				})
			)
		);
	}

	async function handleEnd(evt: Sortable.SortableEvent) {
		const taskId = evt.item.getAttribute('data-task-id');
		const to = evt.to as HTMLElement;
		if (!taskId) return;
		const isRail = to.hasAttribute('data-cal-rail');
		const nextDue = isRail ? null : Number(to.getAttribute('data-day'));

		// Drop SortableJS's moved node; the store-driven rebuild below recreates it.
		evt.item.remove();

		const current = get(tasksStore).find((t) => t.id === taskId);
		const curKey = current?.due_date == null ? null : dayKey(current.due_date);
		const nextKey = nextDue == null ? null : dayKey(nextDue);
		if (curKey !== nextKey) await editTask(taskId, { due_date: nextDue });

		epoch += 1; // rebuild grid + rail from the store
		await initSortables();
	}

	// Re-init whenever the rendered cell set changes (period, mode, filtered
	// tasks, or a post-drop rebuild). Guarded by tick() inside initSortables.
	$: void [days, mode, $filteredTasks, epoch], queueInit();
	let queued = false;
	function queueInit() {
		if (queued) return;
		queued = true;
		tick().then(() => { queued = false; initSortables(); });
	}

	onDestroy(destroySortables);
```

Wrap the grid+rail row in the `gridEl` ref and the `{#key epoch}` rebuild. Change the outer container opening tag and wrap its contents:

```svelte
	<div class="flex-1 overflow-auto p-4 bg-white dark:bg-gray-900 flex gap-4 items-start" bind:this={gridEl}>
		{#key epoch}
			<div class="flex-1 min-w-0 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
				<div class="grid grid-cols-7 bg-gray-50 dark:bg-gray-950">
					{#each WEEKDAYS as w (w)}
						<div class="px-2 py-1.5 text-xs text-gray-400 border-b border-gray-100 dark:border-gray-900">{w}</div>
					{/each}
				</div>
				<div class="grid grid-cols-7">
					{#each days as d (d.getTime())}
						<DayCell
							date={d}
							dimmed={mode === 'month' && d.getMonth() !== cursorMonth}
							today={isToday(d.getTime(), Date.now())}
							tasks={byDay.get(dayKey(d.getTime())) ?? []}
							{cap}
						/>
					{/each}
				</div>
			</div>
			<UnscheduledRail tasks={unscheduled} />
		{/key}
	</div>
```

(The `bind:this={gridEl}` is on the flex row so its `querySelectorAll` reaches both the day lists and the rail. The `{#key epoch}` wraps both children.)

- [ ] **Step 3: Type-check**

Run: `npm run check`
Expected: PASS.

- [ ] **Step 4: Verify in browser (ask the user)**

Ask the user to confirm:
- Drag a chip from one day to another → it moves and persists (reload keeps it); reschedule reflects in the task's due date.
- Drag a rail (unscheduled) task onto a day → it leaves the rail and becomes a chip on that day.
- Drag a chip onto the rail → it leaves the calendar and joins the unscheduled list (due date cleared).
- Dropping a chip back on its own day is a no-op (no flicker/duplicate).
- After any drag, the day cells and rail show no stranded/duplicate chips.
- Open a second session on the same workstream → a drag in one updates the other (realtime still flows through the store).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/views/calendar/DayCell.svelte src/lib/components/workos/views/CalendarView.svelte
git commit -m "feat(workos): drag to schedule/reschedule calendar tasks"
```

---

## Self-Review notes

- **Spec coverage:** Due-date placement (Task 3), Month+Week toggle (Task 2), all four interactions — open (Task 3), reschedule + schedule + unschedule (Task 6), quick-add (Task 4), rail (Task 5); right-rail placement (Task 5); Sunday start (Task 1 `monthGrid`/`weekDays`); chip styling incl. overdue/done/urgent (Task 3); today + dimmed days (Task 2); `+N more` month-only cap (Tasks 2-3); filter reuse (`filteredTasks`, Task 3); realtime (free via store, verified Task 6); `addTask` due_date thread (Task 4); no backend changes (confirmed — `createTask`/`updateTask` already accept `due_date`). YAGNI items (span bars, recurring, saved views) intentionally excluded.
- **Type consistency:** `filteredTasks` (Task 3) consumed by Tasks 5-6; `DayCell` props grow monotonically (`date/dimmed/today` → `+tasks/cap` → quick-add internals → `data-cal-list`); `addTask` widened once (Task 4) and used by Task 4 only; `dayKey` used consistently for grouping (Task 3) and drop comparison (Task 6); `data-task-id` / `data-cal-list` / `data-day` / `data-cal-rail` attribute names match between DayCell/UnscheduledRail (producers) and `handleEnd` (consumer).
- **Icon coverage (resolved):** `ui/Icon.svelte`'s map already has `alert-triangle`, `flag`, `check`, `chevron-right`, `chevron-down`, `calendar`, `search`, `plus`. The three it lacks — `chevron-left` (Task 2 Step 5), `inbox` and `grip-vertical` (Task 5 Step 1) — are added by this plan with standard Lucide path data, so no chip/toolbar/rail glyph renders blank.
