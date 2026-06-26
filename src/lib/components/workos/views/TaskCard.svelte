<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { cn } from '$lib/components/ui/utils.js';
	import { buttonVariants } from '$lib/components/ui/button';
	import type { Task, Label } from '../lib/types';
	import { initials, displayName, openTask, removeTask, roles, currentTeam } from '../lib/store';
	import { user } from '$lib/stores';
	import { canDeleteTask } from '../lib/roles';
	import { formatDateRange } from '../lib/format';
	import { actualProgress, plannedProgress, taskHealth, HEALTH_LABEL, type TaskHealth } from '../lib/progress';

	export let task: Task;
	export let labelById: Record<string, Label> = {};

	$: myRole = $currentTeam ? $roles[$currentTeam.id] : undefined;
	$: canDelete = canDeleteTask(task, $user?.id ?? '', myRole);

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
	$: planned = plannedProgress(task.start_date, task.due_date, Date.now());
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
	<!-- Labels header + menu -->
	<div class="flex items-start gap-2 mb-2">
		<div class="flex flex-wrap gap-1.5 flex-1 min-w-0">
			{#each task.labels as lid (lid)}
				{#if labelById[lid]}
					<span class="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 rounded bg-gray-50 dark:bg-gray-900">
						<span class="w-1.5 h-1.5 rounded-full" style="background:{labelById[lid].color}"></span>{labelById[lid].name}
					</span>
				{/if}
			{/each}
		</div>
		<DropdownMenu.Root>
			<DropdownMenu.Trigger
				title="More"
				class={cn(buttonVariants({ variant: 'ghost', size: 'icon-sm' }), 'flex-none -mr-1 -mt-1 text-gray-300 hover:text-gray-500')}
				onclick={(e) => e.stopPropagation()}
			>
				<Icon name="more-horizontal" size={16} />
			</DropdownMenu.Trigger>
			<DropdownMenu.Content align="end">
				<DropdownMenu.Item onSelect={() => openTask(task.id)}>
					<span class="inline-flex items-center gap-2"><Icon name="pencil" size={14} /> Edit</span>
				</DropdownMenu.Item>
				{#if canDelete}
					<DropdownMenu.Item class="text-red-600" onSelect={() => removeTask(task.id)}>
						<span class="inline-flex items-center gap-2"><Icon name="trash" size={14} /> Delete</span>
					</DropdownMenu.Item>
				{/if}
			</DropdownMenu.Content>
		</DropdownMenu.Root>
	</div>

	<!-- Title -->
	<div class="text-[15px] font-semibold leading-snug mb-2.5">{task.title}</div>

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

	<!-- Progress (in-progress tasks only) — read-only mirror of the task-detail bar:
	     planned (wide, gray) + actual (thin, health-colored) overlaid, with a legend. -->
	{#if task.status === 'in_progress'}
		<div class="space-y-1.5 mb-3">
			<div class="flex items-center gap-2">
				<div class="relative flex-1 h-2.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
					{#if planned !== null}
						<div class="absolute inset-y-0 left-0 bg-gray-300 dark:bg-gray-600 rounded-full" style="width:{planned}%"></div>
					{/if}
					<div class="absolute left-0 top-1/2 -translate-y-1/2 h-1 {barColor} rounded-full" style="width:{actual}%"></div>
				</div>
				<span class="text-[12px] text-gray-500 dark:text-gray-400 w-10 text-right tabular-nums">{actual}%</span>
			</div>
			{#if planned !== null}
				<div class="flex items-center gap-4 text-[11px]">
					<span class="inline-flex items-center gap-1.5 text-gray-600 dark:text-gray-300">
						<span class="inline-block w-2.5 h-1 rounded-full {barColor}"></span>Actual {actual}%
					</span>
					<span class="inline-flex items-center gap-1.5 text-gray-400">
						<span class="inline-block w-2.5 h-2.5 rounded-full bg-gray-300 dark:bg-gray-600"></span>Planned {planned}%
					</span>
				</div>
			{/if}
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
