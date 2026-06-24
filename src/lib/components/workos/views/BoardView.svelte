<script lang="ts">
	import Sortable from 'sortablejs';
	import { onDestroy, tick } from 'svelte';
	import Icon from '../ui/Icon.svelte';
	import StatusDot from '../ui/StatusDot.svelte';
	import TaskCard from './TaskCard.svelte';
	import { STATUS_ORDER, STATUS_LABEL, type TaskStatus } from '../lib/types';
	import { tasksByStatus, currentWorkstream, labels, moveTask, addTask } from '../lib/store';

	// Status accent + glyph — hollow ring (not started) → half pie (working) →
	// filled check/x (resolved), echoing the board mock.
	const STATUS_META: Record<TaskStatus, { color: string; shape: 'dashed' | 'ring' | 'half' | 'check' | 'x' }> = {
		backlog: { color: '#9ca3af', shape: 'dashed' },
		todo: { color: '#6b7280', shape: 'ring' },
		in_progress: { color: '#2563eb', shape: 'half' },
		in_review: { color: '#7c3aed', shape: 'half' },
		done: { color: '#16a34a', shape: 'check' },
		canceled: { color: '#9ca3af', shape: 'x' }
	};

	const FILTERS = [
		{ k: 'Due Date', v: 'All' },
		{ k: 'Assignee', v: 'All' },
		{ k: 'Priority', v: 'All' }
	];

	let columnEls: Record<string, HTMLElement> = {};
	let sortables: Sortable[] = [];
	// Per-column render epoch. Bumping a column's epoch makes Svelte tear down and
	// rebuild that column's cards from the store, discarding any DOM that SortableJS
	// mutated directly (see handleEnd).
	let columnEpoch: Record<string, number> = {};
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
					// Only cards are draggable — the empty-column placeholder is ignored,
					// so it never becomes a drag source and never skews newIndex.
					draggable: '[data-task-id]',
					onEnd: handleEnd
				})
			);
		}
	}

	function rerenderColumns(...statuses: (TaskStatus | null)[]) {
		const next = { ...columnEpoch };
		for (const status of new Set(statuses)) if (status) next[status] = (next[status] ?? 0) + 1;
		columnEpoch = next;
	}

	async function handleEnd(evt: Sortable.SortableEvent) {
		const taskId = evt.item.getAttribute('data-task-id');
		const toStatus = (evt.to as HTMLElement).getAttribute('data-status') as TaskStatus | null;
		const fromStatus = (evt.from as HTMLElement).getAttribute('data-status') as TaskStatus | null;
		if (!taskId || !toStatus) return;
		const newIndex = evt.newIndex ?? 0;

		// Target column from the store, excluding the moved task; insert at newIndex.
		const col = (byStatus[toStatus] ?? []).filter((t) => t.id !== taskId);
		const before = newIndex > 0 ? col[newIndex - 1] : null;
		const after = col[newIndex] ?? null;

		// SortableJS has already moved the dragged node in the DOM. Delete that node outright:
		// on an end-of-column or empty-column drop SortableJS appends it past the {#each} anchor
		// (outside the range the rebuild tears down), so leaving it in place strands it as a
		// duplicate. Removing it is position-independent — the column rebuild below recreates
		// every card from the store, and Svelte's later teardown of this item is a safe no-op
		// on the now-detached node.
		evt.item.remove();

		// Apply the optimistic move, then force the affected columns to rebuild from the store
		// (the single source of truth). moveTask's optimistic write is synchronous, so bumping
		// the epoch in the same tick rebuilds cleanly instead of leaning on Svelte 5's incremental
		// keyed-{#each} reconcile, which strands a stale card in the source column when siblings remain.
		const move = moveTask(taskId, toStatus, before ? before.sort_key : null, after ? after.sort_key : null);
		rerenderColumns(fromStatus, toStatus);
		await move;
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
				tabindex="-1"
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
			tabindex="-1"
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

	<!-- Columns: white board, each column a flexible-height tinted panel -->
	<div class="flex-1 overflow-auto flex gap-4 p-4 box-border items-start bg-white dark:bg-gray-950">
		{#each STATUS_ORDER as status (status)}
			<div class="w-72 flex-none flex flex-col rounded-2xl bg-gray-50/70 dark:bg-gray-900/40 p-2.5">
				<div class="flex items-center gap-2 px-1 pb-2.5">
					<span
						class="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg text-[13px] font-semibold"
						style="background:{STATUS_META[status].color}24; color:{STATUS_META[status].color}"
					>
						<StatusDot shape={STATUS_META[status].shape} color={STATUS_META[status].color} size={15} />
						{STATUS_LABEL[status]}
					</span>
					<div class="flex-1"></div>
					<button class="text-gray-400 hover:text-gray-600" title="More" aria-disabled="true" tabindex="-1"><Icon name="more-horizontal" size={16} /></button>
					<button class="text-gray-400 hover:text-gray-600" onclick={() => (adding = status)} title="Add task"><Icon name="plus" size={16} /></button>
				</div>

				<div bind:this={columnEls[status]} data-status={status} class="flex flex-col gap-2.5 min-h-[24px]">
					{#key columnEpoch[status] ?? 0}
						{#each byStatus[status] ?? [] as task (task.id)}
							<TaskCard {task} {labelById} />
						{/each}
					{/key}

					{#if !(byStatus[status]?.length) && adding !== status}
						<!-- Empty column: a quiet, column-specific hint (no border) -->
						<div class="flex flex-col items-center justify-center gap-2 py-6 text-center select-none">
							<span class="opacity-50">
								<StatusDot shape={STATUS_META[status].shape} color={STATUS_META[status].color} size={22} />
							</span>
							<span class="text-xs text-gray-400 dark:text-gray-500">No tasks in {STATUS_LABEL[status]}</span>
						</div>
					{/if}
				</div>

				{#if adding === status}
					<input
						class="mt-2.5 text-sm px-2 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950"
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
