<script lang="ts">
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import Icon from '../../ui/Icon.svelte';
	import { PRIORITY_ORDER, type TaskPriority, type Task } from '../../lib/types';
	import { PRIORITY_COLOR } from '../../lib/colors';
	import { editTask } from '../../lib/store';

	export let task: Task;

	const LABEL: Record<TaskPriority, string> = {
		urgent: 'Urgent', high: 'High', medium: 'Medium', low: 'Low'
	};
</script>

<DropdownMenu.Root>
	<DropdownMenu.Trigger
		title="Set priority"
		class="inline-flex items-center gap-1.5 rounded-md px-1 -mx-1 py-0.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-800"
	>
		{#if task.priority}
			<span style="color:{PRIORITY_COLOR[task.priority]}"><Icon name="flag" size={15} /></span>
			<span>{LABEL[task.priority]}</span>
		{:else}
			<span class="text-gray-300 dark:text-gray-600"><Icon name="flag" size={15} /></span>
		{/if}
	</DropdownMenu.Trigger>
	<DropdownMenu.Content align="start">
		<DropdownMenu.Item onSelect={() => editTask(task.id, { priority: null })}>
			<span class="text-gray-400">No priority</span>
		</DropdownMenu.Item>
		{#each PRIORITY_ORDER as p (p)}
			<DropdownMenu.Item onSelect={() => editTask(task.id, { priority: p })}>
				<span class="inline-flex items-center gap-2">
					<span style="color:{PRIORITY_COLOR[p]}"><Icon name="flag" size={14} /></span> {LABEL[p]}
				</span>
			</DropdownMenu.Item>
		{/each}
	</DropdownMenu.Content>
</DropdownMenu.Root>
