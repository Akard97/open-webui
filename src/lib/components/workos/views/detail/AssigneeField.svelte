<script lang="ts">
	import { Avatar, AvatarFallback } from '$lib/components/ui/avatar';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import Icon from '../../ui/Icon.svelte';
	import { directory, displayName, initials, editTask } from '../../lib/store';
	import type { Task } from '../../lib/types';

	export let task: Task;

	$: assigned = task.assignee_id ?? null;
	$: members = Object.entries($directory).map(([id, u]) => ({ id, name: u.name }));

	const fallback = 'bg-teal-100 text-teal-700 dark:bg-teal-900/40 dark:text-teal-300';

	function assign(id: string | null) {
		editTask(task.id, { assignee_id: id });
	}
</script>

<DropdownMenu.Root>
	<DropdownMenu.Trigger
		class="inline-flex items-center gap-2 rounded-md px-1 -mx-1 py-0.5 hover:bg-gray-100 dark:hover:bg-gray-900"
	>
		{#if assigned}
			<Avatar size="sm">
				<AvatarFallback class="{fallback} text-[11px]">{initials(assigned)}</AvatarFallback>
			</Avatar>
			<span class="text-sm">{displayName(assigned)}</span>
		{:else}
			<span class="inline-flex items-center gap-1.5 text-sm text-gray-400">
				<Icon name="user" size={15} /> Unassigned
			</span>
		{/if}
	</DropdownMenu.Trigger>
	<DropdownMenu.Content class="max-h-64 overflow-y-auto">
		<DropdownMenu.Item onSelect={() => assign(null)}>Unassigned</DropdownMenu.Item>
		{#each members as m (m.id)}
			<DropdownMenu.Item onSelect={() => assign(m.id)}>
				<span class="inline-flex items-center gap-2">
					<Avatar size="sm" class="size-5">
						<AvatarFallback class="{fallback} text-[10px]">{initials(m.id)}</AvatarFallback>
					</Avatar>
					{m.name}
				</span>
			</DropdownMenu.Item>
		{/each}
		{#if !members.length}<DropdownMenu.Item disabled>No members</DropdownMenu.Item>{/if}
	</DropdownMenu.Content>
</DropdownMenu.Root>
