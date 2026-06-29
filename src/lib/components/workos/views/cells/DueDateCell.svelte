<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { editTask } from '../../lib/store';
	import { formatDueDate } from '../../lib/format';
	import type { Task } from '../../lib/types';

	export let task: Task;
	let editing = false;

	function commit(v: string) {
		editTask(task.id, { due_date: v ? new Date(v).getTime() : null });
		editing = false;
	}
</script>

{#if editing}
	<!-- svelte-ignore a11y_autofocus -->
	<input
		type="date"
		class="text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded px-1.5 py-0.5"
		value={task.due_date ? new Date(task.due_date).toISOString().slice(0, 10) : ''}
		onchange={(e) => commit((e.target as HTMLInputElement).value)}
		onblur={() => (editing = false)}
		autofocus
	/>
{:else}
	<button
		class="inline-flex items-center gap-1.5 rounded-md px-1 -mx-1 py-0.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-800 {task.due_date ? 'text-gray-600 dark:text-gray-300' : 'text-gray-400'}"
		onclick={() => (editing = true)}
	>
		{#if task.due_date}
			{formatDueDate(task.due_date)}
		{:else}
			<Icon name="calendar" size={14} /> Add date
		{/if}
	</button>
{/if}
