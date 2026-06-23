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
	onkeydown={(e) => {
		if (e.target !== e.currentTarget) return;
		if (e.key === 'Enter' || e.key === ' ') {
			e.preventDefault();
			openTask(task.id);
		}
	}}
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
