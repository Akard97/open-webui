<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import LabelChip from '../ui/LabelChip.svelte';
	import PriorityFlag from '../ui/PriorityFlag.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import { cn } from '$lib/components/ui/utils.js';
	import { buttonVariants } from '$lib/components/ui/button';
	import type { Task, Label } from '../lib/types';
	import AssigneeAvatars from './AssigneeAvatars.svelte';
	import { displayName, openTask, removeTask, roles, currentTeam } from '../lib/store';
	import { user } from '$lib/stores';
	import { canDeleteTask } from '../lib/roles';
	import { formatDateRange, isOverdue } from '../lib/format';
	import { actualProgress, plannedProgress, taskHealth, HEALTH_LABEL, HEALTH_CHIP, type TaskHealth } from '../lib/progress';

	export let task: Task;
	export let labelById: Record<string, Label> = {};

	$: myRole = $currentTeam ? $roles[$currentTeam.id] : undefined;
	$: canDelete = canDeleteTask(task, $user?.id ?? '', myRole);

	// Health → progress-bar fill, echoing the task-detail color scale.
	const HEALTH_BAR: Record<TaskHealth, string> = {
		on_track: 'bg-success',
		at_risk: 'bg-amber-500',
		behind: 'bg-orange-500',
		overdue: 'bg-red-500'
	};
	$: dateRange = formatDateRange(task.start_date, task.due_date);
	$: overdue = isOverdue(task.due_date, task.status, Date.now());
	$: actual = actualProgress(task);
	$: planned = plannedProgress(task.start_date, task.due_date, Date.now());
	$: health = taskHealth(task, Date.now());
	$: cardLabels = (task.labels ?? []).map((lid) => labelById[lid]).filter((l): l is Label => l != null);
	$: shownLabels = cardLabels.slice(0, 3);
	$: labelOverflow = cardLabels.length - shownLabels.length;
	$: barColor =
		task.status === 'done' ? 'bg-success'
		: task.status === 'canceled' ? 'bg-gray-400'
		: health ? HEALTH_BAR[health]
		: 'bg-primary';
</script>

<div
	data-task-id={task.id}
	data-sort-key={task.sort_key}
	class="bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 rounded-xl p-4 cursor-pointer hover:shadow-md transition {task.status === 'backlog' ? 'opacity-60 hover:opacity-100' : ''}"
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
			{#each shownLabels as l (l.id)}
				<LabelChip name={l.name} color={l.color} />
			{/each}
			{#if labelOverflow > 0}
				<LabelChip count={labelOverflow} />
			{/if}
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
	<div class="text-sm font-semibold leading-snug mb-2.5">{task.title}</div>

	<!-- Dates + priority -->
	<div class="flex items-center gap-x-4 gap-y-1 flex-wrap mb-2.5 text-[13px]">
		<span class="inline-flex items-center gap-1.5 {overdue ? 'text-red-600 dark:text-red-400 font-medium' : 'text-gray-600 dark:text-gray-300'}">
			<span class="flex-none {overdue ? '' : 'text-gray-400'}"><Icon name="calendar" size={15} /></span>
			{dateRange ?? '–'}
		</span>
		<PriorityFlag priority={task.priority} />
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
		{#if task.assignee_ids?.length}
			<AssigneeAvatars ids={task.assignee_ids} size={24} max={4} />
			<span class="text-gray-600 dark:text-gray-300 truncate">
				{task.assignee_ids.length === 1 ? displayName(task.assignee_ids[0]) : `${task.assignee_ids.length} assignees`}
			</span>
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
