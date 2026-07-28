# WorkOS Subtask Panel Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the task-detail Subtasks panel to the approved "teal checklist" design: segmented progress header, soft-fill rows with round teal checkboxes, hover-reveal drag/delete, persistent quick-add with Enter chaining, inline rename, and pointer-drag reorder via `sort_key` midpoints.

**Architecture:** All changes are frontend-only, inside `SubtasksPanel.svelte` plus one new pure helper module (`subtaskPanel.ts`) that is unit-tested. The store API is untouched — `addSubtask` / `editSubtask` / `removeSubtask` already cover every mutation (title, completed, sort_key, assignee_ids) with optimistic update + rollback. The panel renders a derived list sorted by `sort_key` ascending, which makes reorder and realtime echoes purely data-driven.

**Tech Stack:** Svelte 5 (runes-free component style used in this repo: `export let`, `$:` reactives, `onclick=` DOM props), Tailwind (workos-scoped shadcn tokens; teal = `primary`), vitest.

**Spec:** `docs/superpowers/specs/2026-07-28-workos-subtask-panel-redesign-design.md`

## Global Constraints

- The grouped assignee dropdown block (`DropdownMenu.Root` … `DropdownMenu.Content` with "On this task" / "Everyone else" / auto-add hint) moves over **verbatim** — zero changes to its markup, logic, or `canExpand` gating.
- No backend, store, or API changes of any kind.
- Teal is the existing `primary` token (`bg-primary`, `text-primary`, `bg-primary/10`) — no new palette entries, no hardcoded hex.
- Badges are rectangles (`rounded`, not `rounded-full`) per the locked design-system rule.
- All mutations stay optimistic; failures surface via the existing `notifyFailed` toast ("Couldn't update — try again"). At most one toast per reorder batch.
- Completed rows stay in place (no sinking/regrouping).
- Indentation: tabs (repo convention). Svelte 5 event syntax (`onclick`, `onkeydown` — never `on:click`).
- NEVER dispatch a haiku-model subagent for Svelte edits (cp1252 corruption history on this machine).
- Commands run from repo root `C:\Projects\open-webui`.

---

### Task 1: Pure helpers — `computeSortKey` + `resolveRename`

**Files:**
- Create: `src/lib/components/workos/lib/subtaskPanel.ts`
- Test: `src/lib/components/workos/lib/subtaskPanel.test.ts`

**Interfaces:**
- Consumes: `Subtask` type from `./types` (only `id: string` and `sort_key: number` fields).
- Produces (Tasks 3 and 4 import these exact names from `../../lib/subtaskPanel`):
  - `SORT_SPACING = 1000`
  - `interface SortKeyUpdate { id: string; sort_key: number }`
  - `computeSortKey(list: Pick<Subtask, 'id' | 'sort_key'>[], fromIndex: number, toIndex: number): SortKeyUpdate[]` — `list` must be sorted by `sort_key` ascending; `toIndex` is the index the moved row should occupy in the **final** list. Returns one midpoint update normally, a full-list renumber plan (`(i+1)*1000`) when the midpoint degenerates, `[]` for no-ops/invalid indices.
  - `resolveRename(current: string, draft: string): { action: 'commit'; title: string } | { action: 'revert' }`

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/workos/lib/subtaskPanel.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { computeSortKey, resolveRename, SORT_SPACING } from './subtaskPanel';

const row = (id: string, sort_key: number) => ({ id, sort_key });

