<script lang="ts">
	import { STATUS_COLOR } from '../../lib/colors';
	import { STATUS_LABEL } from '../../lib/types';
	import { actualProgress } from '../../lib/progress';
	import { barGeometry, type TimelineItem, type TimelineWindow } from '../../lib/timeline';
	import { openTask, initials, currentWorkstream } from '../../lib/store';
	import * as HoverCard from '$lib/components/ui/hover-card';
	import TaskHoverCard from '../TaskHoverCard.svelte';

	export let item: TimelineItem;
	export let win: TimelineWindow;
	export let dayWidth: number;
	export let today: number;

	$: t = item.task;
	$: color = STATUS_COLOR[t.status];
	$: geom = barGeometry(item, win, dayWidth, today);
	$: pct = actualProgress(t);
	$: daysLate = today - item.endDay;
	$: stateText =
		t.status === 'done' ? '✓ Done' : t.status === 'in_progress' && pct > 0 ? `${pct}%` : STATUS_LABEL[t.status];
</script>

<HoverCard.Root openDelay={300} closeDelay={80}>
	<HoverCard.Trigger>
		{#snippet child({ props }: { props: Record<string, any> })}
			{#if item.kind === 'milestone'}
				<button
					{...props}
					type="button"
					class="absolute top-1/2 -translate-y-1/2 z-10"
					style="left: {geom.left + geom.width / 2 - 8}px;"
					title={t.title}
					onclick={() => openTask(t.id)}
				>
					<span class="block w-4 h-4 rotate-45 rounded-[3px]" style="background:{color}; box-shadow: 0 1px 4px {color}66;"></span>
				</button>
			{:else}
				<button
					{...props}
					type="button"
					class="absolute top-1/2 -translate-y-1/2 h-6 rounded-md z-10 flex items-center px-2 gap-1.5 text-[10px] font-semibold text-white whitespace-nowrap overflow-hidden"
					style="left: {geom.left}px; width: {geom.width}px; background: {t.status === 'done'
						? color
						: `linear-gradient(to right, ${color} ${pct}%, ${color}42 ${pct}%)`}; box-shadow: 0 1px 3px {color}55;"
					onclick={() => openTask(t.id)}
				>
					{#if geom.width >= 64}<span class="flex-none">{stateText}</span>{/if}
					{#if geom.width >= 48 && t.assignee_ids?.length}
						<span class="ml-auto flex-none w-[18px] h-[18px] rounded-full bg-white text-[8px] font-bold inline-flex items-center justify-center" style="color:{color}">
							{initials(t.assignee_ids[0])}
						</span>
					{/if}
				</button>
			{/if}
		{/snippet}
	</HoverCard.Trigger>
	<HoverCard.Content
		side="top"
		align="start"
		sideOffset={8}
		class="w-[340px] p-0 overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-xl select-none"
	>
		<TaskHoverCard task={t} workstreamName={$currentWorkstream?.name ?? ''} />
	</HoverCard.Content>
</HoverCard.Root>

{#if geom.slipWidth > 0}
	<!-- Overdue slip tail: hatched red from the bar/milestone end to the today line -->
	<span
		class="absolute top-1/2 -translate-y-1/2 h-6 rounded-r-md z-[9] flex items-center justify-end pr-1.5 text-[9px] font-bold text-white pointer-events-none"
		style="left: {geom.left + geom.width}px; width: {geom.slipWidth}px; background: repeating-linear-gradient(-45deg, #dc2626, #dc2626 4px, #ef4444 4px, #ef4444 8px);"
	>
		{#if geom.slipWidth >= 40}⚠ {daysLate}d{/if}
	</span>
{/if}
