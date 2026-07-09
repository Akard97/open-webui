<script lang="ts">
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import Icon from '../../ui/Icon.svelte';
	import AssigneeAvatars from '../AssigneeAvatars.svelte';
	import { directory, displayName, editTask } from '../../lib/store';
	import { toggleAssignee } from '../../lib/assignees';
	import type { Task } from '../../lib/types';

	export let task: Task;
	export let placeholder = 'Unassigned';

	$: assigned = task.assignee_ids ?? [];
	$: members = Object.entries($directory).map(([id, u]) => ({ id, name: u.name }));
	$: summary =
		assigned.length === 0 ? '' :
		assigned.length === 1 ? displayName(assigned[0]) :
		`${displayName(assigned[0])} +${assigned.length - 1}`;

	function toggle(id: string) {
		editTask(task.id, { assignee_ids: toggleAssignee(assigned, id) });
	}
</script>

<DropdownMenu.Root>
	<DropdownMenu.Trigger
		class="inline-flex items-center gap-2 rounded-md px-1 -mx-1 py-0.5 hover:bg-gray-100 dark:hover:bg-gray-900"
	>
		{#if assigned.length}
			<AssigneeAvatars ids={assigned} size={22} max={4} />
			<span class="text-sm">{summary}</span>
		{:else}
			<span class="inline-flex items-center gap-1.5 text-sm text-gray-400">
				<Icon name="user" size={15} /> {placeholder}
			</span>
		{/if}
	</DropdownMenu.Trigger>
	<DropdownMenu.Content class="w-64 max-h-64 overflow-y-auto">
		{#each members as m (m.id)}
			<DropdownMenu.CheckboxItem
				checked={assigned.includes(m.id)}
				closeOnSelect={false}
				onCheckedChange={() => toggle(m.id)}
			>
				<span class="inline-flex items-center gap-2">
					<AssigneeAvatars ids={[m.id]} max={1} size={20} />
					{m.name}
				</span>
			</DropdownMenu.CheckboxItem>
		{/each}
		{#if !members.length}<DropdownMenu.Item disabled>No members</DropdownMenu.Item>{/if}
	</DropdownMenu.Content>
</DropdownMenu.Root>
