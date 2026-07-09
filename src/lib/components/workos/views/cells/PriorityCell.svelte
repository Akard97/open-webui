<script lang="ts">
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import PriorityFlag from '../../ui/PriorityFlag.svelte';
	import { PRIORITY_ORDER, type Task } from '../../lib/types';
	import { editTask } from '../../lib/store';

	export let task: Task;
</script>

<DropdownMenu.Root>
	<DropdownMenu.Trigger
		title="Set priority"
		class="inline-flex items-center gap-1.5 rounded-md px-1 -mx-1 py-0.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-800"
	>
		<PriorityFlag priority={task.priority} />
	</DropdownMenu.Trigger>
	<DropdownMenu.Content align="start">
		<DropdownMenu.Item onSelect={() => editTask(task.id, { priority: null })}>
			<span class="text-gray-400">No priority</span>
		</DropdownMenu.Item>
		{#each PRIORITY_ORDER as p (p)}
			<DropdownMenu.Item onSelect={() => editTask(task.id, { priority: p })}>
				<PriorityFlag priority={p} />
			</DropdownMenu.Item>
		{/each}
	</DropdownMenu.Content>
</DropdownMenu.Root>
