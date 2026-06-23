# WorkOS Board Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the WorkOS workstream board + topbar to match the TaskBoard mockup, with no backend or data-model changes and all current behavior preserved.

**Architecture:** Presentation-layer only. Extract the kanban card into a focused `TaskCard.svelte`; restyle column headers and add a (decorative) filter bar in `BoardView.svelte`; rebuild `Topbar.svelte` as a title row + tab row; extend the shared `Icon` glyph set and add one CSS keyframe. The one piece of real logic (date formatting + overdue detection) is extracted to a unit-tested helper.

**Tech Stack:** SvelteKit (Svelte 5 event syntax + legacy `$:` reactivity), Tailwind utility classes, SortableJS (drag-drop), Vitest (unit tests), svelte-check (types).

## Global Constraints

- No backend, status-enum, or data-model changes. The 5 statuses stay: `backlog`, `todo`, `in_progress`, `in_review`, `done` (board order excludes `canceled`).
- Drag-and-drop must keep working: preserve `data-status` on column drop targets and `data-task-id` / `data-sort-key` on each card, and the existing `handleEnd` / `moveTask` wiring.
- Decorative controls (Share, Automation, Overview/Calendar/Files tabs, filter pills, Advance Filters, per-card/column `…`, edit-pencil) render but are inert; mark them `aria-disabled="true"` and keep them as real `<button>`s.
- Accent color for redesigned board+topbar primary actions and the active tab is **indigo-600** (matches the mockup). The sidebar (teal) is out of scope and untouched.
- Every new surface has light + dark variants using the existing `dark:` utility pattern.
- Type-check command: `npm run check`. Frontend unit tests: `npx vitest run <path>`.

---

### Task 1: Visual primitives — Icon glyphs + spinner keyframe

Add the Lucide glyphs the new card/topbar need, plus a spin keyframe for the in-progress loader. Foundational; consumed by Tasks 3–5.

**Files:**
- Modify: `src/lib/components/workos/ui/Icon.svelte` (the `LUCIDE` map)
- Modify: `src/lib/components/workos/styles.css`

**Interfaces:**
- Produces: icon names usable via `<Icon name="..." />`: `flag`, `user`, `loader`, `sliders`, `pencil`, `share-2`, `zap`. CSS helper class `workos-spin`.

- [ ] **Step 1: Add the new glyphs to `Icon.svelte`**

In `src/lib/components/workos/ui/Icon.svelte`, the `LUCIDE` map currently ends with the `trash` entry on line 20:

```js
		trash: '<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>'
```

Add a trailing comma after it and append these entries (keep them inside the object literal):

```js
		trash: '<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
		flag: '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" x2="4" y1="22" y2="15"/>',
		user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
		loader: '<path d="M21 12a9 9 0 1 1-6.219-8.56"/>',
		sliders: '<line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/><line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/><line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/><line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/><line x1="16" x2="16" y1="18" y2="22"/>',
		pencil: '<path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/>',
		'share-2': '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" x2="15.42" y1="13.51" y2="17.49"/><line x1="15.41" x2="8.59" y1="6.51" y2="10.49"/>',
		zap: '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>'
```

- [ ] **Step 2: Add the spinner keyframe to `styles.css`**

Append to `src/lib/components/workos/styles.css`:

```css
@keyframes workos-spin {
	to { transform: rotate(360deg); }
}
.workos-spin {
	display: inline-flex;
	animation: workos-spin 0.8s linear infinite;
	transform-origin: center;
}
```

- [ ] **Step 3: Type-check**

Run: `npm run check`
Expected: PASS — no new errors referencing `Icon.svelte` or `styles.css`.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/ui/Icon.svelte src/lib/components/workos/styles.css
git commit -m "feat(workos): add board-redesign icons + spinner keyframe"
```

---

### Task 2: Date/overdue formatting helper (TDD)

The only real logic in the redesign: formatting a due date and deciding when it's overdue. Pure functions, fully unit-tested, so `TaskCard` stays presentational.

**Files:**
- Create: `src/lib/components/workos/lib/format.ts`
- Test: `src/lib/components/workos/lib/format.test.ts`

**Interfaces:**
- Consumes: `TaskStatus` from `./types`.
- Produces:
  - `formatDueDate(ts: number): string` — `"Jun 23"` at local midnight, `"Jun 23 · 09:30 AM"` otherwise.
  - `isOverdue(dueDate: number | null | undefined, status: TaskStatus, now: number): boolean`.

- [ ] **Step 1: Write the failing tests**

Create `src/lib/components/workos/lib/format.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { formatDueDate, isOverdue } from './format';

