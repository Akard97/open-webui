<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import PriorityFlag from '../../ui/PriorityFlag.svelte';
	import type { Task } from '../../lib/types';
	import { STATUS_COLOR } from '../../lib/colors';
	import { isOverdue } from '../../lib/format';
	import { openTask, currentWorkstream } from '../../lib/store';
	import * as HoverCard from '$lib/components/ui/hover-card';
	import TaskHoverCard from '../TaskHoverCard.svelte';

	export let task: Task;

	$: overdue = isOverdue(task.due_date, task.status, Date.now());
	$: done = task.status === 'done';
	$: color = STATUS_COLOR[task.status];
</script>

<HoverCard.Root openDelay={220} closeDelay={120}>
	<HoverCard.Trigger>
		{#snippet child({ props }: { props: Record<string, any> })}
			<button
				{...props}
				data-task-id={task.id}
				type="button"
				class="w-full flex items-center gap-1.5 rounded-md px-1.5 py-1 text-left text-[11px] leading-tight ring-1 ring-inset ring-transparent transition hover:ring-black/[0.07] dark:hover:ring-white/10"
				style={overdue ? 'background:#dc26261f' : `background:${color}1f`}
				onclick={() => openTask(task.id)}
			>
				{#if overdue}
					<span class="flex-none text-red-600"><Icon name="alert-triangle" size={11} /></span>
				{:else if done}
					<span class="flex-none" style="color:{color}"><Icon name="check" size={11} /></span>
				{:else if task.priority === 'urgent'}
					<span class="flex-none">
						<PriorityFlag priority={task.priority} showLabel={false} />
					</span>
				{:else}
					<span class="flex-none w-[7px] h-[7px] rounded-full" style="background:{color}"></span>
				{/if}
				<span
					class="truncate {overdue ? 'text-red-600' : done ? 'text-gray-400 line-through' : 'text-gray-800 dark:text-gray-100'}"
				>{task.title}</span>
			</button>
		{/snippet}
	</HoverCard.Trigger>
	<HoverCard.Content
		side="right"
		align="start"
		sideOffset={10}
		class="w-[340px] p-0 overflow-hidden rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-xl select-none"
	>
		<TaskHoverCard {task} workstreamName={$currentWorkstream?.name ?? ''} />
	</HoverCard.Content>
</HoverCard.Root>
