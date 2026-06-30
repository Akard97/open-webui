<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import type { Task } from '../../lib/types';
	import { STATUS_COLOR } from '../../lib/colors';
	import { openTask, currentWorkstream } from '../../lib/store';
	import * as HoverCard from '$lib/components/ui/hover-card';
	import TaskHoverCard from '../TaskHoverCard.svelte';

	export let tasks: Task[] = [];
</script>

<div class="w-44 flex-none border border-gray-200 dark:border-gray-800 rounded-xl p-2.5 flex flex-col gap-2 bg-white dark:bg-gray-950">
	<div class="flex items-center gap-1.5">
		<Icon name="inbox" size={14} />
		<span class="text-xs font-medium">Unscheduled</span>
		<span class="text-[11px] text-gray-400">{tasks.length}</span>
	</div>
	<p class="text-[11px] text-gray-400 leading-snug">Drag a task onto a day to set its due date.</p>

	<div data-cal-rail class="flex flex-col gap-1.5 min-h-[24px]">
		{#each tasks as t (t.id)}
			<HoverCard.Root openDelay={220} closeDelay={120}>
				<HoverCard.Trigger>
					{#snippet child({ props }: { props: Record<string, any> })}
						<button
							{...props}
							data-task-id={t.id}
							type="button"
							class="flex items-center gap-1.5 rounded-md border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 px-2 py-1.5 text-left text-[11px] cursor-grab"
							onclick={() => openTask(t.id)}
						>
							<span class="flex-none text-gray-300 dark:text-gray-600"><Icon name="grip-vertical" size={12} /></span>
							<span class="flex-none w-[7px] h-[7px] rounded-full" style="background:{STATUS_COLOR[t.status]}"></span>
							<span class="truncate text-gray-800 dark:text-gray-100">{t.title}</span>
						</button>
					{/snippet}
				</HoverCard.Trigger>
				<HoverCard.Content
					side="right"
					align="start"
					sideOffset={10}
					class="w-[340px] p-0 overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-xl select-none"
				>
					<TaskHoverCard task={t} workstreamName={$currentWorkstream?.name ?? ''} />
				</HoverCard.Content>
			</HoverCard.Root>
		{/each}
		{#if !tasks.length}
			<div class="text-[11px] text-gray-300 dark:text-gray-600 py-2 text-center">Nothing unscheduled</div>
		{/if}
	</div>
</div>
