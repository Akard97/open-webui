<script lang="ts">
	import Sortable from 'sortablejs';
	import { onDestroy, tick } from 'svelte';
	import Icon from '../ui/Icon.svelte';
	import { Button } from '$lib/components/ui/button';
	import StatusDot from '../ui/StatusDot.svelte';
	import StatusBadge from '../ui/StatusBadge.svelte';
	import TaskCard from './TaskCard.svelte';
	import { STATUS_ORDER, STATUS_LABEL, type TaskStatus } from '../lib/types';
	import { tasksByStatus, currentWorkstream, labels, moveTask, openTaskCreate, boardFilter } from '../lib/store';
	import { STATUS_COLOR, STATUS_SHAPE } from '../lib/colors';
	import FilterBar from '../chrome/FilterBar.svelte';

	let columnEls: Record<string, HTMLElement> = {};
	let sortables: Sortable[] = [];
	// Per-column render epoch. Bumping a column's epoch makes Svelte tear down and
	// rebuild that column's cards from the store, discarding any DOM that SortableJS
	// mutated directly (see handleEnd).
	let columnEpoch: Record<string, number> = {};

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
</script>

<div class="h-full flex flex-col min-h-0">
	<!-- Filter bar + Add New -->
	<div class="flex-none flex flex-col md:flex-row md:items-stretch">
		<div class="flex-1"><FilterBar filter={boardFilter} /></div>
		<div class="flex items-center px-4 py-2 md:py-0 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
			<Button size="sm" onclick={() => { const ws = $currentWorkstream; if (ws) openTaskCreate(ws.id); }}>
				<Icon name="plus" size={15} /> Add New
			</Button>
		</div>
	</div>

	<!-- Columns: white board, each column a flexible-height tinted panel -->
	<div class="flex-1 overflow-auto flex gap-4 p-4 box-border items-start bg-white dark:bg-gray-950 max-md:snap-x max-md:snap-mandatory max-md:gap-3 max-md:p-3">
		{#each STATUS_ORDER as status (status)}
			<div class="w-72 max-md:w-[82vw] max-md:snap-center flex-none flex flex-col rounded-lg bg-gray-50/70 dark:bg-gray-900/40 p-2.5">
				<div class="flex items-center gap-2 px-1 pb-2.5">
					<StatusBadge {status} size="md" />
					<div class="flex-1"></div>
					<button class="text-gray-400 opacity-50 cursor-default" title="More" aria-disabled="true" tabindex="-1"><Icon name="more-horizontal" size={16} /></button>
					<Button variant="ghost" size="icon-xs" class="text-gray-400 hover:text-gray-600"
						onclick={() => { const ws = $currentWorkstream; if (ws) openTaskCreate(ws.id, { status }); }}
						title="Add task"><Icon name="plus" size={16} /></Button>
				</div>

				<div bind:this={columnEls[status]} data-status={status} class="flex flex-col gap-2.5 min-h-[24px]">
					{#key columnEpoch[status] ?? 0}
						{#each byStatus[status] ?? [] as task (task.id)}
							<TaskCard {task} {labelById} />
						{/each}
					{/key}

					{#if !(byStatus[status]?.length)}
						<!-- Empty column: a quiet, column-specific hint (no border) -->
						<div class="flex flex-col items-center justify-center gap-2 py-6 text-center select-none">
							<span class="opacity-50">
								<StatusDot shape={STATUS_SHAPE[status]} color={STATUS_COLOR[status]} size={22} />
							</span>
							<span class="text-xs text-gray-400 dark:text-gray-500">No tasks in {STATUS_LABEL[status]}</span>
						</div>
					{/if}
				</div>
			</div>
		{/each}
	</div>
</div>
