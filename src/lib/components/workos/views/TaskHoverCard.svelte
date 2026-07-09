<script lang="ts">
	// Rich detail card shown when hovering a task row in My Work. Read-only peek —
	// full title + description plus the meta you'd otherwise have to open the task to
	// see. Mirrors the board TaskCard's visual language (status/priority/health colors,
	// planned-vs-actual progress) so the two surfaces read the same.
	import Icon from '../ui/Icon.svelte';
	import StatusBadge from '../ui/StatusBadge.svelte';
	import PriorityFlag from '../ui/PriorityFlag.svelte';
	import AssigneeAvatars from './AssigneeAvatars.svelte';
	import type { Task } from '../lib/types';
	import { STATUS_COLOR } from '../lib/colors';
	import {
		taskHealth, HEALTH_LABEL, HEALTH_CHIP, actualProgress, plannedProgress, type TaskHealth
	} from '../lib/progress';
	import { formatDateRange, isOverdue } from '../lib/format';
	import { displayName, labels } from '../lib/store';

	export let task: Task;
	export let workstreamName = '';
	export let now = Date.now();

	const HEALTH_HEX: Record<TaskHealth, string> = {
		on_track: '#16a34a', at_risk: '#d97706', behind: '#ea580c', overdue: '#dc2626'
	};
	function ago(ms: number): string {
		const s = Math.max(0, Math.floor((now - ms) / 1000));
		if (s < 60) return `${s}s`;
		const m = Math.floor(s / 60); if (m < 60) return `${m}m`;
		const h = Math.floor(m / 60); if (h < 24) return `${h}h`;
		return `${Math.floor(h / 24)}d`;
	}

	$: health = taskHealth(task, now);
	$: overdue = isOverdue(task.due_date, task.status, now);
	$: range = formatDateRange(task.start_date, task.due_date);
	$: actual = actualProgress(task);
	$: planned = plannedProgress(task.start_date, task.due_date, now);
	$: barColor =
		task.status === 'done' ? STATUS_COLOR.done
		: task.status === 'canceled' ? STATUS_COLOR.canceled
		: health ? HEALTH_HEX[health]
		: STATUS_COLOR.in_progress;
	$: labelChips = (task.labels ?? [])
		.map((id) => $labels.find((l) => l.id === id))
		.filter((l): l is NonNullable<typeof l> => l != null);
	$: assigneeNames = (task.assignee_ids ?? []).map((id) => displayName(id).split(' ')[0]).join(', ');
</script>

