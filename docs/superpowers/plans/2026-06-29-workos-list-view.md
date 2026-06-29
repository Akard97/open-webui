# WorkOS List View Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the WorkOS List view as a status-grouped, inline-editable table (no Kanban feel) with user-configurable, browser-persisted columns.

**Architecture:** Pure, testable helpers (column metadata + grid-template builder, status→glyph map) go in `lib/`. A `localStorage`-persisted `listColumns` store mirrors the existing `navCollapsed` pattern. Four small list-tuned cell components (status / priority / due date / progress) plus the reused `AssigneeField` are composed by a rewritten `ListView.svelte` that groups tasks by status into collapsible cards. All editing reuses existing store actions (`editTask`, `addTask`, `removeTask`).

**Tech Stack:** SvelteKit (Svelte 5 runes-era syntax as used in the repo), TypeScript, Tailwind, shadcn-svelte (`DropdownMenu`), Vitest.

## Global Constraints

- Accent color is the Osool **teal** brand: Tailwind `text-primary` / `bg-primary` / `brand-*`. Never indigo/purple.
- Status colors come from `lib/colors.ts` `STATUS_COLOR`; priority colors from `PRIORITY_COLOR`. Do not introduce new status/priority color values.
- Iterate `STATUS_ORDER` (`backlog, todo, in_progress, in_review, done`) — there is **no `canceled` group**; canceled tasks are not shown (preserves Board/List parity).
- All task mutations reuse existing store exports: `editTask`, `addTask`, `removeTask`. No backend, API, or realtime-event changes.
- Column visibility persists to `localStorage` under key `workos:list-columns`.
- **Do NOT start a Vite dev server for smoke testing.** Browser smoke is a manual follow-up the user runs.
- Match existing file conventions: tabs for indentation, `export let` props, `$lib/...` import aliases.
- Frontend tests run with `npm run test:frontend` (vitest). Type/Svelte check runs with `npm run check`.

---

### Task 1: Column metadata + grid-template helpers (`lib/columns.ts`)

Pure module (no Svelte/`$app` imports) so it is unit-testable in isolation. Owns the optional-column list, the preference shape + parsing, and the grid-template builder.

**Files:**
- Create: `src/lib/components/workos/lib/columns.ts`
- Test: `src/lib/components/workos/lib/columns.test.ts`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `type ListColumnKey = 'assignee' | 'due' | 'priority' | 'labels' | 'progress'`
  - `interface ListColumnMeta { key: ListColumnKey; label: string }`
  - `const LIST_COLUMNS: ListColumnMeta[]` (fixed order: assignee, due, priority, labels, progress)
  - `type ColumnPrefs = Record<ListColumnKey, boolean>`
  - `function defaultColumnPrefs(): ColumnPrefs` (all `true`)
  - `function parseColumnPrefs(raw: string | null): ColumnPrefs` (safe-merge over defaults)
  - `function gridTemplate(prefs: ColumnPrefs): string`

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/workos/lib/columns.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { defaultColumnPrefs, parseColumnPrefs, gridTemplate, LIST_COLUMNS } from './columns';

describe('LIST_COLUMNS', () => {
	it('lists the five optional columns in fixed order', () => {
		expect(LIST_COLUMNS.map((c) => c.key)).toEqual(['assignee', 'due', 'priority', 'labels', 'progress']);
	});
});

describe('defaultColumnPrefs', () => {
	it('enables every optional column', () => {
		expect(defaultColumnPrefs()).toEqual({
			assignee: true, due: true, priority: true, labels: true, progress: true
		});
	});
});

describe('parseColumnPrefs', () => {
	it('returns defaults for null', () => {
		expect(parseColumnPrefs(null)).toEqual(defaultColumnPrefs());
	});
	it('returns defaults for invalid JSON', () => {
		expect(parseColumnPrefs('not json')).toEqual(defaultColumnPrefs());
	});
	it('merges a partial object over defaults', () => {
		expect(parseColumnPrefs('{"labels":false,"progress":false}')).toEqual({
			assignee: true, due: true, priority: true, labels: false, progress: false
		});
	});
	it('ignores unknown keys and non-boolean values', () => {
		expect(parseColumnPrefs('{"bogus":true,"assignee":"yes"}')).toEqual(defaultColumnPrefs());
	});
});

