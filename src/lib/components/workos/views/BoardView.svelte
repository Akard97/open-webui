<script lang="ts">
	import Sortable from 'sortablejs';
	import { onDestroy, tick } from 'svelte';
	import Icon from '../ui/Icon.svelte';
	import Pills from '../ui/Pills.svelte';
	import { STATUS_ORDER, STATUS_LABEL, type TaskStatus } from '../lib/types';
	import { tasksByStatus, currentWorkstream, labels, openTask, moveTask, addTask } from '../lib/store';

	let columnEls: Record<string, HTMLElement> = {};
	let sortables: Sortable[] = [];
	let adding: TaskStatus | null = null;
	let newTitle = '';

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
</script>

<div class="h-full overflow-x-auto flex gap-4 p-4 box-border">
	{#each STATUS_ORDER as status (status)}
		<div class="w-72 flex-none flex flex-col h-full">
			<div class="flex items-center gap-2 px-1 pb-2">
				<Pills {status} />
				<span class="text-sm font-semibold">{STATUS_LABEL[status]}</span>
				<span class="text-xs text-gray-400">{(byStatus[status] ?? []).length}</span>
				<div class="flex-1"></div>
				<button class="text-gray-400 hover:text-gray-600" onclick={() => (adding = status)}><Icon name="plus" size={15} /></button>
			</div>

			<div bind:this={columnEls[status]} data-status={status} class="flex flex-col gap-2 overflow-y-auto flex-1 pb-4 min-h-[8px]">
				{#each byStatus[status] ?? [] as task (task.id)}
					<div
						data-task-id={task.id}
						data-sort-key={task.sort_key}
						class="bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 rounded-lg p-2.5 cursor-pointer hover:shadow-sm"
						onclick={() => openTask(task.id)}
						role="button"
						tabindex="0"
					>
						<div class="flex items-center justify-between mb-1.5">
							<span class="text-[11px] text-gray-400 font-mono">{task.key}</span>
							<Pills priority={task.priority} />
						</div>
						<div class="text-sm font-medium mb-2 leading-snug">{task.title}</div>
						{#if task.labels.length}
							<div class="flex flex-wrap gap-1 mb-2">
								{#each task.labels as lid (lid)}
									{#if labelById[lid]}<Pills label={labelById[lid]} />{/if}
								{/each}
							</div>
						{/if}
						<div class="flex items-center gap-3 text-[11px] text-gray-400">
							{#if task.due_date}
								<span class="inline-flex items-center gap-1"><Icon name="calendar" size={12} />{new Date(task.due_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
							{/if}
							{#if task.progress > 0}<span>{task.progress}%</span>{/if}
						</div>
					</div>
				{/each}
			</div>

			{#if adding === status}
				<input
					class="mt-2 text-sm px-2 py-1.5 rounded border border-gray-300 dark:border-gray-700 bg-transparent"
					placeholder="Task title…"
					bind:value={newTitle}
					onkeydown={(e) => { if (e.key === 'Enter') submitAdd(status); if (e.key === 'Escape') { adding = null; newTitle = ''; } }}
					autofocus
				/>
			{/if}
		</div>
	{/each}
</div>
