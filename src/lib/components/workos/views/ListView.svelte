<script lang="ts">
	import Pills from '../ui/Pills.svelte';
	import { STATUS_ORDER, STATUS_LABEL } from '../lib/types';
	import { tasksByStatus, openTask, directory, initials } from '../lib/store';

	$: byStatus = $tasksByStatus;
	$: void $directory; // re-render when names load
</script>

<div class="h-full overflow-y-auto py-2">
	{#each STATUS_ORDER as status (status)}
		{#if (byStatus[status] ?? []).length}
			<div class="mb-2">
				<div class="flex items-center gap-2 px-3.5 py-2 sticky top-0 bg-gray-50 dark:bg-gray-900 z-[1]">
					<Pills {status} />
					<span class="text-sm font-semibold">{STATUS_LABEL[status]}</span>
					<span class="text-xs text-gray-400">{byStatus[status].length}</span>
				</div>
				{#each byStatus[status] as task (task.id)}
					<div
						class="grid items-center gap-2.5 h-10 px-3.5 cursor-pointer border-b border-gray-100 dark:border-gray-800 hover:bg-gray-100/60 dark:hover:bg-gray-800/40"
						style="grid-template-columns: 18px 70px 1fr 90px 90px 28px"
						onclick={() => openTask(task.id)}
						role="button"
						tabindex="0"
					>
						<Pills status={task.status} />
						<span class="text-xs text-gray-400 font-mono">{task.key}</span>
						<span class="text-sm font-medium truncate">{task.title}</span>
						<span class="text-xs"><Pills priority={task.priority} /></span>
						<span class="text-xs text-gray-500">
							{task.due_date ? new Date(task.due_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '—'}
						</span>
						<span class="w-6 h-6 rounded-full bg-brand-100 text-brand-800 text-[10px] flex items-center justify-center" title={task.assignee_id ?? ''}>
							{initials(task.assignee_id)}
						</span>
					</div>
				{/each}
			</div>
		{/if}
	{/each}
</div>