describe('gridTemplate', () => {
	it('builds name + all columns + menu when everything is visible', () => {
		expect(gridTemplate(defaultColumnPrefs())).toBe(
			'minmax(180px, 1fr) 120px 120px 130px 160px 120px 36px'
		);
	});
	it('omits hidden columns but keeps name and menu', () => {
		expect(gridTemplate({ assignee: true, due: true, priority: true, labels: false, progress: false })).toBe(
			'minmax(180px, 1fr) 120px 120px 130px 36px'
		);
	});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/lib/components/workos/lib/columns.test.ts`
Expected: FAIL — cannot resolve `./columns`.

- [ ] **Step 3: Write the implementation**

Create `src/lib/components/workos/lib/columns.ts`:

```ts
export type ListColumnKey = 'assignee' | 'due' | 'priority' | 'labels' | 'progress';

export interface ListColumnMeta {
	key: ListColumnKey;
	label: string;
}

// Fixed left-to-right order of the optional columns (Name is always first, the row
// menu is always last — neither is configurable).
export const LIST_COLUMNS: ListColumnMeta[] = [
	{ key: 'assignee', label: 'Assignee' },
	{ key: 'due', label: 'Due date' },
	{ key: 'priority', label: 'Priority' },
	{ key: 'labels', label: 'Labels' },
	{ key: 'progress', label: 'Progress' }
];

export type ColumnPrefs = Record<ListColumnKey, boolean>;

export function defaultColumnPrefs(): ColumnPrefs {
	return { assignee: true, due: true, priority: true, labels: true, progress: true };
}

// Merge a persisted preference string over the defaults, tolerating missing keys,
// unknown keys, non-boolean values, and malformed JSON (always returns a full set).
export function parseColumnPrefs(raw: string | null): ColumnPrefs {
	const prefs = defaultColumnPrefs();
	if (!raw) return prefs;
	try {
		const parsed = JSON.parse(raw);
		if (!parsed || typeof parsed !== 'object') return prefs;
		for (const { key } of LIST_COLUMNS) {
			if (typeof (parsed as Record<string, unknown>)[key] === 'boolean') {
				prefs[key] = (parsed as Record<string, boolean>)[key];
			}
		}
		return prefs;
	} catch {
		return prefs;
	}
}

const NAME_WIDTH = 'minmax(180px, 1fr)';
const MENU_WIDTH = '36px';
const COLUMN_WIDTH: Record<ListColumnKey, string> = {
	assignee: '120px',
	due: '120px',
	priority: '130px',
	labels: '160px',
	progress: '120px'
};

// CSS grid-template-columns for one row: name (flexible) + each visible optional
// column (fixed) + trailing menu column. Header and task rows share this template.
export function gridTemplate(prefs: ColumnPrefs): string {
	const cols = [NAME_WIDTH];
	for (const { key } of LIST_COLUMNS) if (prefs[key]) cols.push(COLUMN_WIDTH[key]);
	cols.push(MENU_WIDTH);
	return cols.join(' ');
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:frontend -- src/lib/components/workos/lib/columns.test.ts`
Expected: PASS (all cases green).

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/columns.ts src/lib/components/workos/lib/columns.test.ts
git commit -m "feat(workos): list column metadata + grid-template helpers"
```

---

### Task 2: `statusShape` helper (`lib/colors.ts`)

Centralize the status→`StatusDot` glyph mapping (today duplicated in `BoardView` and `TaskDetail`) so the new `StatusCell` reuses it. Uses the Board's canonical mapping.

**Files:**
- Modify: `src/lib/components/workos/lib/colors.ts`
- Test: `src/lib/components/workos/lib/colors.test.ts`

**Interfaces:**
- Consumes: `TaskStatus` from `./types`.
- Produces:
  - `type StatusShape = 'dashed' | 'ring' | 'half' | 'check' | 'x'`
  - `function statusShape(s: TaskStatus): StatusShape`

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/workos/lib/colors.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { statusShape } from './colors';

describe('statusShape', () => {
	it('maps each status to its board glyph shape', () => {
		expect(statusShape('backlog')).toBe('dashed');
		expect(statusShape('todo')).toBe('ring');
		expect(statusShape('in_progress')).toBe('half');
		expect(statusShape('in_review')).toBe('half');
		expect(statusShape('done')).toBe('check');
		expect(statusShape('canceled')).toBe('x');
	});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm run test:frontend -- src/lib/components/workos/lib/colors.test.ts`
Expected: FAIL — `statusShape` is not exported.

- [ ] **Step 3: Write the implementation**

Append to `src/lib/components/workos/lib/colors.ts` (keep the existing `STATUS_COLOR` / `PRIORITY_COLOR` exports):

```ts
export type StatusShape = 'dashed' | 'ring' | 'half' | 'check' | 'x';

// State-shaped glyph per status, matching the Board's StatusDot rendering.
export const STATUS_SHAPE: Record<TaskStatus, StatusShape> = {
	backlog: 'dashed', todo: 'ring', in_progress: 'half',
	in_review: 'half', done: 'check', canceled: 'x'
};

export function statusShape(s: TaskStatus): StatusShape {
	return STATUS_SHAPE[s];
}
```

The file already imports `TaskStatus` at the top (`import type { TaskStatus, TaskPriority } from './types';`) — no new import needed.

- [ ] **Step 4: Run test to verify it passes**

Run: `npm run test:frontend -- src/lib/components/workos/lib/colors.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/colors.ts src/lib/components/workos/lib/colors.test.ts
git commit -m "feat(workos): shared statusShape glyph helper"
```

---

### Task 3: Persisted `listColumns` store (`lib/store.ts`)

Add the column-preference writable, persisted to `localStorage`, mirroring the existing `navCollapsed` wiring.

**Files:**
- Modify: `src/lib/components/workos/lib/store.ts`

**Interfaces:**
- Consumes: `defaultColumnPrefs`, `parseColumnPrefs`, `type ColumnPrefs` from `./columns`.
- Produces: `export const listColumns: Writable<ColumnPrefs>`.

- [ ] **Step 1: Add the import**

In `src/lib/components/workos/lib/store.ts`, add near the other `./` imports (e.g. after the `import { applyFilters, emptyFilter } from './filters';` line):

```ts
import { defaultColumnPrefs, parseColumnPrefs, type ColumnPrefs } from './columns';
```

- [ ] **Step 2: Add the persisted writable**

Immediately after the existing `navCollapsed` block (the lines defining `NAV_COLLAPSED_KEY`, `navCollapsed`, and its `subscribe`), add:

```ts
// List column visibility, persisted per browser like the sidebar flag.
const LIST_COLUMNS_KEY = 'workos:list-columns';
export const listColumns: Writable<ColumnPrefs> = writable(
	browser ? parseColumnPrefs(localStorage.getItem(LIST_COLUMNS_KEY)) : defaultColumnPrefs()
);
if (browser) listColumns.subscribe((v) => localStorage.setItem(LIST_COLUMNS_KEY, JSON.stringify(v)));
```

`writable`, `Writable`, and `browser` are already imported at the top of `store.ts`.

- [ ] **Step 3: Verify it type-checks**

Run: `npm run check`
Expected: no new errors referencing `store.ts` or `columns`.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/lib/store.ts
git commit -m "feat(workos): persisted listColumns preference store"
```

---

### Task 4: `AssigneeField` placeholder prop

Let the reused assignee field show "Assign" (the list's empty placeholder) without changing the drawer, which keeps "Unassigned".

**Files:**
- Modify: `src/lib/components/workos/views/detail/AssigneeField.svelte`

**Interfaces:**
- Produces: `AssigneeField` now accepts an optional `placeholder` prop (default `'Unassigned'`).

- [ ] **Step 1: Add the prop**

In `AssigneeField.svelte`, change the props line:

```svelte
	export let task: Task;
```

to:

```svelte
	export let task: Task;
	export let placeholder = 'Unassigned';
```

- [ ] **Step 2: Use the prop in the empty branch**

Replace the empty-state text `Unassigned` in the trigger:

```svelte
			<span class="inline-flex items-center gap-1.5 text-sm text-gray-400">
				<Icon name="user" size={15} /> Unassigned
			</span>
```

with:

```svelte
			<span class="inline-flex items-center gap-1.5 text-sm text-gray-400">
				<Icon name="user" size={15} /> {placeholder}
			</span>
```

- [ ] **Step 3: Verify it type-checks**

Run: `npm run check`
Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/detail/AssigneeField.svelte
git commit -m "feat(workos): AssigneeField placeholder prop"
```

---

### Task 5: Inline cell components (`views/cells/`)

Four small, list-tuned cells. Status / priority / due reuse the drawer's editing patterns (DropdownMenu / native date input → `editTask`); progress is read-only.

**Files:**
- Create: `src/lib/components/workos/views/cells/StatusCell.svelte`
- Create: `src/lib/components/workos/views/cells/PriorityCell.svelte`
- Create: `src/lib/components/workos/views/cells/DueDateCell.svelte`
- Create: `src/lib/components/workos/views/cells/ProgressCell.svelte`

**Interfaces:**
- Consumes: `editTask` (store), `STATUS_COLOR`/`PRIORITY_COLOR`/`statusShape` (colors), `STATUS_ORDER`/`STATUS_LABEL`/`PRIORITY_ORDER` (types), `formatDueDate` (format), `actualProgress` (progress), `StatusDot`, `Icon`, `DropdownMenu`.
- Produces: four components, each taking `export let task: Task;`.

- [ ] **Step 1: Create `StatusCell.svelte`**

`src/lib/components/workos/views/cells/StatusCell.svelte`:

```svelte
<script lang="ts">
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import StatusDot from '../../ui/StatusDot.svelte';
	import { STATUS_ORDER, STATUS_LABEL, type TaskStatus, type Task } from '../../lib/types';
	import { STATUS_COLOR, statusShape } from '../../lib/colors';
	import { editTask } from '../../lib/store';

	export let task: Task;
</script>

<DropdownMenu.Root>
	<DropdownMenu.Trigger
		title="Change status"
		class="inline-flex items-center justify-center rounded-full p-0.5 hover:bg-gray-100 dark:hover:bg-gray-800"
	>
		<StatusDot shape={statusShape(task.status)} color={STATUS_COLOR[task.status]} size={16} />
	</DropdownMenu.Trigger>
	<DropdownMenu.Content align="start">
		{#each STATUS_ORDER as s (s)}
			<DropdownMenu.Item onSelect={() => editTask(task.id, { status: s })}>
				<span class="inline-flex items-center gap-2">
					<StatusDot shape={statusShape(s)} color={STATUS_COLOR[s]} /> {STATUS_LABEL[s]}
				</span>
			</DropdownMenu.Item>
		{/each}
		<DropdownMenu.Item onSelect={() => editTask(task.id, { status: 'canceled' as TaskStatus })}>
			<span class="inline-flex items-center gap-2">
				<StatusDot shape="x" color={STATUS_COLOR.canceled} /> {STATUS_LABEL.canceled}
			</span>
		</DropdownMenu.Item>
	</DropdownMenu.Content>
</DropdownMenu.Root>
```

- [ ] **Step 2: Create `PriorityCell.svelte`**

`src/lib/components/workos/views/cells/PriorityCell.svelte`:

```svelte
<script lang="ts">
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import Icon from '../../ui/Icon.svelte';
	import { PRIORITY_ORDER, type TaskPriority, type Task } from '../../lib/types';
	import { PRIORITY_COLOR } from '../../lib/colors';
	import { editTask } from '../../lib/store';

	export let task: Task;

	const LABEL: Record<TaskPriority, string> = {
		urgent: 'Urgent', high: 'High', medium: 'Medium', low: 'Low'
	};
</script>

<DropdownMenu.Root>
	<DropdownMenu.Trigger
		title="Set priority"
		class="inline-flex items-center gap-1.5 rounded-md px-1 -mx-1 py-0.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-800"
	>
		{#if task.priority}
			<span style="color:{PRIORITY_COLOR[task.priority]}"><Icon name="flag" size={15} /></span>
			<span>{LABEL[task.priority]}</span>
		{:else}
			<span class="text-gray-300 dark:text-gray-600"><Icon name="flag" size={15} /></span>
		{/if}
	</DropdownMenu.Trigger>
	<DropdownMenu.Content align="start">
		<DropdownMenu.Item onSelect={() => editTask(task.id, { priority: null })}>
			<span class="text-gray-400">No priority</span>
		</DropdownMenu.Item>
		{#each PRIORITY_ORDER as p (p)}
			<DropdownMenu.Item onSelect={() => editTask(task.id, { priority: p })}>
				<span class="inline-flex items-center gap-2">
					<span style="color:{PRIORITY_COLOR[p]}"><Icon name="flag" size={14} /></span> {LABEL[p]}
				</span>
			</DropdownMenu.Item>
		{/each}
	</DropdownMenu.Content>
</DropdownMenu.Root>
```

- [ ] **Step 3: Create `DueDateCell.svelte`**

`src/lib/components/workos/views/cells/DueDateCell.svelte`:

```svelte
<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { editTask } from '../../lib/store';
	import { formatDueDate } from '../../lib/format';
	import type { Task } from '../../lib/types';

	export let task: Task;
	let editing = false;

	function commit(v: string) {
		editTask(task.id, { due_date: v ? new Date(v).getTime() : null });
		editing = false;
	}
</script>

{#if editing}
	<!-- svelte-ignore a11y_autofocus -->
	<input
		type="date"
		class="text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded px-1.5 py-0.5"
		value={task.due_date ? new Date(task.due_date).toISOString().slice(0, 10) : ''}
		onchange={(e) => commit((e.target as HTMLInputElement).value)}
		onblur={() => (editing = false)}
		autofocus
	/>
{:else}
	<button
		class="inline-flex items-center gap-1.5 rounded-md px-1 -mx-1 py-0.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-800 {task.due_date ? 'text-gray-600 dark:text-gray-300' : 'text-gray-400'}"
		onclick={() => (editing = true)}
	>
		{#if task.due_date}
			{formatDueDate(task.due_date)}
		{:else}
			<Icon name="calendar" size={14} /> Add date
		{/if}
	</button>
{/if}
```

- [ ] **Step 4: Create `ProgressCell.svelte`**

`src/lib/components/workos/views/cells/ProgressCell.svelte`:

```svelte
<script lang="ts">
	import { actualProgress } from '../../lib/progress';
	import type { Task } from '../../lib/types';

	export let task: Task;
	$: pct = actualProgress(task);
</script>

{#if task.status === 'in_progress'}
	<div class="flex items-center gap-2">
		<span class="flex-1 h-1.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
			<span class="block h-full bg-primary rounded-full" style="width:{pct}%"></span>
		</span>
		<span class="text-xs text-gray-400 tabular-nums w-7 text-right">{pct}</span>
	</div>
{:else}
	<span class="text-gray-300 dark:text-gray-600">—</span>
{/if}
```

- [ ] **Step 5: Verify all four type-check**

Run: `npm run check`
Expected: no new errors referencing the four cell files.

- [ ] **Step 6: Commit**

```bash
git add src/lib/components/workos/views/cells/
git commit -m "feat(workos): inline list cells (status, priority, due date, progress)"
```

---

### Task 6: Rewrite `ListView.svelte`

Compose the toolbar (FilterBar + Columns picker), status-grouped collapsible cards, dynamic column header + rows, per-group inline add, and the row menu.

**Files:**
- Modify (full rewrite): `src/lib/components/workos/views/ListView.svelte`

**Interfaces:**
- Consumes: `tasksByStatus`, `openTask`, `removeTask`, `addTask`, `directory`, `labels`, `boardFilter`, `listColumns`, `currentWorkstream`, `currentTeam`, `roles` (store); `LIST_COLUMNS`, `gridTemplate` (columns); `STATUS_ORDER`, `STATUS_LABEL` (types); `STATUS_COLOR`, `statusShape` (colors); `canDeleteTask` (roles); `user` (`$lib/stores`); `StatusCell`/`PriorityCell`/`DueDateCell`/`ProgressCell`/`AssigneeField`/`Icon`/`StatusDot`; shadcn `DropdownMenu`, `cn`, `buttonVariants`.

- [ ] **Step 1: Replace the file contents**

Overwrite `src/lib/components/workos/views/ListView.svelte` with:

```svelte
<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import StatusDot from '../ui/StatusDot.svelte';
	import FilterBar from '../chrome/FilterBar.svelte';
	import AssigneeField from './detail/AssigneeField.svelte';
	import StatusCell from './cells/StatusCell.svelte';
	import PriorityCell from './cells/PriorityCell.svelte';
	import DueDateCell from './cells/DueDateCell.svelte';
	import ProgressCell from './cells/ProgressCell.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { cn } from '$lib/components/ui/utils.js';
	import { buttonVariants } from '$lib/components/ui/button';
	import { STATUS_ORDER, STATUS_LABEL, type TaskStatus } from '../lib/types';
	import { STATUS_COLOR, statusShape } from '../lib/colors';
	import { LIST_COLUMNS, gridTemplate } from '../lib/columns';
	import { canDeleteTask } from '../lib/roles';
	import { user } from '$lib/stores';
	import {
		tasksByStatus, openTask, removeTask, addTask, directory, labels,
		boardFilter, listColumns, currentWorkstream, currentTeam, roles
	} from '../lib/store';

	$: byStatus = $tasksByStatus;
	$: void $directory; // re-render when names load
	$: labelById = Object.fromEntries($labels.map((l) => [l.id, l]));
	$: template = gridTemplate($listColumns);
	$: myRole = $currentTeam ? $roles[$currentTeam.id] : undefined;

	// Ephemeral UI state (not persisted): collapsed groups + per-group quick-add.
	let collapsed: Record<string, boolean> = {};
	let adding: TaskStatus | null = null;
	let newTitle = '';

	function toggle(s: TaskStatus) {
		collapsed = { ...collapsed, [s]: !collapsed[s] };
	}

	async function submitAdd(status: TaskStatus) {
		const ws = $currentWorkstream;
		if (!newTitle.trim() || !ws) return;
		await addTask(ws.id, { title: newTitle.trim(), status });
		newTitle = '';
		adding = null;
	}
</script>

<div class="h-full flex flex-col min-h-0">
	<FilterBar filter={boardFilter} />

	<!-- List toolbar: column picker (right-aligned) -->
	<div class="flex-none flex items-center justify-end px-4 py-2 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
		<DropdownMenu.Root>
			<DropdownMenu.Trigger class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 text-sm hover:bg-gray-100 dark:hover:bg-gray-900">
				<Icon name="sliders" size={14} /> Columns <Icon name="chevron-down" size={13} />
			</DropdownMenu.Trigger>
			<DropdownMenu.Content align="end">
				{#each LIST_COLUMNS as c (c.key)}
					<DropdownMenu.CheckboxItem
						checked={$listColumns[c.key]}
						closeOnSelect={false}
						onCheckedChange={(v) => listColumns.update((p) => ({ ...p, [c.key]: !!v }))}
					>{c.label}</DropdownMenu.CheckboxItem>
				{/each}
			</DropdownMenu.Content>
		</DropdownMenu.Root>
	</div>

	<!-- Grouped, collapsible status sections -->
	<div class="flex-1 overflow-auto p-4 space-y-3">
		{#each STATUS_ORDER as status (status)}
			{#if (byStatus[status] ?? []).length}
				<section class="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 overflow-hidden">
					<!-- Group header -->
					<div class="flex items-center gap-2 px-3 py-2.5">
						<button class="text-gray-400 hover:text-gray-600" onclick={() => toggle(status)} title={collapsed[status] ? 'Expand' : 'Collapse'}>
							<Icon name={collapsed[status] ? 'chevron-right' : 'chevron-down'} size={16} />
						</button>
						<span
							class="inline-flex items-center gap-2 px-2.5 py-1 rounded-full text-[13px] font-medium"
							style="background:{STATUS_COLOR[status]}24; color:{STATUS_COLOR[status]}"
						>
							<StatusDot shape={statusShape(status)} color={STATUS_COLOR[status]} size={14} />
							{STATUS_LABEL[status]}
						</span>
						<span class="text-xs text-gray-400">{byStatus[status].length}</span>
					</div>

					{#if !collapsed[status]}
						<!-- Column header -->
						<div class="grid items-center gap-3 px-3 py-1.5 border-t border-gray-100 dark:border-gray-900 text-xs text-gray-400" style="grid-template-columns: {template};">
							<span style="padding-left: 26px;">Name</span>
							{#if $listColumns.assignee}<span>Assignee</span>{/if}
							{#if $listColumns.due}<span>Due date</span>{/if}
							{#if $listColumns.priority}<span>Priority</span>{/if}
							{#if $listColumns.labels}<span>Labels</span>{/if}
							{#if $listColumns.progress}<span>Progress</span>{/if}
							<span></span>
						</div>

						<!-- Task rows -->
						{#each byStatus[status] as task (task.id)}
							<div class="group grid items-center gap-3 px-3 py-2 border-t border-gray-100 dark:border-gray-900 hover:bg-gray-50 dark:hover:bg-gray-900/50" style="grid-template-columns: {template};">
								<!-- Name (status circle + title) -->
								<span class="inline-flex items-center gap-2.5 min-w-0">
									<StatusCell {task} />
									<button class="text-sm font-medium truncate text-left hover:text-primary" onclick={() => openTask(task.id)}>{task.title}</button>
								</span>

								{#if $listColumns.assignee}
									<span class="min-w-0"><AssigneeField {task} placeholder="Assign" /></span>
								{/if}
								{#if $listColumns.due}
									<span class="min-w-0"><DueDateCell {task} /></span>
								{/if}
								{#if $listColumns.priority}
									<span class="min-w-0"><PriorityCell {task} /></span>
								{/if}
								{#if $listColumns.labels}
									<span class="flex items-center gap-1 min-w-0 overflow-hidden">
										{#each (task.labels ?? []).slice(0, 2) as lid (lid)}
											{#if labelById[lid]}
												<span class="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded-full bg-gray-100 dark:bg-gray-800 whitespace-nowrap">
													<span class="w-1.5 h-1.5 rounded-full" style="background:{labelById[lid].color}"></span>{labelById[lid].name}
												</span>
											{/if}
										{/each}
										{#if (task.labels?.length ?? 0) > 2}
											<span class="text-[11px] text-gray-400">+{(task.labels?.length ?? 0) - 2}</span>
										{:else if !(task.labels?.length)}
											<span class="text-gray-300 dark:text-gray-600">—</span>
										{/if}
									</span>
								{/if}
								{#if $listColumns.progress}
									<span class="min-w-0"><ProgressCell {task} /></span>
								{/if}

								<!-- Row menu -->
								<DropdownMenu.Root>
									<DropdownMenu.Trigger
										title="More"
										class={cn(buttonVariants({ variant: 'ghost', size: 'icon-sm' }), 'opacity-0 group-hover:opacity-100 text-gray-400 hover:text-gray-600')}
									>
										<Icon name="more-horizontal" size={16} />
									</DropdownMenu.Trigger>
									<DropdownMenu.Content align="end">
										<DropdownMenu.Item onSelect={() => openTask(task.id)}>
											<span class="inline-flex items-center gap-2"><Icon name="pencil" size={14} /> Edit</span>
										</DropdownMenu.Item>
										{#if canDeleteTask(task, $user?.id ?? '', myRole)}
											<DropdownMenu.Item class="text-red-600" onSelect={() => removeTask(task.id)}>
												<span class="inline-flex items-center gap-2"><Icon name="trash" size={14} /> Delete</span>
											</DropdownMenu.Item>
										{/if}
									</DropdownMenu.Content>
								</DropdownMenu.Root>
							</div>
						{/each}

						<!-- Add task -->
						<div class="border-t border-gray-100 dark:border-gray-900 px-3 py-2" style="padding-left: calc(0.75rem + 26px);">
							{#if adding === status}
								<!-- svelte-ignore a11y_autofocus -->
								<input
									class="text-sm px-2 py-1 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent w-64"
									placeholder="Task title…"
									bind:value={newTitle}
									onkeydown={(e) => { if (e.key === 'Enter') submitAdd(status); if (e.key === 'Escape') { adding = null; newTitle = ''; } }}
									autofocus
								/>
							{:else}
								<button class="inline-flex items-center gap-1.5 text-sm text-primary font-medium hover:opacity-80" onclick={() => { adding = status; newTitle = ''; }}>
									<Icon name="plus" size={15} /> Add task
								</button>
							{/if}
						</div>
					{/if}
				</section>
			{/if}
		{/each}
	</div>
</div>
```

- [ ] **Step 2: Verify it type-checks and compiles**

Run: `npm run check`
Expected: no new errors referencing `ListView.svelte` or its imports.

- [ ] **Step 3: Commit**

```bash
git add src/lib/components/workos/views/ListView.svelte
git commit -m "feat(workos): inline-editable grouped List view"
```

---

### Task 7: Full verification

Confirm the whole suite + type check are green and record the manual smoke checklist.

**Files:** none (verification only).

- [ ] **Step 1: Run the full frontend test suite**

Run: `npm run test:frontend`
Expected: PASS (includes the new `columns.test.ts` and `colors.test.ts`; existing `progress.test.ts` still green).

- [ ] **Step 2: Run the type/Svelte check**

Run: `npm run check`
Expected: no new errors introduced by this work.

- [ ] **Step 3: Record manual browser-smoke checklist (do NOT auto-start Vite)**

The user runs their own hot-reload dev server. Hand off this checklist for manual smoke:
- Switch to the **List** tab → tasks appear in collapsible status-grouped cards; only non-empty statuses show; no `canceled` group.
- **Columns** dropdown toggles Assignee/Due date/Priority/Labels/Progress; the header row and rows reflow; reload the page → the choice persists.
- Inline edits save: click the **status circle** → pick a status; **Assign** → pick assignees; **Add date** → set a due date; **Priority** flag → set/clear priority.
- **+ Add task** in a group creates a task already in that status.
- Row **…** menu: Edit opens the drawer; Delete is shown only when permitted and removes the row.
- Clicking the **task name** opens the detail drawer.
- Verify **dark mode** looks correct.

- [ ] **Step 4: Final commit (if any docs/checklist notes were added)**

No code changes expected here. If the manual smoke surfaces a bug, fix it under a new focused commit referencing the affected file.

---

## Notes for the implementer

- Svelte version: this repo uses the modern event syntax (`onclick={...}`, `onkeydown={...}`) and `export let` props — match the surrounding files exactly (see `TaskCard.svelte`, `AssigneeField.svelte`).
- The `gridTemplate` string is applied identically to the column-header row and each task row, so their cells always align. When you add/remove a conditional `{#if $listColumns.x}` cell, the matching width is already added/removed by `gridTemplate` because both iterate `LIST_COLUMNS` in the same order — keep the markup's column order (assignee, due, priority, labels, progress) in sync with `LIST_COLUMNS`.
- Only the task **name** opens the drawer; every other interactive cell is its own control, so no row-level click handler or `stopPropagation` plumbing is needed.
- `editTask`, `addTask`, `removeTask` are optimistic and already wired to realtime — no extra refresh logic.
