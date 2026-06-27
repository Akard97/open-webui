<script lang="ts">
	import { STATUS_LABEL, type Task } from '../../lib/types';
	import { STATUS_COLOR } from '../../lib/colors';
	import { openTask, displayName, initials } from '../../lib/store';
	export let task: Task;
	const fmt = (ms: number | null | undefined) => (ms == null ? '' : new Date(ms).toLocaleDateString());
	// Overdue = due before today's start and still open — drives the date accent.
	$: overdue =
		task.due_date != null &&
		task.due_date < new Date().setHours(0, 0, 0, 0) &&
		task.status !== 'done' &&
		task.status !== 'canceled';
	$: statusColor = STATUS_COLOR[task.status];
</script>

<button
	type="button"
	class="flex items-center gap-3 px-3 py-2.5 text-left w-full rounded-lg hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors"
	onclick={() => openTask(task.id)}
>
	<span class="text-[11px] font-medium text-gray-400 w-14 flex-none tabular-nums">{task.key}</span>
	<span class="flex-1 truncate text-sm">{task.title}</span>
	<span class="inline-flex items-center gap-1.5 text-[11px] text-gray-500 dark:text-gray-400 whitespace-nowrap">
		<span class="w-2 h-2 rounded-full flex-none" style="background:{statusColor}"></span>{STATUS_LABEL[task.status]}
	</span>
	{#if task.due_date}
		<span class="text-[11px] w-20 text-right {overdue ? 'text-red-500 font-medium' : 'text-gray-400'}">{fmt(task.due_date)}</span>
	{/if}
	<span class="flex -space-x-1.5">
		{#each (task.assignee_ids ?? []).slice(0, 3) as a (a)}
			<span class="w-6 h-6 rounded-full bg-gray-200 dark:bg-gray-700 text-[10px] flex items-center justify-center border border-white dark:border-gray-950" title={displayName(a)}>{initials(a)}</span>
		{/each}
	</span>
</button>
