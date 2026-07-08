<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { STATUS_COLOR, PRIORITY_COLOR } from '../../lib/colors';
	import { openTask } from '../../lib/store';
	import type { Task } from '../../lib/types';

	export let tasks: Task[] = [];
	export let collapsed = false;

	function dragStart(e: DragEvent, t: Task) {
		e.dataTransfer?.setData('text/workos-task', t.id);
		if (e.dataTransfer) e.dataTransfer.effectAllowed = 'move';
	}
</script>

{#if collapsed}
	<button
		class="flex-none w-9 border-l border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-900 flex flex-col items-center gap-2 py-3 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
		title="Show unscheduled"
		onclick={() => (collapsed = false)}
	>
		<Icon name="chevron-left" size={14} />
		<span class="text-[10px] font-bold [writing-mode:vertical-rl]">UNSCHEDULED · {tasks.length}</span>
	</button>
{:else}
	<div class="flex-none w-52 border-l border-gray-200 dark:border-gray-800 bg-gray-50/60 dark:bg-gray-900/40 p-2.5 flex flex-col gap-2 overflow-y-auto">
		<div class="flex items-center gap-1.5">
			<span class="text-[10px] font-bold tracking-wider text-gray-500 dark:text-gray-400">UNSCHEDULED</span>
			<span class="text-[10px] px-1.5 rounded-full bg-gray-200 dark:bg-gray-800 text-gray-500">{tasks.length}</span>
			<span class="flex-1"></span>
			<button class="text-gray-400 hover:text-gray-600" title="Collapse" onclick={() => (collapsed = true)}>
				<Icon name="chevron-right" size={14} />
			</button>
		</div>
		<p class="text-[11px] text-gray-400 leading-snug">Drag a task onto the chart to schedule it.</p>
		{#each tasks as t (t.id)}
			<div
				role="button"
				tabindex="0"
				draggable="true"
				ondragstart={(e) => dragStart(e, t)}
				class="rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 px-2.5 py-2 cursor-grab shadow-sm"
				onclick={() => openTask(t.id)}
				onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') openTask(t.id); }}
			>
				<span class="flex items-center gap-1.5 min-w-0">
					<span class="flex-none text-gray-300 dark:text-gray-600"><Icon name="grip-vertical" size={12} /></span>
					<span class="flex-none w-2 h-2 rounded-full" style="background:{STATUS_COLOR[t.status]}"></span>
					<span class="text-[12px] font-medium truncate text-gray-800 dark:text-gray-100">{t.title}</span>
				</span>
				{#if t.priority}
					<span class="mt-0.5 pl-[26px] flex items-center gap-1 text-[10px]" style="color:{PRIORITY_COLOR[t.priority]}">
						<Icon name="flag" size={10} /> {t.priority[0].toUpperCase() + t.priority.slice(1)}
					</span>
				{/if}
			</div>
		{/each}
		{#if !tasks.length}
			<div class="text-[11px] text-gray-300 dark:text-gray-600 py-2 text-center">Nothing unscheduled</div>
		{/if}
	</div>
{/if}
