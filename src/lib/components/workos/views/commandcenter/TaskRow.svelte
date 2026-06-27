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
