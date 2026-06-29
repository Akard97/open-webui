<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import type { Task } from '../../lib/types';
	import { STATUS_COLOR } from '../../lib/colors';
	import { openTask } from '../../lib/store';

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
			<button
				data-task-id={t.id}
				class="flex items-center gap-1.5 rounded-md border border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 px-2 py-1.5 text-left text-[11px] cursor-grab"
				title={t.title}
				onclick={() => openTask(t.id)}
			>
				<span class="flex-none text-gray-300 dark:text-gray-600"><Icon name="grip-vertical" size={12} /></span>
				<span class="flex-none w-[7px] h-[7px] rounded-full" style="background:{STATUS_COLOR[t.status]}"></span>
				<span class="truncate text-gray-800 dark:text-gray-100">{t.title}</span>
			</button>
		{/each}
		{#if !tasks.length}
			<div class="text-[11px] text-gray-300 dark:text-gray-600 py-2 text-center">Nothing unscheduled</div>
		{/if}
	</div>
</div>
