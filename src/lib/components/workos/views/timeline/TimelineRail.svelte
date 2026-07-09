<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import AssigneeAvatars from '../AssigneeAvatars.svelte';
	import { STATUS_COLOR, PRIORITY_COLOR } from '../../lib/colors';
	import { openTask } from '../../lib/store';
	import type { TimelineItem } from '../../lib/timeline';

	export let item: TimelineItem;
	export let today: number;
	export let compact = false; // mobile: single line, no meta row

	$: t = item.task;
	$: daysLate =
		t.status !== 'done' && t.status !== 'canceled' && item.endDay < today
			? today - item.endDay
			: 0;
</script>

<div class="h-full min-w-0 px-3 flex flex-col justify-center gap-0.5">
	<span class="flex items-center gap-2 min-w-0">
		<span class="flex-none w-2 h-2 rounded-full" style="background:{STATUS_COLOR[t.status]}"></span>
		<button
			class="text-[13px] font-semibold text-gray-900 dark:text-gray-100 truncate text-left hover:text-primary"
			onclick={() => openTask(t.id)}
		>{t.title}</button>
	</span>
	{#if !compact}
		<span class="pl-4 flex items-center gap-1.5 text-[11px] text-gray-400 dark:text-gray-500 whitespace-nowrap overflow-hidden">
			{#if t.assignee_ids?.length}
				<AssigneeAvatars ids={t.assignee_ids} max={3} size={16} />
			{:else}
				<span class="text-gray-300 dark:text-gray-600">Unassigned</span>
			{/if}
			{#if t.priority}
				<span class="flex-none inline-flex items-center gap-0.5" style="color:{PRIORITY_COLOR[t.priority]}">
					<Icon name="flag" size={11} /> {t.priority[0].toUpperCase() + t.priority.slice(1)}
				</span>
			{/if}
			{#if daysLate}
				<span class="flex-none text-red-600 dark:text-red-400 font-medium">· {daysLate}d overdue</span>
			{/if}
		</span>
	{/if}
</div>
