<script lang="ts">
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import StatusDot from '../../ui/StatusDot.svelte';
	import { STATUS_ORDER, STATUS_LABEL, type TaskStatus, type Task } from '../../lib/types';
	import { STATUS_COLOR, statusShape } from '../../lib/colors';
	import { editTask } from '../../lib/store';

	export let task: Task;
</script>

<DropdownMenu.Root>
	<DropdownMenu.Trigger
		title="Change status"
		class="inline-flex items-center justify-center rounded-full p-0.5 hover:bg-gray-100 dark:hover:bg-gray-800"
	>
		<StatusDot shape={statusShape(task.status)} color={STATUS_COLOR[task.status]} size={16} />
	</DropdownMenu.Trigger>
	<DropdownMenu.Content align="start">
		{#each STATUS_ORDER as s (s)}
			<DropdownMenu.Item onSelect={() => editTask(task.id, { status: s })}>
				<span class="inline-flex items-center gap-2">
					<StatusDot shape={statusShape(s)} color={STATUS_COLOR[s]} /> {STATUS_LABEL[s]}
				</span>
			</DropdownMenu.Item>
		{/each}
		<DropdownMenu.Item onSelect={() => editTask(task.id, { status: 'canceled' as TaskStatus })}>
			<span class="inline-flex items-center gap-2">
				<StatusDot shape="x" color={STATUS_COLOR.canceled} /> {STATUS_LABEL.canceled}
			</span>
		</DropdownMenu.Item>
	</DropdownMenu.Content>
</DropdownMenu.Root>