<div class="overflow-hidden">
	<!-- Status accent strip -->
	<div class="h-[3px]" style="background:{STATUS_COLOR[task.status]}"></div>

	<div class="p-3.5">
		<!-- Header: status · priority · key -->
		<div class="flex items-center gap-2 mb-3">
			<StatusBadge status={task.status} size="sm" />
			{#if task.priority}
				<PriorityFlag priority={task.priority} />
			{/if}
			<span class="flex-1"></span>
			<span class="text-[11px] font-medium tabular-nums text-gray-400 dark:text-gray-500">{task.key}</span>
		</div>

		<!-- Full title -->
		<div class="text-[15px] font-semibold leading-snug text-gray-900 dark:text-gray-100">{task.title}</div>

		<!-- Description -->
		{#if task.description}
			<p class="mt-1.5 text-[13px] leading-relaxed text-gray-500 dark:text-gray-400 line-clamp-3">{task.description}</p>
		{:else}
			<p class="mt-1.5 text-[13px] italic text-gray-400 dark:text-gray-600">No description</p>
		{/if}

		<!-- Meta -->
		<div class="mt-3.5 pt-3 border-t border-gray-100 dark:border-gray-800 flex flex-col gap-2.5">
			<div class="flex items-center text-[12.5px]">
				<span class="w-[88px] flex-none text-gray-400 dark:text-gray-500">Workstream</span>
				<span class="inline-flex items-center gap-1.5 min-w-0 text-gray-700 dark:text-gray-200">
					<span class="w-1.5 h-1.5 rounded-full bg-brand-500 flex-none"></span>
					<span class="truncate">{workstreamName || '—'}</span>
				</span>
			</div>
			<div class="flex items-center text-[12.5px]">
				<span class="w-[88px] flex-none text-gray-400 dark:text-gray-500">Timeline</span>
				<span class="inline-flex items-center gap-1.5 {overdue ? 'text-red-500' : 'text-gray-700 dark:text-gray-200'}">
					<span class="flex-none"><Icon name="calendar" size={13} /></span>
					{range ?? 'No dates'}{#if overdue} · overdue{/if}
				</span>
			</div>
			<div class="flex items-center text-[12.5px]">
				<span class="w-[88px] flex-none text-gray-400 dark:text-gray-500">Assignees</span>
				{#if task.assignee_ids?.length}
					<span class="inline-flex items-center gap-2 min-w-0 text-gray-700 dark:text-gray-200">
						<AssigneeAvatars ids={task.assignee_ids} size={20} max={3} />
						<span class="truncate">{assigneeNames}</span>
					</span>
				{:else}
					<span class="text-gray-400">Unassigned</span>
				{/if}
			</div>
		</div>

		<!-- Progress (in-progress only) — planned (wide, gray) + actual (thin, health-colored) -->
		{#if task.status === 'in_progress'}
			<div class="mt-3">
				<div class="flex items-center gap-2.5 mb-1.5">
					<div class="relative flex-1 h-2 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
						{#if planned !== null}
							<div class="absolute inset-y-0 left-0 bg-gray-300 dark:bg-gray-600 rounded-full" style="width:{planned}%"></div>
						{/if}
						<div class="absolute left-0 top-1/2 -translate-y-1/2 h-[3px] rounded-full" style="width:{actual}%; background:{barColor}"></div>
					</div>
					<span class="text-[12px] tabular-nums text-gray-500 dark:text-gray-400 w-9 text-right">{actual}%</span>
				</div>
				{#if planned !== null}
					<div class="flex items-center gap-3.5 text-[11px]">
						<span class="inline-flex items-center gap-1.5 text-gray-600 dark:text-gray-300"><span class="inline-block w-2.5 h-[3px] rounded-full" style="background:{barColor}"></span>Actual {actual}%</span>
						<span class="inline-flex items-center gap-1.5 text-gray-400"><span class="inline-block w-2 h-2 rounded-full bg-gray-300 dark:bg-gray-600"></span>Planned {planned}%</span>
					</div>
				{/if}
			</div>
		{/if}

		<!-- Labels -->
		{#if labelChips.length}
			<div class="mt-3 flex flex-wrap gap-1.5">
				{#each labelChips as l (l.id)}
					<span class="inline-flex items-center gap-1.5 text-[11px] px-2 py-0.5 rounded bg-gray-50 dark:bg-gray-800/70 text-gray-600 dark:text-gray-300">
						<span class="w-1.5 h-1.5 rounded-full flex-none" style="background:{l.color}"></span>{l.name}
					</span>
				{/each}
			</div>
		{/if}

		<!-- Footer: health · subtasks · updated -->
		<div class="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800 flex items-center gap-2 text-[11px]">
			{#if health}
				<span class="rounded-md px-2 py-0.5 font-medium {HEALTH_CHIP[health]}">{HEALTH_LABEL[health]}</span>
			{/if}
			{#if (task.subtask_total ?? 0) > 0}
				<span class="text-gray-500 dark:text-gray-400">{task.subtask_completed ?? 0}/{task.subtask_total ?? 0} subtasks</span>
			{/if}
			<span class="flex-1"></span>
			<span class="text-gray-400 dark:text-gray-500">Updated {ago(task.updated_at)} ago</span>
		</div>
	</div>
</div>