describe('computeSortKey', () => {
	const list = [row('a', 1000), row('b', 2000), row('c', 3000), row('d', 4000)];

	it('returns [] when fromIndex === toIndex', () => {
		expect(computeSortKey(list, 1, 1)).toEqual([]);
	});

	it('returns [] for out-of-range indices', () => {
		expect(computeSortKey(list, -1, 2)).toEqual([]);
		expect(computeSortKey(list, 0, 4)).toEqual([]);
		expect(computeSortKey([], 0, 0)).toEqual([]);
	});

	it('moves between neighbors via midpoint', () => {
		// move d (idx 3) to final idx 1 → between a(1000) and b(2000)
		expect(computeSortKey(list, 3, 1)).toEqual([{ id: 'd', sort_key: 1500 }]);
	});

	it('moves to top via first − SORT_SPACING', () => {
		expect(computeSortKey(list, 2, 0)).toEqual([{ id: 'c', sort_key: 1000 - SORT_SPACING }]);
	});

	it('moves to bottom via last + SORT_SPACING', () => {
		expect(computeSortKey(list, 0, 3)).toEqual([{ id: 'a', sort_key: 4000 + SORT_SPACING }]);
	});

	it('swaps a two-item list', () => {
		const two = [row('a', 1000), row('b', 2000)];
		expect(computeSortKey(two, 0, 1)).toEqual([{ id: 'a', sort_key: 2000 + SORT_SPACING }]);
		expect(computeSortKey(two, 1, 0)).toEqual([{ id: 'b', sort_key: 1000 - SORT_SPACING }]);
	});

	it('adjacent move down lands between the next pair', () => {
		// move a (idx 0) to final idx 1 → between b(2000) and c(3000)
		expect(computeSortKey(list, 0, 1)).toEqual([{ id: 'a', sort_key: 2500 }]);
	});

	it('renumbers the whole list when the midpoint degenerates', () => {
		// b and c share a key → midpoint equals both → not strictly between
		const tight = [row('a', 1000), row('b', 2000), row('c', 2000), row('d', 4000)];
		// move d to final idx 2 → between b(2000) and c(2000) → renumber
		expect(computeSortKey(tight, 3, 2)).toEqual([
			{ id: 'a', sort_key: 1 * SORT_SPACING },
			{ id: 'b', sort_key: 2 * SORT_SPACING },
			{ id: 'd', sort_key: 3 * SORT_SPACING },
			{ id: 'c', sort_key: 4 * SORT_SPACING }
		]);
	});

	it('does not mutate the input list', () => {
		const input = [row('a', 1000), row('b', 2000)];
		computeSortKey(input, 0, 1);
		expect(input).toEqual([row('a', 1000), row('b', 2000)]);
	});
});

