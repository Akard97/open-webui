<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import type { Task } from '../../lib/types';
	import { STATUS_COLOR } from '../../lib/colors';
	import { isOverdue } from '../../lib/calendar';
	import { openTask } from '../../lib/store';

	export let task: Task;

	$: overdue = isOverdue(task, Date.now());
	$: done = task.status === 'done';
	$: color = STATUS_COLOR[task.status];
</script>

<button
	data-task-id={task.id}
	class="w-full flex items-center gap-1.5 rounded-md px-1.5 py-1 text-left text-[11px] leading-tight"
	style={overdue ? 'background:#dc26261f' : `background:${color}1f`}
	title={task.title}
	onclick={() => openTask(task.id)}
>
	{#if overdue}
		<Icon name="alert-triangle" size={11} />
	{:else if task.priority === 'urgent'}
		<span class="flex-none text-red-600"><Icon name="flag" size={11} /></span>
	{:else if done}
		<span class="flex-none" style="color:{color}"><Icon name="check" size={11} /></span>
	{:else}
		<span class="flex-none w-[7px] h-[7px] rounded-full" style="background:{color}"></span>
	{/if}
	<span
		class="truncate {overdue ? 'text-red-600' : done ? 'text-gray-400 line-through' : 'text-gray-800 dark:text-gray-100'}"
	>{task.title}</span>
</button>
