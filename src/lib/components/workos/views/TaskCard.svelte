<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import type { Task, Label } from '../lib/types';
	import { initials, displayName, openTask } from '../lib/store';
	import { formatDateRange } from '../lib/format';
	import { actualProgress, taskHealth, HEALTH_LABEL, type TaskHealth } from '../lib/progress';

	export let task: Task;
	export let labelById: Record<string, Label> = {};

	const PRIORITY_META: Record<string, { color: string; label: string }> = {
		urgent: { color: '#dc2626', label: 'Urgent' },
		high: { color: '#ea580c', label: 'High' },
		medium: { color: '#ca8a04', label: 'Medium' },
		low: { color: '#6b7280', label: 'Low' }
	};
	// Health → chip tint + progress-bar fill, echoing the task-detail color scale.
	const HEALTH_CHIP: Record<TaskHealth, string> = {
		on_track: 'bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300',
		at_risk: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
		behind: 'bg-orange-100 text-orange-700 dark:bg-orange-900/40 dark:text-orange-300',
		overdue: 'bg-red-100 text-red-700 dark:bg-red-900/40 dark:text-red-300'
	};
	const HEALTH_BAR: Record<TaskHealth, string> = {
		on_track: 'bg-success',
		at_risk: 'bg-amber-500',
		behind: 'bg-orange-500',
		overdue: 'bg-red-500'
	};
	$: prio = task.priority ? PRIORITY_META[task.priority] : { color: '#cbd5e1', label: '–' };
	$: dateRange = formatDateRange(task.start_date, task.due_date);
	$: actual = actualProgress(task);
	$: health = taskHealth(task, Date.now());
	$: barColor =
		task.status === 'done' ? 'bg-success'
		: task.status === 'canceled' ? 'bg-gray-400'
		: health ? HEALTH_BAR[health]
		: 'bg-primary';
</script>

<div
	data-task-id={task.id}
	data-sort-key={task.sort_key}
	class="bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 rounded-lg p-4 cursor-pointer hover:shadow-md transition {task.status === 'backlog' ? 'opacity-60 hover:opacity-100' : ''}"
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
	<!-- Labels header -->
	{#if task.labels.length}
		<div class="flex flex-wrap gap-1.5 mb-2">
			{#each task.labels as lid (lid)}
				{#if labelById[lid]}
					<span class="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-gray-50 dark:bg-gray-900">
						<span class="w-1.5 h-1.5 rounded-full" style="background:{labelById[lid].color}"></span>{labelById[lid].name}
					</span>
				{/if}
			{/each}
		</div>
	{/if}

	<!-- Title + spinner + menu -->
	<div class="flex items-start gap-2 mb-2.5">
		<div class="text-[15px] font-semibold leading-snug flex-1">{task.title}</div>
		<button
			class="text-gray-300 hover:text-gray-500 flex-none -mr-1"
			title="More"
			aria-disabled="true"
			tabindex="-1"
			onclick={(e) => e.stopPropagation()}
		>
			<Icon name="more-horizontal" size={16} />
		</button>
	</div>

	<!-- Dates + priority -->
	<div class="flex items-center gap-x-4 gap-y-1 flex-wrap mb-2.5 text-[13px] text-gray-600 dark:text-gray-300">
		<span class="inline-flex items-center gap-1.5">
			<span class="text-gray-400 flex-none"><Icon name="calendar" size={15} /></span>
			{dateRange ?? '–'}
		</span>
		<span class="inline-flex items-center gap-1.5">
			<span class="flex-none" style="color:{prio.color}"><Icon name="flag" size={15} /></span>
			{prio.label}
		</span>
	</div>

	<!-- Progress (in-progress tasks only) -->
	{#if task.status === 'in_progress'}
		<div class="flex items-center gap-2 mb-3">
			<div class="flex-1 h-[5px] rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
				<div class="h-full rounded-full {barColor}" style="width:{actual}%"></div>
			</div>
			<span class="text-[12px] text-gray-500 dark:text-gray-400 tabular-nums">{actual}%</span>
		</div>
	{/if}

	<!-- Footer: assignee · subtasks · health -->
	<div class="flex items-center gap-2 pt-2.5 border-t border-gray-100 dark:border-gray-800 text-[12px]">
		{#if task.assignee_id}
			<span class="w-6 h-6 rounded-full bg-brand-100 text-brand-700 dark:bg-brand-900 dark:text-brand-200 text-[10px] font-semibold inline-flex items-center justify-center flex-none">{initials(task.assignee_id)}</span>
			<span class="text-gray-600 dark:text-gray-300 truncate">{displayName(task.assignee_id)}</span>
		{:else}
			<span class="text-gray-400">Unassigned</span>
		{/if}
		<div class="flex-1"></div>
		{#if (task.subtask_total ?? 0) > 0}
			<span class="text-gray-500 dark:text-gray-400 flex-none">{task.subtask_completed ?? 0}/{task.subtask_total ?? 0} subtasks</span>
		{/if}
		{#if health}
			<span class="rounded-md px-2 py-1 font-medium flex-none {HEALTH_CHIP[health]}">{HEALTH_LABEL[health]}</span>
		{/if}
	</div>
</div>
