# My Work Command Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the WorkOS My Work view from a flat bucketed task list into a "focus cockpit" command center: a workable task list spine framed by KPI stats, a completion/breakdown insights panel, a notifications-backed activity rail, and workstream quick-launch.

**Architecture:** Frontend-only. Decompose the single `MyWorkView.svelte` into an orchestrator plus small single-purpose components under `views/commandcenter/`, backed by a new pure, unit-tested `lib/stats.ts`. All numbers derive from data already loaded (`myTasks` via `/me/tasks`); the activity rail reuses the existing `notifications` store (`/notifications`). No backend, migration, or access-control change.

**Tech Stack:** SvelteKit (Svelte 5, callback-prop components), TypeScript, Tailwind with shadcn-svelte tokens scoped to `.workos-root`, Vitest for `lib/` unit tests.

## Global Constraints

- **No backend / migration / access-control change.** Consume `/me/tasks` and `/notifications` as-is; both are already visibility-filtered. (Spec §8, §10.)
- **Svelte 5 callback props** — components communicate via `export let onX: (...) => void`, never `createEventDispatcher` or `on:` forwarding (matches existing WorkOS components, e.g. `DetailHeader.svelte`'s `export let onEditTitle: () => void`).
- **Styling** uses existing Tailwind + shadcn token classes already in use in this folder: `bg-primary`, `text-primary`, `text-primary-foreground`, `bg-accent`, `border-gray-200 dark:border-gray-800`. Every color must work in light and dark mode.
- **Pure helpers in `lib/`** take `now: number` as a parameter (mirrors `bucketByDueDate(tasks, now)`) so they are deterministically testable.
- **Frontend test command:** `npx vitest run <path>` (one-shot, no watch).
- **Typecheck gate for components:** `npm run check` (svelte-check over the project); confirm it introduces no new errors referencing the files you touched.
- **Do not stage `src/lib/components/workos/chrome/FilterBar.svelte`** — it has an unrelated pre-existing working-tree modification. Stage only the exact paths each task lists.

---

### Task 1: Pure stats module (`lib/stats.ts`)

**Files:**
- Create: `src/lib/components/workos/lib/stats.ts`
- Test: `src/lib/components/workos/lib/stats.test.ts`

**Interfaces:**
- Consumes: `bucketByDueDate(tasks, now)` from `./buckets`; `Task`, `TaskStatus` from `./types`.
- Produces:
  - `type PriorityKey = 'urgent' | 'high' | 'medium' | 'low' | 'none'`
  - `interface MyWorkStats { overdue; dueToday; inProgress; doneThisWeek; completionRate; total; byStatus: Record<TaskStatus, number>; byPriority: Record<PriorityKey, number> }`
  - `function computeStats(tasks: Task[], now: number): MyWorkStats`
  - `function needsAttention(tasks: Task[], now: number): Task[]`

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/workos/lib/stats.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { computeStats, needsAttention } from './stats';
import type { Task, TaskStatus, TaskPriority } from './types';

const DAY = 86_400_000;
const NOW = new Date(2024, 2, 6, 12, 0, 0).getTime(); // 2024-03-06 12:00 local

const mk = (
	id: string,
	o: Partial<Task> = {}
): Task => ({
	id, workstream_id: 'w1', team_id: 'tm', number: 1, key: `OSL-${id}`, title: id,
	status: (o.status ?? 'todo') as TaskStatus, priority: o.priority ?? null,
	assignee_ids: o.assignee_ids ?? [], progress: 0, labels: [], sort_key: 1,
	created_by_id: 'u1', due_date: o.due_date ?? null, completed_at: o.completed_at ?? null,
	created_at: 0, updated_at: 0
});

describe('computeStats', () => {
	it('counts buckets, statuses, priorities, and completion', () => {
		const tasks = [
			mk('a', { status: 'in_progress', priority: 'urgent', due_date: NOW - DAY }), // overdue
			mk('b', { status: 'todo', priority: 'high', due_date: NOW + 3600_000 }),      // today
			mk('c', { status: 'done', priority: 'medium', completed_at: NOW - 2 * DAY }), // done this week
			mk('d', { status: 'done', priority: 'low', completed_at: NOW - 10 * DAY }),   // done, old
			mk('e', { status: 'canceled' }),
			mk('f', { status: 'backlog' })
		];
		const s = computeStats(tasks, NOW);
		expect(s.overdue).toBe(1);
		expect(s.dueToday).toBe(1);
		expect(s.inProgress).toBe(1);
		expect(s.doneThisWeek).toBe(1);
		expect(s.byStatus.done).toBe(2);
		expect(s.byStatus.canceled).toBe(1);
		expect(s.byPriority.urgent).toBe(1);
		expect(s.byPriority.none).toBe(2); // e (canceled) + f (backlog) have null priority
		// total excludes canceled: a,b,c,d,f = 5; done = 2 → 2/5 = 0.4
		expect(s.total).toBe(5);
		expect(s.completionRate).toBeCloseTo(0.4, 5);
	});

	it('doneThisWeek includes the exact 7-day boundary and excludes earlier', () => {
		const tasks = [
			mk('edge', { status: 'done', completed_at: NOW - 7 * DAY }),
			mk('past', { status: 'done', completed_at: NOW - 7 * DAY - 1 })
		];
		const s = computeStats(tasks, NOW);
		expect(s.doneThisWeek).toBe(1);
	});

	it('completionRate is 0 when there are no non-canceled tasks', () => {
		expect(computeStats([], NOW).completionRate).toBe(0);
		expect(computeStats([mk('x', { status: 'canceled' })], NOW).completionRate).toBe(0);
	});
});

describe('needsAttention', () => {
	it('unions overdue, due-today, and urgent/high open tasks, de-duplicated', () => {
		const tasks = [
			mk('overdueUrgent', { status: 'in_progress', priority: 'urgent', due_date: NOW - DAY }),
			mk('today', { due_date: NOW + 3600_000 }),
			mk('highLater', { priority: 'high', due_date: NOW + 30 * DAY }),
			mk('doneHigh', { status: 'done', priority: 'high' }), // excluded: resolved
			mk('lowLater', { priority: 'low', due_date: NOW + 30 * DAY }) // excluded: not urgent/high, not due soon
		];
		const ids = needsAttention(tasks, NOW).map((t) => t.id);
		expect(ids).toEqual(['overdueUrgent', 'today', 'highLater']);
	});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/lib/components/workos/lib/stats.test.ts`
Expected: FAIL — `Failed to resolve import "./stats"` / `computeStats is not a function`.

- [ ] **Step 3: Write minimal implementation**

Create `src/lib/components/workos/lib/stats.ts`:

```ts
import { bucketByDueDate } from './buckets';
import type { Task, TaskStatus } from './types';

const WEEK = 7 * 86_400_000;

export type PriorityKey = 'urgent' | 'high' | 'medium' | 'low' | 'none';

export interface MyWorkStats {
	overdue: number;
	dueToday: number;
	inProgress: number;
	doneThisWeek: number;
	completionRate: number; // 0..1
	total: number;          // non-canceled count (completion denominator)
	byStatus: Record<TaskStatus, number>;
	byPriority: Record<PriorityKey, number>;
}

export function computeStats(tasks: Task[], now: number): MyWorkStats {
	const b = bucketByDueDate(tasks, now);
	const byStatus: Record<TaskStatus, number> = {
		backlog: 0, todo: 0, in_progress: 0, in_review: 0, done: 0, canceled: 0
	};
	const byPriority: Record<PriorityKey, number> = {
		urgent: 0, high: 0, medium: 0, low: 0, none: 0
	};
	const weekAgo = now - WEEK;
	let done = 0, total = 0, doneThisWeek = 0;
	for (const t of tasks) {
		byStatus[t.status]++;
		byPriority[t.priority ?? 'none']++;
		if (t.status !== 'canceled') {
			total++;
			if (t.status === 'done') done++;
		}
		if (t.status === 'done' && (t.completed_at ?? 0) >= weekAgo) doneThisWeek++;
	}
	return {
		overdue: b.overdue.length,
		dueToday: b.today.length,
		inProgress: byStatus.in_progress,
		doneThisWeek,
		completionRate: total === 0 ? 0 : done / total,
		total,
		byStatus,
		byPriority
	};
}

// overdue ∪ due-today ∪ (urgent|high priority, still open), de-duplicated, overdue first.
export function needsAttention(tasks: Task[], now: number): Task[] {
	const b = bucketByDueDate(tasks, now);
	const urgentHigh = tasks.filter(
		(t) =>
			(t.priority === 'urgent' || t.priority === 'high') &&
			t.status !== 'done' &&
			t.status !== 'canceled'
	);
	const seen = new Set<string>();
	const out: Task[] = [];
	for (const t of [...b.overdue, ...b.today, ...urgentHigh]) {
		if (seen.has(t.id)) continue;
		seen.add(t.id);
		out.push(t);
	}
	return out;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/lib/components/workos/lib/stats.test.ts`
Expected: PASS (3 + 1 = all tests green).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/stats.ts src/lib/components/workos/lib/stats.test.ts
git commit -m "feat(workos): pure My Work stats module (counts, completion, needs-attention)"
```

---

### Task 2: Shared status/priority colors (`lib/colors.ts`)

DRY the color maps currently inlined in `Pills.svelte` so the new InsightsPanel and Pills share one source of truth.

**Files:**
- Create: `src/lib/components/workos/lib/colors.ts`
- Modify: `src/lib/components/workos/ui/Pills.svelte`

**Interfaces:**
- Produces: `STATUS_COLOR: Record<TaskStatus, string>`, `PRIORITY_COLOR: Record<TaskPriority, string>` from `./colors`.

- [ ] **Step 1: Create the colors module**

Create `src/lib/components/workos/lib/colors.ts`:

```ts
import type { TaskStatus, TaskPriority } from './types';

export const STATUS_COLOR: Record<TaskStatus, string> = {
	backlog: '#9ca3af', todo: '#6b7280', in_progress: '#00a5ba',
	in_review: '#d97706', done: '#769a4a', canceled: '#9ca3af'
};

export const PRIORITY_COLOR: Record<TaskPriority, string> = {
	urgent: '#dc2626', high: '#ea580c', medium: '#ca8a04', low: '#6b7280'
};
```

- [ ] **Step 2: Point Pills at the shared maps**

In `src/lib/components/workos/ui/Pills.svelte`, replace the two inline `const PRIORITY_COLOR`/`const STATUS_COLOR` declarations with an import. The `<script>` top becomes:

```svelte
<script lang="ts">
	import type { TaskPriority, TaskStatus, Label } from '../lib/types';
	import { STATUS_COLOR, PRIORITY_COLOR } from '../lib/colors';
	export let priority: TaskPriority | null | undefined = undefined;
	export let status: TaskStatus | undefined = undefined;
	export let label: Label | undefined = undefined;
	export let size: 'sm' | 'md' = 'sm';

	$: textSize = size === 'md' ? 'text-sm' : 'text-[11px]';
</script>
```

Leave the markup below unchanged (it already references `PRIORITY_COLOR[priority]` and `STATUS_COLOR[status]`).

- [ ] **Step 3: Typecheck**

Run: `npm run check`
Expected: no new errors referencing `colors.ts` or `Pills.svelte`.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/lib/colors.ts src/lib/components/workos/ui/Pills.svelte
git commit -m "refactor(workos): extract shared status/priority color maps"
```

---

### Task 3: Notification summary helper + `openNotification` action

Extract the notification one-liner (currently a local `summary()` in `InboxView.svelte`) into a tested pure helper, and lift the click-to-open behavior into the store so both the Inbox and the new Activity rail share it.

**Files:**
- Create: `src/lib/components/workos/lib/notifications.ts`
- Test: `src/lib/components/workos/lib/notifications.test.ts`
- Modify: `src/lib/components/workos/lib/store.ts`
- Modify: `src/lib/components/workos/views/InboxView.svelte`

**Interfaces:**
- Produces: `summarizeNotification(n: Notification): string` from `./notifications`; `openNotification(n: Notification): Promise<void>` from `./store`.
- Consumes (store): existing `markRead`, `selectWorkstream`, `openTask`, `view`, `Notification`.

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/workos/lib/notifications.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { summarizeNotification } from './notifications';
import type { Notification, NotificationType } from './types';

const mk = (type: NotificationType, data: Record<string, any> = {}): Notification => ({
	id: 'n1', user_id: 'u1', actor_id: 'u2', task_id: 't1', type, data, read: false, created_at: 0
});

describe('summarizeNotification', () => {
	it('renders a line per type with actor and task key', () => {
		const d = { actor_name: 'Mia', task_key: 'OSL-7' };
		expect(summarizeNotification(mk('assigned', d))).toBe('Mia assigned you OSL-7');
		expect(summarizeNotification(mk('mentioned', d))).toBe('Mia mentioned you in OSL-7');
		expect(summarizeNotification(mk('commented', d))).toBe('Mia commented on OSL-7');
		expect(summarizeNotification(mk('status_changed', d))).toBe('Mia changed status of OSL-7');
	});

	it('falls back gracefully when actor and key are missing', () => {
		expect(summarizeNotification(mk('assigned'))).toBe('Someone assigned you');
	});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/lib/components/workos/lib/notifications.test.ts`
Expected: FAIL — cannot resolve `./notifications`.

- [ ] **Step 3: Create the helper**

Create `src/lib/components/workos/lib/notifications.ts`:

```ts
import type { Notification } from './types';

export function summarizeNotification(n: Notification): string {
	const who = n.data?.actor_name ?? 'Someone';
	const key = n.data?.task_key ? `${n.data.task_key} ` : '';
	switch (n.type) {
		case 'assigned': return `${who} assigned you ${key}`.trim();
		case 'mentioned': return `${who} mentioned you in ${key}`.trim();
		case 'commented': return `${who} commented on ${key}`.trim();
		case 'status_changed': return `${who} changed status of ${key}`.trim();
		default: return `${who} updated ${key}`.trim();
	}
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/lib/components/workos/lib/notifications.test.ts`
Expected: PASS.

- [ ] **Step 5: Add `openNotification` to the store**

In `src/lib/components/workos/lib/store.ts`, add this exported function next to `markAllRead` (the `Notification` type is already imported at the top of the file):

```ts
export async function openNotification(n: Notification): Promise<void> {
	if (!n.read) await markRead([n.id]);
	if (n.data?.workstream_id) await selectWorkstream(n.data.workstream_id);
	if (n.task_id) openTask(n.task_id);
	view.set('board');
}
```

- [ ] **Step 6: Refactor InboxView to consume both**

In `src/lib/components/workos/views/InboxView.svelte`:

Replace the `<script>` block's imports and the local `summary`/`open` functions with:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { notifications, loadNotifications, markAllRead, openNotification } from '../lib/store';
	import { summarizeNotification } from '../lib/notifications';

	onMount(loadNotifications);
</script>
```

Then in the markup, change the summary call and the row click handler:
- `{summary(n)}` → `{summarizeNotification(n)}`
- `onclick={() => open(n)}` → `onclick={() => openNotification(n)}`

(Leave the rest of InboxView's markup unchanged.)

- [ ] **Step 7: Typecheck**

Run: `npm run check`
Expected: no new errors. `InboxView.svelte` no longer references `markRead`, `selectWorkstream`, `openTask`, `view`, or `Notification` directly.

- [ ] **Step 8: Commit**

```bash
git add src/lib/components/workos/lib/notifications.ts src/lib/components/workos/lib/notifications.test.ts src/lib/components/workos/lib/store.ts src/lib/components/workos/views/InboxView.svelte
git commit -m "refactor(workos): shared notification summary + openNotification action"
```

---

### Task 4: StatStrip component

**Files:**
- Create: `src/lib/components/workos/views/commandcenter/StatStrip.svelte`

**Interfaces:**
- Consumes: `MyWorkStats` from `../../lib/stats`.
- Produces: props `stats: MyWorkStats`, `active: string | null`, `onPick: (key: string) => void`. Tile keys: `'overdue' | 'dueToday' | 'inProgress' | 'doneThisWeek'`.

- [ ] **Step 1: Create the component**

Create `src/lib/components/workos/views/commandcenter/StatStrip.svelte`:

```svelte
<script lang="ts">
	import type { MyWorkStats } from '../../lib/stats';
	export let stats: MyWorkStats;
	export let active: string | null = null;
	export let onPick: (key: string) => void;

	$: tiles = [
		{ key: 'overdue', label: 'Overdue', value: stats.overdue, danger: stats.overdue > 0 },
		{ key: 'dueToday', label: 'Due today', value: stats.dueToday, danger: false },
		{ key: 'inProgress', label: 'In progress', value: stats.inProgress, danger: false },
		{ key: 'doneThisWeek', label: 'Done this week', value: stats.doneThisWeek, danger: false }
	];
</script>

<div class="grid grid-cols-2 sm:grid-cols-4 gap-2 px-4 pt-3">
	{#each tiles as t (t.key)}
		<button
			type="button"
			class="text-left rounded-lg border px-3 py-2 transition
				{active === t.key ? 'border-primary ring-1 ring-primary' : 'border-gray-200 dark:border-gray-800'}
				{t.danger ? 'bg-red-50 dark:bg-red-950/30' : 'bg-white dark:bg-gray-950'}
				hover:bg-gray-50 dark:hover:bg-gray-900"
			onclick={() => onPick(t.key)}
		>
			<div class="text-xl font-semibold {t.danger ? 'text-red-600 dark:text-red-400' : ''}">{t.value}</div>
			<div class="text-[11px] {t.danger ? 'text-red-600/80 dark:text-red-400/80' : 'text-gray-500'}">{t.label}</div>
		</button>
	{/each}
</div>
```

- [ ] **Step 2: Typecheck**

Run: `npm run check`
Expected: no new errors referencing `StatStrip.svelte`.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/workos/views/commandcenter/StatStrip.svelte
git commit -m "feat(workos): My Work KPI stat strip component"
```

---

### Task 5: InsightsPanel component (completion ring + breakdown bars)

**Files:**
- Create: `src/lib/components/workos/views/commandcenter/InsightsPanel.svelte`

**Interfaces:**
- Consumes: `MyWorkStats`, `PriorityKey` from `../../lib/stats`; `STATUS_COLOR`, `PRIORITY_COLOR` from `../../lib/colors`; `STATUS_ORDER`, `STATUS_LABEL`, `TaskStatus` from `../../lib/types`.
- Produces: prop `stats: MyWorkStats`.

- [ ] **Step 1: Create the component**

Create `src/lib/components/workos/views/commandcenter/InsightsPanel.svelte`:

```svelte
<script lang="ts">
	import type { MyWorkStats, PriorityKey } from '../../lib/stats';
	import { STATUS_COLOR, PRIORITY_COLOR } from '../../lib/colors';
	import { STATUS_ORDER, STATUS_LABEL, type TaskStatus } from '../../lib/types';
	export let stats: MyWorkStats;

	const R = 20;
	const CIRC = 2 * Math.PI * R;
	$: pct = Math.round(stats.completionRate * 100);
	$: offset = CIRC * (1 - stats.completionRate);

	$: statusSegs = ([...STATUS_ORDER, 'canceled'] as TaskStatus[])
		.map((s) => ({ key: s, label: STATUS_LABEL[s], count: stats.byStatus[s], color: STATUS_COLOR[s] }))
		.filter((seg) => seg.count > 0);
	$: statusTotal = statusSegs.reduce((n, s) => n + s.count, 0);

	const PRI_ORDER: PriorityKey[] = ['urgent', 'high', 'medium', 'low', 'none'];
	const PRI_LABEL: Record<PriorityKey, string> = {
		urgent: 'Urgent', high: 'High', medium: 'Medium', low: 'Low', none: 'No priority'
	};
	const PRI_COLOR: Record<PriorityKey, string> = { ...PRIORITY_COLOR, none: '#d1d5db' };
	$: priSegs = PRI_ORDER
		.map((p) => ({ key: p, label: PRI_LABEL[p], count: stats.byPriority[p], color: PRI_COLOR[p] }))
		.filter((seg) => seg.count > 0);
	$: priTotal = priSegs.reduce((n, s) => n + s.count, 0);
</script>

<div class="rounded-lg border border-gray-200 dark:border-gray-800 p-3 flex flex-col gap-4">
	<div class="flex items-center gap-3">
		<svg width="52" height="52" viewBox="0 0 52 52" class="flex-none" aria-hidden="true">
			<circle cx="26" cy="26" r={R} fill="none" stroke="currentColor" class="text-gray-200 dark:text-gray-800" stroke-width="5" />
			<circle cx="26" cy="26" r={R} fill="none" stroke="currentColor" class="text-primary" stroke-width="5"
				stroke-dasharray={CIRC} stroke-dashoffset={offset} stroke-linecap="round" transform="rotate(-90 26 26)" />
		</svg>
		<div>
			<div class="text-lg font-semibold">{pct}%</div>
			<div class="text-[11px] text-gray-500">Completion</div>
		</div>
	</div>

	<div>
		<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-1.5">By status</div>
		{#if statusTotal}
			<div class="flex h-2 rounded-full overflow-hidden">
				{#each statusSegs as s (s.key)}
					<div style="width:{(s.count / statusTotal) * 100}%; background:{s.color}" title="{s.label}: {s.count}"></div>
				{/each}
			</div>
			<div class="flex flex-wrap gap-x-3 gap-y-1 mt-2">
				{#each statusSegs as s (s.key)}
					<span class="inline-flex items-center gap-1 text-[11px] text-gray-500">
						<span class="w-2 h-2 rounded-full" style="background:{s.color}"></span>{s.label} {s.count}
					</span>
				{/each}
			</div>
		{:else}
			<div class="text-[11px] text-gray-400">No tasks</div>
		{/if}
	</div>

	<div>
		<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-1.5">By priority</div>
		{#if priTotal}
			<div class="flex h-2 rounded-full overflow-hidden">
				{#each priSegs as s (s.key)}
					<div style="width:{(s.count / priTotal) * 100}%; background:{s.color}" title="{s.label}: {s.count}"></div>
				{/each}
			</div>
			<div class="flex flex-wrap gap-x-3 gap-y-1 mt-2">
				{#each priSegs as s (s.key)}
					<span class="inline-flex items-center gap-1 text-[11px] text-gray-500">
						<span class="w-2 h-2 rounded-full" style="background:{s.color}"></span>{s.label} {s.count}
					</span>
				{/each}
			</div>
		{:else}
			<div class="text-[11px] text-gray-400">No tasks</div>
		{/if}
	</div>
</div>
```

- [ ] **Step 2: Typecheck**

Run: `npm run check`
Expected: no new errors referencing `InsightsPanel.svelte`.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/workos/views/commandcenter/InsightsPanel.svelte
git commit -m "feat(workos): My Work insights panel (completion ring + status/priority bars)"
```

---

### Task 6: ActivityRail component

Self-loads notifications on mount (so the rail is independent of the Inbox view), shows the latest ~8, and links out to the full Inbox.

**Files:**
- Create: `src/lib/components/workos/views/commandcenter/ActivityRail.svelte`

**Interfaces:**
- Consumes: `notifications`, `loadNotifications`, `openNotification`, `view` from `../../lib/store`; `summarizeNotification` from `../../lib/notifications`.

- [ ] **Step 1: Create the component**

Create `src/lib/components/workos/views/commandcenter/ActivityRail.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { notifications, loadNotifications, openNotification, view } from '../../lib/store';
	import { summarizeNotification } from '../../lib/notifications';

	onMount(loadNotifications);
	$: recent = $notifications.slice(0, 8);
</script>

<div class="rounded-lg border border-gray-200 dark:border-gray-800 p-3">
	<div class="flex items-center justify-between mb-2">
		<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold">Activity</div>
		<button type="button" class="text-[11px] text-primary hover:underline" onclick={() => view.set('inbox')}>See all</button>
	</div>
	{#if !recent.length}
		<div class="text-[11px] text-gray-400 py-2">You're all caught up.</div>
	{:else}
		<div class="flex flex-col gap-1">
			{#each recent as n (n.id)}
				<button
					type="button"
					class="flex items-start gap-2 text-left rounded-md px-1.5 py-1 hover:bg-gray-100 dark:hover:bg-gray-900"
					onclick={() => openNotification(n)}
				>
					<span class="mt-1.5 w-1.5 h-1.5 rounded-full flex-none {n.read ? 'bg-transparent' : 'bg-primary'}"></span>
					<span class="min-w-0">
						<span class="block text-xs truncate">{summarizeNotification(n)}</span>
						{#if n.data?.snippet}<span class="block text-[11px] text-gray-400 truncate">{n.data.snippet}</span>{/if}
					</span>
				</button>
			{/each}
		</div>
	{/if}
</div>
```

- [ ] **Step 2: Typecheck**

Run: `npm run check`
Expected: no new errors referencing `ActivityRail.svelte`.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/workos/views/commandcenter/ActivityRail.svelte
git commit -m "feat(workos): My Work activity rail (recent notifications)"
```

---

### Task 7: QuickLaunch component

Lists the distinct workstreams present in the user's tasks (most tasks first) and jumps to that workstream's board. New-task creation lives in the MyWorkView header (Task 9), not here, to avoid two entry points.

**Files:**
- Create: `src/lib/components/workos/views/commandcenter/QuickLaunch.svelte`

**Interfaces:**
- Consumes: `workspaces`, `workstreams`, `selectWorkstream`, `view` from `../../lib/store`; `Task` from `../../lib/types`; `Icon` from `../../ui/Icon.svelte`.
- Produces: prop `tasks: Task[]`.

- [ ] **Step 1: Create the component**

Create `src/lib/components/workos/views/commandcenter/QuickLaunch.svelte`:

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { workspaces, workstreams, selectWorkstream, view } from '../../lib/store';
	import type { Task } from '../../lib/types';
	export let tasks: Task[];

	$: streams = (() => {
		const counts = new Map<string, number>();
		for (const t of tasks) counts.set(t.workstream_id, (counts.get(t.workstream_id) ?? 0) + 1);
		return [...counts.entries()]
			.map(([id, count]) => {
				const ws = $workstreams.find((s) => s.id === id);
				const wsp = ws ? $workspaces.find((w) => w.id === ws.workspace_id) : null;
				return ws ? { id, count, label: `${wsp ? wsp.name + ' · ' : ''}${ws.name}` } : null;
			})
			.filter((x): x is { id: string; count: number; label: string } => x !== null)
			.sort((a, b) => b.count - a.count);
	})();

	async function go(id: string) {
		await selectWorkstream(id);
		view.set('board');
	}
</script>

<div class="rounded-lg border border-gray-200 dark:border-gray-800 p-3">
	<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-2">Quick launch</div>
	{#if streams.length}
		<div class="flex flex-col gap-0.5">
			{#each streams as s (s.id)}
				<button
					type="button"
					class="flex items-center gap-2 text-left rounded-md px-1.5 py-1 hover:bg-gray-100 dark:hover:bg-gray-900"
					onclick={() => go(s.id)}
				>
					<Icon name="layers" size={13} />
					<span class="flex-1 truncate text-xs">{s.label}</span>
					<span class="text-[11px] text-gray-400">{s.count}</span>
				</button>
			{/each}
		</div>
	{:else}
		<div class="text-[11px] text-gray-400">No workstreams yet</div>
	{/if}
</div>
```

- [ ] **Step 2: Typecheck**

Run: `npm run check`
Expected: no new errors referencing `QuickLaunch.svelte`.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/workos/views/commandcenter/QuickLaunch.svelte
git commit -m "feat(workos): My Work quick-launch workstream shortcuts"
```

---

### Task 8: TaskRow + FocusList components

Extract the existing list-row markup into a reusable `TaskRow`, then build `FocusList` = "Needs attention" hero + due-date buckets, both using `TaskRow`.

**Files:**
- Create: `src/lib/components/workos/views/commandcenter/TaskRow.svelte`
- Create: `src/lib/components/workos/views/commandcenter/FocusList.svelte`

**Interfaces:**
- TaskRow consumes: `STATUS_LABEL`, `Task` from `../../lib/types`; `openTask`, `displayName`, `initials` from `../../lib/store`. Prop: `task: Task`.
- FocusList consumes: `TaskRow`; `Icon` from `../../ui/Icon.svelte`; `Task` from `../../lib/types`; `bucketByDueDate`, `BUCKET_ORDER`, `BUCKET_LABEL` from `../../lib/buckets`; `needsAttention` from `../../lib/stats`. Props: `tasks: Task[]` (already segment+filter narrowed), `now: number`.
- FocusList produces: a `data-bucket="<key>"` attribute on each bucket section, so the orchestrator can scroll to `overdue`/`today`.

- [ ] **Step 1: Create TaskRow**

Create `src/lib/components/workos/views/commandcenter/TaskRow.svelte`:

```svelte
<script lang="ts">
	import { STATUS_LABEL, type Task } from '../../lib/types';
	import { openTask, displayName, initials } from '../../lib/store';
	export let task: Task;
	const fmt = (ms: number | null | undefined) => (ms == null ? '' : new Date(ms).toLocaleDateString());
</script>

<button
	type="button"
	class="flex items-center gap-3 px-3 py-2 text-left w-full hover:bg-gray-50 dark:hover:bg-gray-900"
	onclick={() => openTask(task.id)}
>
	<span class="text-[11px] text-gray-400 w-16 flex-none">{task.key}</span>
	<span class="flex-1 truncate text-sm">{task.title}</span>
	<span class="text-[11px] text-gray-400">{STATUS_LABEL[task.status]}</span>
	{#if task.due_date}<span class="text-[11px] text-gray-400 w-24 text-right">{fmt(task.due_date)}</span>{/if}
	<span class="flex -space-x-1.5">
		{#each (task.assignee_ids ?? []).slice(0, 3) as a (a)}
			<span class="w-6 h-6 rounded-full bg-gray-200 dark:bg-gray-700 text-[10px] flex items-center justify-center border border-white dark:border-gray-950" title={displayName(a)}>{initials(a)}</span>
		{/each}
	</span>
</button>
```

- [ ] **Step 2: Create FocusList**

Create `src/lib/components/workos/views/commandcenter/FocusList.svelte`:

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import TaskRow from './TaskRow.svelte';
	import type { Task } from '../../lib/types';
	import { bucketByDueDate, BUCKET_ORDER, BUCKET_LABEL } from '../../lib/buckets';
	import { needsAttention } from '../../lib/stats';
	export let tasks: Task[];
	export let now: number;

	$: attention = needsAttention(tasks, now);
	$: buckets = bucketByDueDate(tasks, now);
</script>

{#if !tasks.length}
	<div class="h-full flex flex-col items-center justify-center gap-2 text-center text-gray-400 py-16">
		<Icon name="check" size={28} />
		<div class="text-sm">Nothing on your plate yet</div>
	</div>
{:else}
	{#if attention.length}
		<div class="mb-5">
			<div class="text-[11px] uppercase tracking-wide text-primary font-semibold mb-2 px-1">Needs attention · {attention.length}</div>
			<div class="flex flex-col divide-y divide-gray-100 dark:divide-gray-900 rounded-lg border border-primary/40 bg-primary/5">
				{#each attention as t (t.id)}<TaskRow task={t} />{/each}
			</div>
		</div>
	{/if}
	{#each BUCKET_ORDER as bucket (bucket)}
		{#if buckets[bucket].length}
			<div class="mb-5" data-bucket={bucket}>
				<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-2 px-1">{BUCKET_LABEL[bucket]} · {buckets[bucket].length}</div>
				<div class="flex flex-col divide-y divide-gray-100 dark:divide-gray-900 rounded-lg border border-gray-200 dark:border-gray-800">
					{#each buckets[bucket] as t (t.id)}<TaskRow task={t} />{/each}
				</div>
			</div>
		{/if}
	{/each}
{/if}
```

- [ ] **Step 3: Typecheck**

Run: `npm run check`
Expected: no new errors referencing `TaskRow.svelte` or `FocusList.svelte`.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/commandcenter/TaskRow.svelte src/lib/components/workos/views/commandcenter/FocusList.svelte
git commit -m "feat(workos): extract TaskRow + FocusList (needs-attention hero + buckets)"
```

---

### Task 9: Rewrite MyWorkView as the command-center orchestrator

Wire the strip, insights, activity, quick-launch, and focus list into the two-column cockpit layout; own segment state, the two derived task sets (`segmentSet` for stats, `visible` for the list), the KPI-tile interaction, and the header new-task form.

**Files:**
- Modify (full rewrite): `src/lib/components/workos/views/MyWorkView.svelte`

**Interfaces:**
- Consumes: `user` from `$lib/stores`; `FilterBar` from `../chrome/FilterBar.svelte`; `Icon` from `../ui/Icon.svelte`; the five command-center components; `MyWorkSegment`, `TaskStatus` from `../lib/types`; `applyFilters` from `../lib/filters`; `computeStats` from `../lib/stats`; `myTasks`, `myWorkFilter`, `workstreams`, `loadMyWork`, `teardownMyWork`, `addTask` from `../lib/store`.

- [ ] **Step 1: Replace MyWorkView**

Overwrite `src/lib/components/workos/views/MyWorkView.svelte` with:

```svelte
<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { user } from '$lib/stores';
	import FilterBar from '../chrome/FilterBar.svelte';
	import Icon from '../ui/Icon.svelte';
	import StatStrip from './commandcenter/StatStrip.svelte';
	import InsightsPanel from './commandcenter/InsightsPanel.svelte';
	import ActivityRail from './commandcenter/ActivityRail.svelte';
	import QuickLaunch from './commandcenter/QuickLaunch.svelte';
	import FocusList from './commandcenter/FocusList.svelte';
	import { type MyWorkSegment, type TaskStatus } from '../lib/types';
	import { applyFilters } from '../lib/filters';
	import { computeStats } from '../lib/stats';
	import { myTasks, myWorkFilter, workstreams, loadMyWork, teardownMyWork, addTask } from '../lib/store';

	let segment: MyWorkSegment = 'all';
	const SEGMENTS: { k: MyWorkSegment; label: string }[] = [
		{ k: 'all', label: 'All' }, { k: 'assigned', label: 'Assigned' }, { k: 'created', label: 'Created' }
	];

	onMount(() => { void loadMyWork(); });
	onDestroy(() => teardownMyWork());

	$: uid = $user?.id ?? '';
	const now = Date.now();

	// segmentSet: segment-only — no FilterBar, no done/canceled hide. Feeds the stats.
	$: segmentSet = $myTasks.filter((t) =>
		segment === 'assigned' ? (t.assignee_ids ?? []).includes(uid)
		: segment === 'created' ? t.created_by_id === uid
		: true
	);
	$: stats = computeStats(segmentSet, now);

	// visible: the worked list set — segment + done/canceled hide + FilterBar (as before).
	$: statusFilterActive = $myWorkFilter.statuses.length > 0;
	$: visible = applyFilters(
		segmentSet.filter((t) => statusFilterActive || (t.status !== 'done' && t.status !== 'canceled')),
		$myWorkFilter
	);

	// KPI tile interaction: in-progress/done-this-week toggle a status facet; overdue/today scroll.
	let activeTile: string | null = null;
	let scroller: HTMLElement;
	function pickTile(key: string) {
		if (key === 'inProgress' || key === 'doneThisWeek') {
			const status: TaskStatus = key === 'inProgress' ? 'in_progress' : 'done';
			const on = $myWorkFilter.statuses.includes(status);
			myWorkFilter.update((f) => ({
				...f,
				statuses: on ? f.statuses.filter((s) => s !== status) : [...f.statuses, status]
			}));
			activeTile = on ? null : key;
		} else {
			const bucket = key === 'overdue' ? 'overdue' : 'today';
			scroller?.querySelector(`[data-bucket="${bucket}"]`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
			activeTile = key;
		}
	}

	// Cross-workstream new task: pick a target workstream (default = most recently updated task's).
	let creating = false;
	let newTitle = '';
	let target = '';
	$: defaultStream = [...$myTasks].sort((a, b) => b.updated_at - a.updated_at)[0]?.workstream_id ?? $workstreams[0]?.id ?? '';
	$: if (!target) target = defaultStream;
	async function submitNew() {
		if (!newTitle.trim() || !target) return;
		await addTask(target, { title: newTitle.trim() });
		newTitle = ''; creating = false;
	}
</script>

<div class="h-full flex flex-col min-h-0">
	<div class="flex-none flex items-center gap-2 px-4 pt-4">
		<h1 class="text-lg font-semibold">My Work</h1>
		<div class="flex-1"></div>
		<div class="inline-flex rounded-lg border border-gray-200 dark:border-gray-800 p-0.5 text-xs">
			{#each SEGMENTS as s (s.k)}
				<button type="button" class="px-3 py-1 rounded-md" class:bg-accent={segment === s.k} onclick={() => (segment = s.k)}>{s.label}</button>
			{/each}
		</div>
		{#if creating}
			<div class="flex items-center gap-1.5">
				<select class="text-sm rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent px-2 py-1" bind:value={target}>
					{#each $workstreams as s (s.id)}<option value={s.id}>{s.name}</option>{/each}
				</select>
				<input
					class="text-sm px-2 py-1 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent w-48"
					placeholder="Task title…"
					bind:value={newTitle}
					onkeydown={(e) => { if (e.key === 'Enter') submitNew(); if (e.key === 'Escape') { creating = false; newTitle = ''; } }}
					autofocus
				/>
			</div>
		{:else}
			<button type="button" class="text-sm px-3 py-1.5 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground inline-flex items-center gap-1" onclick={() => (creating = true)}>
				<Icon name="plus" size={15} /> New task
			</button>
		{/if}
	</div>

	<StatStrip {stats} active={activeTile} onPick={pickTile} />

	<FilterBar filter={myWorkFilter} showAssignee={false} />

	<div bind:this={scroller} class="flex-1 overflow-auto p-4 bg-white dark:bg-gray-950">
		<div class="grid grid-cols-1 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-4">
			<div class="min-w-0">
				<FocusList tasks={visible} {now} />
			</div>
			<div class="flex flex-col gap-3">
				<InsightsPanel {stats} />
				<ActivityRail />
				<QuickLaunch tasks={segmentSet} />
			</div>
		</div>
	</div>
</div>
```

- [ ] **Step 2: Typecheck**

Run: `npm run check`
Expected: no new errors. In particular, confirm `applyFilters`, `computeStats`, and all five component imports resolve.

- [ ] **Step 3: Run the full frontend test suite (regression)**

Run: `npx vitest run src/lib/components/workos/lib`
Expected: PASS — including the new `stats`/`notifications` tests and the untouched `buckets`/`filters`/`store` tests.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/MyWorkView.svelte
git commit -m "feat(workos): My Work command-center layout (stats + insights + activity + focus list)"
```

- [ ] **Step 5: Manual browser smoke (deferred — ask first)**

Per the standing "no Vite dev server without asking" rule, do NOT auto-start a server. When the user approves, verify against the running app:
- Stat tile counts match the list; "In progress"/"Done this week" toggle the list filter; "Overdue"/"Due today" scroll to that bucket.
- Segment toggle changes both the list and the stats/ring.
- Completion ring and the status/priority bars reflect the current segment.
- Activity rail shows recent notifications; clicking one navigates; "See all" → Inbox.
- New task: pick a workstream, submit, the task appears live in the list.
- Narrow the window → the rail drops below the list (single column).

---

## Self-Review

**1. Spec coverage** (against `docs/superpowers/specs/2026-06-27-workos-mywork-command-center-design.md`):
- §4 layout (header, KPI strip, FilterBar, 2fr/1fr grid collapsing to 1 col) → Task 9.
- §5 components (MyWorkView, StatStrip, InsightsPanel, ActivityRail, QuickLaunch, FocusList, lib/stats) → Tasks 1, 4–9. (Added `TaskRow` + `lib/colors` + `lib/notifications` as supporting units — DRY extractions noted below.)
- §6 stats (computeStats over `segmentSet`; needsAttention over `visible`; two input sets) → Tasks 1, 9.
- §7 interactions (tile soft-filter/scroll; segment; new-task workstream picker; activity see-all; empty/loading states) → Tasks 6, 7, 8 (empty states), 9.
- §8 backend none; activity rail self-loads notifications → Task 6 (deviation from spec's "MyWorkView loads it" — encapsulated in the rail instead; documented in the rail task).
- §9 testing (unit tests for stats; reuse buckets/filters; deferred manual smoke) → Tasks 1, 3, 9.
- §10 out of scope respected (no `/me/activity`, no migration).

**2. Placeholder scan:** No TBD/TODO; every code step contains full source. ✔

**3. Type consistency:** `MyWorkStats`/`PriorityKey` defined in Task 1 and consumed unchanged in Tasks 5, 9. `computeStats(tasks, now)` / `needsAttention(tasks, now)` signatures consistent across Tasks 1, 8, 9. `STATUS_COLOR`/`PRIORITY_COLOR` defined in Task 2, consumed in Tasks 2, 5. `summarizeNotification`/`openNotification` defined in Task 3, consumed in Tasks 3, 6. `onPick`/`active`/`stats` prop names consistent between Task 4 (StatStrip) and Task 9. ✔

**Refinements vs. spec (intentional, minor):**
- New-task UI consolidated into the MyWorkView header only (QuickLaunch is shortcuts-only) to avoid two new-task entry points.
- Added supporting units not named in the spec: `lib/colors.ts`, `lib/notifications.ts`, `views/commandcenter/TaskRow.svelte` — pure DRY extractions that keep components small and testable.
- ActivityRail self-loads notifications (better encapsulation than the orchestrator loading them).