describe('formatDueDate', () => {
	it('shows date only at local midnight', () => {
		const ts = new Date(2026, 5, 23, 0, 0).getTime();
		const out = formatDueDate(ts);
		expect(out).toContain('Jun');
		expect(out).toContain('23');
		expect(out).not.toContain('·');
	});
	it('includes a time when the timestamp carries one', () => {
		const ts = new Date(2026, 5, 23, 9, 30).getTime();
		expect(formatDueDate(ts)).toContain('·');
	});
});

describe('isOverdue', () => {
	const now = new Date(2026, 5, 23, 12, 0).getTime();
	it('false when no due date', () => {
		expect(isOverdue(null, 'todo', now)).toBe(false);
		expect(isOverdue(undefined, 'todo', now)).toBe(false);
	});
	it('true when past due and not finished', () => {
		expect(isOverdue(now - 1000, 'in_progress', now)).toBe(true);
	});
	it('false when due in the future', () => {
		expect(isOverdue(now + 1000, 'todo', now)).toBe(false);
	});
	it('false when done or canceled even if past due', () => {
		expect(isOverdue(now - 1000, 'done', now)).toBe(false);
		expect(isOverdue(now - 1000, 'canceled', now)).toBe(false);
	});
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npx vitest run src/lib/components/workos/lib/format.test.ts`
Expected: FAIL — `Failed to resolve import "./format"` (file doesn't exist yet).

- [ ] **Step 3: Write the implementation**

Create `src/lib/components/workos/lib/format.ts`:

```ts
import type { TaskStatus } from './types';

/** "Jun 23" at local midnight, "Jun 23 · 09:30 AM" when the timestamp carries a time. */
export function formatDueDate(ts: number): string {
	const d = new Date(ts);
	const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
	if (d.getHours() === 0 && d.getMinutes() === 0) return date;
	const time = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
	return `${date} · ${time}`;
}

/** A task is overdue when it has a past due date and is not finished. */
export function isOverdue(
	dueDate: number | null | undefined,
	status: TaskStatus,
	now: number
): boolean {
	if (dueDate == null) return false;
	if (status === 'done' || status === 'canceled') return false;
	return dueDate < now;
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npx vitest run src/lib/components/workos/lib/format.test.ts`
Expected: PASS — all 6 tests green.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/format.ts src/lib/components/workos/lib/format.test.ts
git commit -m "feat(workos): add due-date format + overdue helpers"
```

---

### Task 3: TaskCard component

Extract the kanban card into a focused component with the mockup's row layout. Keeps drag attributes + click-to-open behavior.

**Files:**
- Create: `src/lib/components/workos/views/TaskCard.svelte`

**Interfaces:**
- Consumes: `formatDueDate`, `isOverdue` (Task 2); `initials`, `openTask` from `../lib/store`; icons `user`, `calendar`, `flag`, `loader`, `more-horizontal` (Task 1); `workos-spin` class (Task 1).
- Produces: `<TaskCard {task} {labelById} />` where `task: Task` and `labelById: Record<string, Label>`. Root element carries `data-task-id` and `data-sort-key` for SortableJS.

- [ ] **Step 1: Create the component**

Create `src/lib/components/workos/views/TaskCard.svelte`:

```svelte
<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import type { Task, Label } from '../lib/types';
	import { initials, openTask } from '../lib/store';
	import { formatDueDate, isOverdue } from '../lib/format';

	export let task: Task;
	export let labelById: Record<string, Label> = {};

	const PRIORITY_META: Record<string, { color: string; label: string }> = {
		urgent: { color: '#dc2626', label: 'Urgent Priority' },
		high: { color: '#ea580c', label: 'High Priority' },
		medium: { color: '#ca8a04', label: 'Medium Priority' },
		low: { color: '#6b7280', label: 'Low Priority' }
	};
	$: prio = task.priority ? PRIORITY_META[task.priority] : { color: '#9ca3af', label: 'No Priority' };
	$: overdue = isOverdue(task.due_date, task.status, Date.now());
</script>

<div
	data-task-id={task.id}
	data-sort-key={task.sort_key}
	class="bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 rounded-xl p-3.5 cursor-pointer hover:shadow-md transition-shadow"
	onclick={() => openTask(task.id)}
	role="button"
	tabindex="0"
>
	<!-- Title + spinner + menu -->
	<div class="flex items-start gap-2 mb-3">
		<div class="text-[15px] font-semibold leading-snug flex-1">{task.title}</div>
		{#if task.status === 'in_progress'}
			<span class="workos-spin text-indigo-500 flex-none mt-0.5"><Icon name="loader" size={15} /></span>
		{/if}
		<button
			class="text-gray-300 hover:text-gray-500 flex-none -mr-1"
			title="More"
			aria-disabled="true"
			onclick={(e) => e.stopPropagation()}
		>
			<Icon name="more-horizontal" size={16} />
		</button>
	</div>

	<!-- Assignee -->
	<div class="flex items-center gap-2 mb-2 text-gray-400">
		<Icon name="user" size={15} />
		{#if task.assignee_id}
			<span class="w-6 h-6 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-200 text-[10px] font-semibold inline-flex items-center justify-center">{initials(task.assignee_id)}</span>
		{:else}
			<span class="w-6 h-6 rounded-full border border-dashed border-gray-300 dark:border-gray-700 text-gray-400 text-[10px] inline-flex items-center justify-center">–</span>
		{/if}
	</div>

	<!-- Due date -->
	{#if task.due_date}
		<div class="flex items-center gap-2 mb-2 text-[13px] text-gray-500 dark:text-gray-400">
			<Icon name="calendar" size={15} />
			<span>{formatDueDate(task.due_date)}</span>
			{#if overdue}<span class="text-red-500 font-medium">Overdue</span>{/if}
		</div>
	{/if}

	<!-- Priority -->
	<div class="flex items-center gap-2 mb-1 text-[13px]" style="color:{prio.color}">
		<Icon name="flag" size={15} />
		<span>{prio.label}</span>
	</div>

	<!-- Labels -->
	{#if task.labels.length}
		<div class="flex flex-wrap gap-1 mt-2">
			{#each task.labels as lid (lid)}
				{#if labelById[lid]}
					<span class="inline-flex items-center gap-1 text-[11px] px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-800">
						<span class="w-2 h-2 rounded-full" style="background:{labelById[lid].color}"></span>{labelById[lid].name}
					</span>
				{/if}
			{/each}
		</div>
	{/if}
</div>
```

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: PASS — no errors in `TaskCard.svelte`. (It is not yet rendered anywhere; that happens in Task 4.)

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/workos/views/TaskCard.svelte
git commit -m "feat(workos): add TaskCard component (mockup card layout)"
```

---

### Task 4: BoardView — filter bar, restyled headers, TaskCard

Rewrite `BoardView.svelte` to add the decorative filter bar + functional "Add New", restyle column headers as colored chips, and render `<TaskCard>` in place of inline card markup. Drag-and-drop wiring is preserved exactly.

**Files:**
- Modify (full rewrite): `src/lib/components/workos/views/BoardView.svelte`

**Interfaces:**
- Consumes: `TaskCard` (Task 3); `tasksByStatus`, `currentWorkstream`, `labels`, `moveTask`, `addTask` from `../lib/store`; `STATUS_ORDER`, `STATUS_LABEL`, `TaskStatus` from `../lib/types`; icons `plus`, `chevron-down`, `sliders`, `more-horizontal` (Task 1).
- Produces: the board UI. No exported API.

- [ ] **Step 1: Replace the file contents**

Overwrite `src/lib/components/workos/views/BoardView.svelte` with:

```svelte
<script lang="ts">
	import Sortable from 'sortablejs';
	import { onDestroy, tick } from 'svelte';
	import Icon from '../ui/Icon.svelte';
	import TaskCard from './TaskCard.svelte';
	import { STATUS_ORDER, STATUS_LABEL, type TaskStatus } from '../lib/types';
	import { tasksByStatus, currentWorkstream, labels, moveTask, addTask } from '../lib/store';

	// Status accent colors — mirrors Pills' STATUS_COLOR.
	const STATUS_COLOR: Record<TaskStatus, string> = {
		backlog: '#9ca3af', todo: '#6b7280', in_progress: '#2563eb',
		in_review: '#7c3aed', done: '#16a34a', canceled: '#9ca3af'
	};

	const FILTERS = [
		{ k: 'Due Date', v: 'All' },
		{ k: 'Assignee', v: 'All' },
		{ k: 'Priority', v: 'All' }
	];

	let columnEls: Record<string, HTMLElement> = {};
	let sortables: Sortable[] = [];
	let adding: TaskStatus | null = null;
	let newTitle = '';
	let creatingTop = false;
	let topTitle = '';

	$: byStatus = $tasksByStatus;
	$: labelById = Object.fromEntries($labels.map((l) => [l.id, l]));

	function destroySortables() {
		sortables.forEach((s) => s.destroy());
		sortables = [];
	}

	async function initSortables() {
		destroySortables();
		await tick();
		for (const status of STATUS_ORDER) {
			const el = columnEls[status];
			if (!el) continue;
			sortables.push(
				new Sortable(el, {
					group: 'workos-tasks',
					animation: 150,
					ghostClass: 'opacity-40',
					onEnd: handleEnd
				})
			);
		}
	}

	async function handleEnd(evt: Sortable.SortableEvent) {
		const taskId = evt.item.getAttribute('data-task-id');
		const toStatus = (evt.to as HTMLElement).getAttribute('data-status') as TaskStatus | null;
		if (!taskId || !toStatus) return;
		const newIndex = evt.newIndex ?? 0;

		// Target column from the store, excluding the moved task; insert at newIndex.
		const col = (byStatus[toStatus] ?? []).filter((t) => t.id !== taskId);
		const before = newIndex > 0 ? col[newIndex - 1] : null;
		const after = col[newIndex] ?? null;

		// Revert the DOM move so the Svelte-rendered store stays the source of truth.
		const origin = evt.from as HTMLElement;
		origin.insertBefore(evt.item, origin.children[evt.oldIndex ?? 0] ?? null);

		await moveTask(taskId, toStatus, before ? before.sort_key : null, after ? after.sort_key : null);
	}

	// Re-init when the workstream changes (column nodes are recreated).
	let initedFor: string | null = null;
	$: if ($currentWorkstream && initedFor !== $currentWorkstream.id) {
		initedFor = $currentWorkstream.id;
		initSortables();
	}

	onDestroy(destroySortables);

	async function submitAdd(status: TaskStatus) {
		if (!newTitle.trim() || !$currentWorkstream) return;
		await addTask($currentWorkstream.id, { title: newTitle.trim(), status });
		newTitle = '';
		adding = null;
		await initSortables(); // attach the new card to the sortable list
	}

	async function submitTop() {
		if (!topTitle.trim() || !$currentWorkstream) return;
		await addTask($currentWorkstream.id, { title: topTitle.trim() });
		topTitle = '';
		creatingTop = false;
		await initSortables();
	}
</script>

<div class="h-full flex flex-col min-h-0">
	<!-- Filter bar: decorative controls + functional Add New -->
	<div class="flex-none flex items-center gap-2 px-4 py-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
		{#each FILTERS as f (f.k)}
			<button
				class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 text-xs hover:bg-gray-100 dark:hover:bg-gray-900"
				title="Coming soon"
				aria-disabled="true"
			>
				<span class="text-gray-400">{f.k}</span>
				<span class="font-medium text-gray-700 dark:text-gray-200">{f.v}</span>
				<Icon name="chevron-down" size={13} />
			</button>
		{/each}
		<button
			class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 text-xs hover:bg-gray-100 dark:hover:bg-gray-900"
			title="Coming soon"
			aria-disabled="true"
		>
			<Icon name="sliders" size={14} /> Advance Filters
		</button>

		<div class="flex-1"></div>

		{#if creatingTop}
			<input
				class="text-sm px-2 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent w-56"
				placeholder="Task title…"
				bind:value={topTitle}
				onkeydown={(e) => { if (e.key === 'Enter') submitTop(); if (e.key === 'Escape') { creatingTop = false; topTitle = ''; } }}
				autofocus
			/>
		{:else}
			<button
				class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium"
				onclick={() => (creatingTop = true)}
			>
				<Icon name="plus" size={15} /> Add New
			</button>
		{/if}
	</div>

	<!-- Columns -->
	<div class="flex-1 overflow-x-auto flex gap-4 p-4 box-border min-h-0">
		{#each STATUS_ORDER as status (status)}
			<div class="w-72 flex-none flex flex-col h-full">
				<div class="flex items-center gap-2 px-1 pb-3">
					<span
						class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold"
						style="background:{STATUS_COLOR[status]}1a; color:{STATUS_COLOR[status]}"
					>
						<span class="w-2 h-2 rounded-full" style="background:{STATUS_COLOR[status]}"></span>
						{STATUS_LABEL[status]}
					</span>
					<span class="text-xs text-gray-400 font-medium">{(byStatus[status] ?? []).length}</span>
					<div class="flex-1"></div>
					<button class="text-gray-300 hover:text-gray-500" title="More" aria-disabled="true"><Icon name="more-horizontal" size={16} /></button>
					<button class="text-gray-400 hover:text-gray-600" onclick={() => (adding = status)} title="Add task"><Icon name="plus" size={16} /></button>
				</div>

				<div bind:this={columnEls[status]} data-status={status} class="flex flex-col gap-2.5 overflow-y-auto flex-1 pb-4 min-h-[8px]">
					{#each byStatus[status] ?? [] as task (task.id)}
						<TaskCard {task} {labelById} />
					{/each}
				</div>

				{#if adding === status}
					<input
						class="mt-2 text-sm px-2 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent"
						placeholder="Task title…"
						bind:value={newTitle}
						onkeydown={(e) => { if (e.key === 'Enter') submitAdd(status); if (e.key === 'Escape') { adding = null; newTitle = ''; } }}
						autofocus
					/>
				{/if}
			</div>
		{/each}
	</div>
</div>
```

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: PASS — no errors in `BoardView.svelte` (note: `Pills` and `openTask` are intentionally no longer imported here).

- [ ] **Step 3: Browser smoke (drag-drop + add)**

With the app running (per the Open WebUI Windows run notes), open `/workos`, select a workstream, and confirm: cards render in the new style; column headers are colored chips with counts; dragging a card to another column persists (reload keeps it); the per-column `+` and the filter bar `+ Add New` both create a task. Capture a screenshot for the final report.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/BoardView.svelte
git commit -m "feat(workos): restyle board (filter bar, colored headers, TaskCard)"
```

---

### Task 5: Topbar — title row + tab row

Rebuild `Topbar.svelte` into the mockup's two-row header. Board/List tabs stay functional; Overview/Calendar/Files are inert. List view keeps an add entry point (the board has its own in the filter bar).

**Files:**
- Modify (full rewrite): `src/lib/components/workos/chrome/Topbar.svelte`

**Interfaces:**
- Consumes: `currentWorkstream`, `currentTeam`, `workspaces`, `view`, `tasks`, `initials`, `addTask` from `../lib/store`; icons `layers`, `pencil`, `share-2`, `zap`, `list`, `columns`, `calendar`, `paperclip`, `plus` (Tasks 1 + existing).
- Produces: the page header. No exported API. `view` values it sets remain `'board' | 'list'`.

- [ ] **Step 1: Replace the file contents**

Overwrite `src/lib/components/workos/chrome/Topbar.svelte` with:

```svelte
<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import { currentWorkstream, currentTeam, workspaces, view, tasks, initials, addTask } from '../lib/store';

	$: ws = $currentWorkstream;
	$: parentWorkspace = ws ? $workspaces.find((w) => w.id === ws.workspace_id) : null;

	// Decorative avatar stack: unique assignees on the current board (max 3).
	$: assignees = Array.from(new Set($tasks.map((t) => t.assignee_id).filter(Boolean))).slice(0, 3) as string[];

	const TABS = [
		{ key: 'overview', label: 'Overview', icon: 'layers', live: false },
		{ key: 'list', label: 'List', icon: 'list', live: true },
		{ key: 'board', label: 'Board', icon: 'columns', live: true },
		{ key: 'calendar', label: 'Calendar', icon: 'calendar', live: false },
		{ key: 'files', label: 'Files', icon: 'paperclip', live: false }
	];
	function selectTab(t: (typeof TABS)[number]) {
		if (t.live) view.set(t.key as 'board' | 'list');
	}

	// List view keeps an add entry point (board has its own in the filter bar).
	let creating = false;
	let title = '';
	async function submitNew() {
		if (!title.trim() || !ws) return;
		await addTask(ws.id, { title: title.trim() });
		title = '';
		creating = false;
	}
</script>

<header class="flex-none border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
	<!-- Title row -->
	<div class="h-14 flex items-center gap-3 px-4">
		<Icon name="layers" size={18} />
		<span class="text-base font-semibold truncate">
			{parentWorkspace ? `${parentWorkspace.name} · ` : ''}{ws?.name ?? $currentTeam?.name ?? 'WorkOS'}
		</span>
		{#if ws}
			<button class="text-gray-400 hover:text-gray-600" title="Rename" aria-disabled="true"><Icon name="pencil" size={15} /></button>
		{/if}

		<div class="flex-1"></div>

		{#if ws}
			{#if $view === 'list'}
				{#if creating}
					<input
						class="text-sm px-2 py-1 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent w-56"
						placeholder="Task title…"
						bind:value={title}
						onkeydown={(e) => { if (e.key === 'Enter') submitNew(); if (e.key === 'Escape') { creating = false; title = ''; } }}
						autofocus
					/>
				{:else}
					<button class="text-sm px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white inline-flex items-center gap-1" onclick={() => (creating = true)}>
						<Icon name="plus" size={15} /> New task
					</button>
				{/if}
			{/if}
			<div class="flex -space-x-2">
				{#each assignees as id (id)}
					<span class="w-7 h-7 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-200 border-2 border-white dark:border-gray-950 text-[10px] font-semibold inline-flex items-center justify-center" title={initials(id)}>{initials(id)}</span>
				{/each}
			</div>
			<button class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 inline-flex items-center gap-1.5 hover:bg-gray-100 dark:hover:bg-gray-900" aria-disabled="true"><Icon name="share-2" size={14} /> Share</button>
			<button class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 inline-flex items-center gap-1.5 hover:bg-gray-100 dark:hover:bg-gray-900" aria-disabled="true"><Icon name="zap" size={14} /> Automation</button>
		{/if}
	</div>

	<!-- Tab row -->
	{#if ws}
		<div class="flex items-center gap-1 px-4">
			{#each TABS as t (t.key)}
				<button
					class="px-3 py-2.5 text-sm inline-flex items-center gap-1.5 border-b-2 -mb-px {$view === t.key ? 'border-indigo-600 text-indigo-600 font-medium' : 'border-transparent text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}"
					class:opacity-60={!t.live}
					onclick={() => selectTab(t)}
					aria-disabled={!t.live}
				>
					<Icon name={t.icon} size={14} /> {t.label}
				</button>
			{/each}
		</div>
	{/if}
</header>
```

- [ ] **Step 2: Type-check**

Run: `npm run check`
Expected: PASS — no errors in `Topbar.svelte`.

- [ ] **Step 3: Browser smoke (tabs + list add)**

Confirm: title row shows breadcrumb + decorative edit/avatars/Share/Automation; tab row shows Overview/List/Board/Calendar/Files with the active tab underlined indigo; clicking Board/List switches views, Overview/Calendar/Files do nothing; in List view, the "New task" button creates a task; dark mode renders correctly. Capture a screenshot for the final report.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/chrome/Topbar.svelte
git commit -m "feat(workos): rebuild topbar (title row + tab row)"
```

---

## Self-Review

**Spec coverage (against `2026-06-23-workos-board-redesign-design.md`):**
- §4.1 Topbar rebuild → Task 5. ✓
- §4.2 BoardView filter bar + colored headers + DnD preserved → Task 4. ✓
- §4.3 TaskCard layout (title/spinner, assignee, date+overdue, priority, labels) → Task 3. ✓
- §4.4 Icon glyphs → Task 1. ✓
- §4.5 styles.css spin keyframe → Task 1. ✓
- §5 data mapping → Tasks 2 (date/overdue), 3 (card fields). ✓
- §6 theming/a11y (dark variants, `aria-disabled`, text alongside color) → Tasks 3–5. ✓
- §7 testing (svelte-check, unit test for the helper, browser smoke) → all tasks. ✓
- §2 non-goals (no backend/enum changes, no sidebar/List restyle) → respected; List add entry point preserved without restyling List. ✓

**Placeholder scan:** No TBD/TODO; every code step contains full content; no "similar to Task N". ✓

**Type consistency:** `formatDueDate(ts)` / `isOverdue(dueDate, status, now)` signatures match between Task 2's definition and Task 3's use. `<TaskCard {task} {labelById} />` props match the component's `export let`. `STATUS_COLOR` keys cover all `TaskStatus` values. `view.set` only receives `'board' | 'list'`. Icon names used in Tasks 3–5 are all added in Task 1 or already exist (`layers`, `list`, `columns`, `calendar`, `paperclip`, `plus`, `chevron-down`, `more-horizontal`). ✓