describe('resolveRename', () => {
	it('commits a changed, trimmed title', () => {
		expect(resolveRename('Old', '  New title  ')).toEqual({ action: 'commit', title: 'New title' });
	});
	it('reverts when the draft is empty or whitespace-only', () => {
		expect(resolveRename('Old', '')).toEqual({ action: 'revert' });
		expect(resolveRename('Old', '   ')).toEqual({ action: 'revert' });
	});
	it('reverts when the trimmed draft is unchanged', () => {
		expect(resolveRename('Same', ' Same ')).toEqual({ action: 'revert' });
	});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
npm run test:frontend -- --run src/lib/components/workos/lib/subtaskPanel.test.ts
```

Expected: FAIL — cannot resolve `./subtaskPanel`.

- [ ] **Step 3: Write minimal implementation**

Create `src/lib/components/workos/lib/subtaskPanel.ts`:

```ts
import type { Subtask } from './types';

/** Gap between renumbered keys; also the step past either end of the list. */
export const SORT_SPACING = 1000;

export interface SortKeyUpdate {
	id: string;
	sort_key: number;
}

/**
 * Plan the sort_key writes for moving list[fromIndex] to final position toIndex.
 * `list` must already be sorted by sort_key ascending; never mutated.
 * Normal case: a single midpoint update. Degenerate midpoint (float precision /
 * duplicate keys): full-list renumber to (index+1)*SORT_SPACING. No-op or
 * invalid indices: empty array.
 */
export function computeSortKey(
	list: Pick<Subtask, 'id' | 'sort_key'>[],
	fromIndex: number,
	toIndex: number
): SortKeyUpdate[] {
	if (fromIndex === toIndex) return [];
	if (fromIndex < 0 || toIndex < 0 || fromIndex >= list.length || toIndex >= list.length) return [];

	const moved = list[fromIndex];
	const rest = list.filter((_, i) => i !== fromIndex);
	const prev = rest[toIndex - 1];
	const next = rest[toIndex];

	let key: number;
	if (!prev && !next) return [];
	else if (!prev) key = next.sort_key - SORT_SPACING;
	else if (!next) key = prev.sort_key + SORT_SPACING;
	else key = (prev.sort_key + next.sort_key) / 2;

	const collides = (prev && !(key > prev.sort_key)) || (next && !(key < next.sort_key));
	if (!collides) return [{ id: moved.id, sort_key: key }];

	const finalOrder = [...rest.slice(0, toIndex), moved, ...rest.slice(toIndex)];
	return finalOrder.map((s, i) => ({ id: s.id, sort_key: (i + 1) * SORT_SPACING }));
}

export type RenameResolution = { action: 'commit'; title: string } | { action: 'revert' };

/** Decide what an inline-rename blur/Enter should do. */
export function resolveRename(current: string, draft: string): RenameResolution {
	const title = draft.trim();
	if (!title || title === current) return { action: 'revert' };
	return { action: 'commit', title };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
npm run test:frontend -- --run src/lib/components/workos/lib/subtaskPanel.test.ts
```

Expected: PASS — 12 tests.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/lib/subtaskPanel.ts src/lib/components/workos/lib/subtaskPanel.test.ts
git commit -m "feat(workos): subtask reorder/rename pure helpers"
```

---

### Task 2: Panel visual rebuild (header, rows, quick-add, empty state)

**Files:**
- Modify: `src/lib/components/workos/views/detail/SubtasksPanel.svelte` (full rewrite, 155 lines today)

**Interfaces:**
- Consumes: store functions `subtasks`, `addSubtask`, `editSubtask`, `removeSubtask`, `directory`, `roles` from `../../lib/store` (unchanged signatures); `toggleAssignee` from `../../lib/assignees`; `canEditTask` from `../../lib/roles`; `AssigneeAvatars` component; `Icon` component (names used: `check`, `plus`, `trash`, `user-plus`, `list-checks`).
- Produces: the component structure Tasks 3 and 4 edit — row markup with `class="group …"`, title `<span>` (replaced in Task 3), `sorted` derived list, `notifyFailed`, scoped `<style>` block (extended in Task 4).

This task is visual; correctness is guarded by `svelte-check` + the untouched
unit suite, and behavior is verified in the final browser smoke. No new unit
tests here (no new logic — helpers were tested in Task 1).

- [ ] **Step 1: Replace the component**

Replace the entire contents of `src/lib/components/workos/views/detail/SubtasksPanel.svelte` with:

```svelte
<script lang="ts">
	import { toast } from 'svelte-sonner';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import Icon from '../../ui/Icon.svelte';
	import { Button } from '$lib/components/ui/button';
	import AssigneeAvatars from '../AssigneeAvatars.svelte';
	import { subtasks, addSubtask, editSubtask, removeSubtask, directory, roles } from '../../lib/store';
	import { toggleAssignee } from '../../lib/assignees';
	import { canEditTask } from '../../lib/roles';
	import { user } from '$lib/stores';
	import type { Task, Subtask } from '../../lib/types';

	export let task: Task;

	let title = '';

	// Panel-local sorted view: the store appends realtime/created rows at the end;
	// sorting here keeps display order canonical and makes sort_key edits
	// (reorder, concurrent editors) re-flow automatically.
	$: sorted = [...$subtasks].sort((a, b) => a.sort_key - b.sort_key);
	$: doneCount = sorted.filter((s) => s.completed).length;

	$: parentIds = task.assignee_ids ?? [];
	$: members = Object.entries($directory).map(([id, u]) => ({ id, name: u.name }));
	$: onTask = members.filter((m) => parentIds.includes(m.id));
	$: everyoneElse = members.filter((m) => !parentIds.includes(m.id));
	// Whether the viewer may expand the parent's assignee list (mirrors the
	// server's task.write gate on auto-add; workspace-admin edge under-shown,
	// server remains authoritative).
	$: canExpand =
		$user?.role === 'admin' || canEditTask(task, $user?.id ?? '', $roles[task.team_id], undefined);

	// Store calls roll back optimistically on failure — surface it, InboxView-style.
	const notifyFailed = () => toast.error("Couldn't update — try again");

	async function submit() {
		const value = title.trim();
		if (!value) return;
		title = '';
		try {
			await addSubtask(task.id, value);
		} catch {
			notifyFailed();
			if (!title) title = value; // restore the draft so a failed create isn't lost
		}
	}

	function toggle(subtask: Subtask, id: string) {
		void editSubtask(subtask.id, { assignee_ids: toggleAssignee(subtask.assignee_ids, id) }).catch(
			notifyFailed
		);
	}
</script>

<div class="pt-4 space-y-3">
	{#if sorted.length}
		<div class="flex items-center gap-3">
			{#if sorted.length <= 24}
				<div class="flex flex-1 gap-[3px]">
					{#each sorted as s, i (s.id)}
						<div
							class="h-1.5 flex-1 rounded-[3px] transition-colors duration-300 {i < doneCount
								? 'bg-primary'
								: 'bg-gray-200 dark:bg-gray-800'}"
						></div>
					{/each}
				</div>
			{:else}
				<div class="h-1.5 flex-1 overflow-hidden rounded-[3px] bg-gray-200 dark:bg-gray-800">
					<div
						class="h-full rounded-[3px] bg-primary transition-[width] duration-300"
						style="width:{(doneCount / sorted.length) * 100}%"
					></div>
				</div>
			{/if}
			<span class="wos-micro rounded bg-primary/10 px-2 py-0.5 text-primary">
				{doneCount}/{sorted.length} done
			</span>
		</div>
	{/if}

	<div class="space-y-[5px]">
		{#each sorted as subtask (subtask.id)}
			<div
				class="group flex items-center gap-2.5 rounded-[10px] bg-gray-50 px-3 py-2.5 transition-colors hover:bg-gray-100 dark:bg-gray-900/50 dark:hover:bg-gray-800/60"
			>
				<button
					type="button"
					role="checkbox"
					aria-checked={subtask.completed}
					aria-label="Toggle subtask completion"
					class="flex size-[18px] shrink-0 items-center justify-center rounded-full border-2 transition-colors {subtask.completed
						? 'border-primary bg-primary text-primary-foreground'
						: 'border-gray-300 hover:border-gray-400 dark:border-gray-600 dark:hover:border-gray-500'}"
					onclick={() =>
						void editSubtask(subtask.id, { completed: !subtask.completed }).catch(notifyFailed)}
				>
					{#if subtask.completed}
						<span class="wos-subcheck-pop"><Icon name="check" size={11} /></span>
					{/if}
				</button>
				<span
					class="min-w-0 flex-1 truncate text-sm {subtask.completed
						? 'text-gray-400 line-through'
						: 'text-gray-900 dark:text-gray-100'}"
				>
					{subtask.title}
				</span>
				<DropdownMenu.Root>
					<DropdownMenu.Trigger
						class="inline-flex items-center rounded-md p-0.5 hover:bg-gray-100 dark:hover:bg-gray-900"
						aria-label="Edit subtask assignees"
					>
						{#if (subtask.assignee_ids ?? []).length}
							<AssigneeAvatars ids={subtask.assignee_ids} size={20} max={3} />
						{:else}
							<span
								class="flex size-6 items-center justify-center rounded-full border-[1.5px] border-dashed border-gray-300 text-gray-400 dark:border-gray-700 dark:text-gray-500"
							>
								<Icon name="user-plus" size={13} />
							</span>
						{/if}
					</DropdownMenu.Trigger>
					<DropdownMenu.Content class="w-72 max-h-72 overflow-y-auto">
						<DropdownMenu.Label class="wos-caption text-gray-400">On this task</DropdownMenu.Label>
						{#each onTask as m (m.id)}
							<DropdownMenu.CheckboxItem
								checked={(subtask.assignee_ids ?? []).includes(m.id)}
								closeOnSelect={false}
								onCheckedChange={() => toggle(subtask, m.id)}
							>
								<span class="inline-flex items-center gap-2">
									<AssigneeAvatars ids={[m.id]} max={1} size={20} />
									{m.name}
								</span>
							</DropdownMenu.CheckboxItem>
						{/each}
						{#if !onTask.length}
							<DropdownMenu.Item disabled>No assignees on this task</DropdownMenu.Item>
						{/if}
						{#if canExpand && everyoneElse.length}
							<DropdownMenu.Separator />
							<DropdownMenu.Label class="wos-caption text-gray-400">Everyone else</DropdownMenu.Label>
							{#each everyoneElse as m (m.id)}
								<DropdownMenu.CheckboxItem
									checked={(subtask.assignee_ids ?? []).includes(m.id)}
									closeOnSelect={false}
									onCheckedChange={() => toggle(subtask, m.id)}
								>
									<span class="inline-flex min-w-0 flex-1 items-center gap-2">
										<AssigneeAvatars ids={[m.id]} max={1} size={20} />
										<span class="truncate">{m.name}</span>
										{#if (subtask.assignee_ids ?? []).includes(m.id)}
											<span
												class="wos-micro ml-auto rounded-full bg-amber-100 px-2 py-px text-amber-700 dark:bg-amber-950 dark:text-amber-400"
											>+ added to task</span>
										{/if}
									</span>
								</DropdownMenu.CheckboxItem>
							{/each}
							<DropdownMenu.Separator />
							<div class="flex items-center gap-1.5 px-2 py-1.5 text-[11px] text-gray-400 dark:text-gray-500">
								<Icon name="user-plus" size={12} /> Picking someone new also adds them to the task
							</div>
						{/if}
					</DropdownMenu.Content>
				</DropdownMenu.Root>
				<span
					class="wos-reveal opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100"
				>
					<Button
						variant="ghost"
						size="icon-xs"
						class="text-gray-400 hover:text-red-500"
						title="Delete subtask"
						onclick={() => void removeSubtask(subtask.id).catch(notifyFailed)}
					>
						<Icon name="trash" size={14} />
					</Button>
				</span>
			</div>
		{/each}
	</div>

	{#if !sorted.length}
		<div class="flex flex-col items-center gap-1.5 py-8 text-center">
			<span class="flex size-9 items-center justify-center rounded-full bg-primary/10 text-primary">
				<Icon name="list-checks" size={18} />
			</span>
			<div class="text-sm font-medium text-gray-700 dark:text-gray-300">
				Break this task into smaller steps.
			</div>
			<div class="text-xs text-gray-400 dark:text-gray-500">Type below — Enter adds the next one.</div>
		</div>
	{/if}

	<div
		class="flex items-center gap-2 rounded-[10px] border-[1.5px] border-gray-200 bg-white px-3 py-2.5 transition-colors focus-within:border-primary dark:border-gray-800 dark:bg-gray-950"
	>
		<span class="text-primary"><Icon name="plus" size={15} /></span>
		<input
			class="min-w-0 flex-1 bg-transparent text-sm outline-none placeholder:text-gray-400"
			placeholder="Add a subtask — Enter adds another"
			aria-label="Add a subtask"
			bind:value={title}
			onkeydown={(e) => {
				if (e.key === 'Enter') void submit();
				if (e.key === 'Escape') {
					title = '';
					e.currentTarget.blur();
				}
			}}
		/>
	</div>
</div>

<style>
	.wos-subcheck-pop {
		display: flex;
		animation: wos-subcheck-pop 0.18s ease-out;
	}
	@keyframes wos-subcheck-pop {
		0% {
			transform: scale(0.4);
			opacity: 0;
		}
		70% {
			transform: scale(1.15);
		}
		100% {
			transform: scale(1);
			opacity: 1;
		}
	}
	/* Touch devices have no hover — keep controls visible. */
	@media (hover: none) {
		.wos-reveal {
			opacity: 1 !important;
		}
	}
</style>
```

Notes for the implementer:
- The `DropdownMenu.Root` … `/DropdownMenu.Root` block is byte-identical to the current file (lines 63–121) — copy it, don't retype it.
- `Checkbox` import and the `creating` toggle state are gone deliberately.
- The `wos-reveal` class sits on a plain `<span>` wrapper (not on the `Button` component) because Svelte scoped CSS only reaches elements in this component's own template.

- [ ] **Step 2: Type-check**

Run:

```bash
npm run check
```

Expected: 0 errors (warnings unchanged from baseline).

- [ ] **Step 3: Full frontend unit suite still green**

Run:

```bash
npm run test:frontend -- --run
```

Expected: PASS, no regressions.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/detail/SubtasksPanel.svelte
git commit -m "feat(workos): subtask panel teal-checklist restyle

Segmented progress header with done-count badge, soft-fill rows with
round teal pop-animation checkboxes, hover-reveal delete, persistent
quick-add with Enter chaining, richer empty state. Assignee dropdown
unchanged. Panel now renders a sort_key-sorted derived list."
```

---

### Task 3: Inline rename

**Files:**
- Modify: `src/lib/components/workos/views/detail/SubtasksPanel.svelte`

**Interfaces:**
- Consumes: `resolveRename` from `../../lib/subtaskPanel` (Task 1); the title `<span>` markup from Task 2.
- Produces: rename state (`renamingId`, `draft`) and handlers (`startRename`, `commitRename`, `cancelRename`) — Task 4 does not touch these.

- [ ] **Step 1: Add rename state and handlers to the script block**

Add to the imports in `SubtasksPanel.svelte`:

```ts
	import { resolveRename } from '../../lib/subtaskPanel';
```

Add below `let title = '';`:

```ts
	let renamingId: string | null = null;
	let draft = '';

	function startRename(subtask: Subtask) {
		renamingId = subtask.id;
		draft = subtask.title;
	}

	// Null renamingId BEFORE acting so the input's blur (fired by unmount)
	// can't double-commit.
	function commitRename(subtask: Subtask) {
		if (renamingId !== subtask.id) return;
		renamingId = null;
		const res = resolveRename(subtask.title, draft);
		if (res.action === 'commit')
			void editSubtask(subtask.id, { title: res.title }).catch(notifyFailed);
	}

	function cancelRename() {
		renamingId = null;
	}
```

- [ ] **Step 2: Swap the title span for a rename-aware block**

In the row markup, replace this Task-2 block:

```svelte
				<span
					class="min-w-0 flex-1 truncate text-sm {subtask.completed
						? 'text-gray-400 line-through'
						: 'text-gray-900 dark:text-gray-100'}"
				>
					{subtask.title}
				</span>
```

with:

```svelte
				{#if renamingId === subtask.id}
					<!-- svelte-ignore a11y_autofocus -->
					<input
						class="min-w-0 flex-1 bg-transparent text-sm outline-none"
						aria-label="Rename subtask"
						bind:value={draft}
						autofocus
						onkeydown={(e) => {
							if (e.key === 'Enter') commitRename(subtask);
							if (e.key === 'Escape') cancelRename();
						}}
						onblur={() => commitRename(subtask)}
					/>
				{:else}
					<button
						type="button"
						class="min-w-0 flex-1 truncate text-left text-sm {subtask.completed
							? 'text-gray-400 line-through'
							: 'text-gray-900 dark:text-gray-100'}"
						title="Click to rename"
						onclick={() => startRename(subtask)}
					>
						{subtask.title}
					</button>
				{/if}
```

- [ ] **Step 3: Type-check**

Run:

```bash
npm run check
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
git add src/lib/components/workos/views/detail/SubtasksPanel.svelte
git commit -m "feat(workos): inline subtask rename

Click the title to edit in place. Enter/blur commits via resolveRename
(trimmed; empty or unchanged reverts), Esc reverts. Optimistic with
rollback toast."
```

---

### Task 4: Drag reorder + keyboard move

**Files:**
- Modify: `src/lib/components/workos/views/detail/SubtasksPanel.svelte`

**Interfaces:**
- Consumes: `computeSortKey`, `SortKeyUpdate` from `../../lib/subtaskPanel` (Task 1); row markup and scoped `<style>` from Task 2.
- Produces: nothing consumed later — final task.

- [ ] **Step 1: Add drag state and handlers to the script block**

Change the Task-3 import line to also pull the reorder helpers:

```ts
	import { computeSortKey, resolveRename, type SortKeyUpdate } from '../../lib/subtaskPanel';
```

Add below the rename handlers:

```ts
	let dragIndex: number | null = null;
	let dropIndex: number | null = null; // gap index 0..n in the sorted list
	let rowEls: HTMLElement[] = [];

	function dragStart(i: number, e: PointerEvent) {
		if (e.button !== 0) return;
		dragIndex = i;
		dropIndex = null;
		(e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
	}

	function dragMove(e: PointerEvent) {
		if (dragIndex === null) return;
		let gap = rowEls.length;
		for (let i = 0; i < rowEls.length; i++) {
			const el = rowEls[i];
			if (!el) continue;
			const r = el.getBoundingClientRect();
			if (e.clientY < r.top + r.height / 2) {
				gap = i;
				break;
			}
		}
		dropIndex = gap;
	}

	function dragEnd() {
		if (dragIndex === null) return;
		const from = dragIndex;
		const gap = dropIndex;
		dragIndex = null;
		dropIndex = null;
		if (gap === null) return;
		// gap is an insertion point in the list INCLUDING the dragged row;
		// removing that row first shifts positions after it down by one.
		const to = gap > from ? gap - 1 : gap;
		void applyReorder(computeSortKey(sorted, from, to));
	}

	async function applyReorder(updates: SortKeyUpdate[]) {
		if (!updates.length) return;
		const results = await Promise.allSettled(
			updates.map((u) => editSubtask(u.id, { sort_key: u.sort_key }))
		);
		// One toast per batch even if several row PATCHes fail (renumber case).
		if (results.some((r) => r.status === 'rejected')) notifyFailed();
	}

	function moveByKeyboard(i: number, e: KeyboardEvent) {
		if (e.key !== 'ArrowUp' && e.key !== 'ArrowDown') return;
		e.preventDefault();
		const to = e.key === 'ArrowUp' ? i - 1 : i + 1;
		if (to < 0 || to >= sorted.length) return;
		void applyReorder(computeSortKey(sorted, i, to));
	}
```

- [ ] **Step 2: Wire the row markup**

Replace the Task-2 `{#each}` opening and row `<div>`:

```svelte
		{#each sorted as subtask (subtask.id)}
			<div
				class="group flex items-center gap-2.5 rounded-[10px] bg-gray-50 px-3 py-2.5 transition-colors hover:bg-gray-100 dark:bg-gray-900/50 dark:hover:bg-gray-800/60"
			>
```

with (index added, `bind:this`, drop line above each row, drag dimming):

```svelte
		{#each sorted as subtask, i (subtask.id)}
			{#if dragIndex !== null && dropIndex === i}
				<div class="h-0.5 rounded bg-primary"></div>
			{/if}
			<div
				bind:this={rowEls[i]}
				class="group flex items-center gap-2.5 rounded-[10px] bg-gray-50 px-3 py-2.5 transition-colors hover:bg-gray-100 dark:bg-gray-900/50 dark:hover:bg-gray-800/60 {dragIndex ===
				i
					? 'opacity-50'
					: ''}"
			>
```

Insert the drag handle as the FIRST child of the row div, before the checkbox button:

```svelte
				<button
					type="button"
					class="wos-drag wos-reveal -ml-1 shrink-0 cursor-grab touch-none text-gray-300 opacity-0 transition-opacity hover:text-gray-500 focus-visible:opacity-100 group-hover:opacity-100 active:cursor-grabbing dark:text-gray-600 dark:hover:text-gray-400"
					aria-label="Reorder subtask (Arrow keys to move)"
					onpointerdown={(e) => dragStart(i, e)}
					onpointermove={dragMove}
					onpointerup={dragEnd}
					onpointercancel={dragEnd}
					onkeydown={(e) => moveByKeyboard(i, e)}
				>
					<Icon name="grip-vertical" size={14} />
				</button>
```

Immediately after the `{/each}` closing tag, add the end-of-list drop line:

```svelte
		{#if dragIndex !== null && dropIndex === sorted.length}
			<div class="h-0.5 rounded bg-primary"></div>
		{/if}
```

- [ ] **Step 3: Hide the handle on touch devices**

In the scoped `<style>` block, extend the existing media query section:

```css
	/* Touch devices have no hover — keep controls visible, and reorder is
	   desktop-only (spec): hide the drag handle entirely. */
	@media (hover: none) {
		.wos-reveal {
			opacity: 1 !important;
		}
		.wos-drag {
			display: none;
		}
	}
```

(Replace the Task-2 `@media (hover: none)` block with this one.)

- [ ] **Step 4: Type-check and full suite**

Run:

```bash
npm run check
```

Expected: 0 errors.

Run:

```bash
npm run test:frontend -- --run
```

Expected: PASS, no regressions.

- [ ] **Step 5: Commit**

```bash
git add src/lib/components/workos/views/detail/SubtasksPanel.svelte
git commit -m "feat(workos): drag-reorder subtasks

Pointer-capture drag on a hover-reveal grip handle with a teal drop
indicator; drop persists sort_key midpoints via computeSortKey
(full renumber on degenerate midpoints, one toast per failed batch).
ArrowUp/Down on the focused handle moves one position. Handle hidden
on touch devices — reorder is desktop-only."
```

---

### Browser smoke checklist (post-build, needs running app + login)

Not a plan task — run after Task 4 as the usual manual smoke:

1. Open a task with subtasks → segmented bar + `n/m done` badge render; segments teal-fill left→right as boxes get checked; checkbox pops on check.
2. Completed row: strikethrough, stays in place.
3. Hover a row → grip + trash fade in; assignee dropdown unchanged (both groups, auto-add hint).
4. Quick-add: type + Enter three times rapidly → three rows appear, focus never leaves the input; Esc clears.
5. Click a title → inline input; Enter commits rename; Esc reverts; empty draft reverts.
6. Drag a row by the grip to top, bottom, and middle → teal drop line tracks, order persists after reload.
7. Handle focused + ArrowUp/ArrowDown moves the row.
8. Empty state on a fresh task shows icon + copy; adding first subtask swaps to list + header.
9. Dark mode pass on all of the above.
10. Mobile width (or touch emulation): no grip handle, trash always visible, rows/quick-add usable.
