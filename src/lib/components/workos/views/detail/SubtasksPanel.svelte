<script lang="ts">
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import Icon from '../../ui/Icon.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import AssigneeAvatars from '../AssigneeAvatars.svelte';
	import { subtasks, addSubtask, editSubtask, removeSubtask, directory, roles } from '../../lib/store';
	import { toggleAssignee } from '../../lib/assignees';
	import { canEditTask } from '../../lib/roles';
	import { user } from '$lib/stores';
	import type { Task, Subtask } from '../../lib/types';

	export let task: Task;

	let title = '';
	let creating = false;

	$: parentIds = task.assignee_ids ?? [];
	$: members = Object.entries($directory).map(([id, u]) => ({ id, name: u.name }));
	$: onTask = members.filter((m) => parentIds.includes(m.id));
	$: everyoneElse = members.filter((m) => !parentIds.includes(m.id));
	// Whether the viewer may expand the parent's assignee list (mirrors the
	// server's task.write gate on auto-add; workspace-admin edge under-shown,
	// server remains authoritative).
	$: canExpand =
		$user?.role === 'admin' || canEditTask(task, $user?.id ?? '', $roles[task.team_id], undefined);

	async function submit() {
		if (!title.trim()) return;
		await addSubtask(task.id, title.trim());
		title = '';
		creating = false;
	}

	function toggle(subtask: Subtask, id: string) {
		editSubtask(subtask.id, { assignee_ids: toggleAssignee(subtask.assignee_ids, id) });
	}
</script>

<div class="pt-4 space-y-2">
	{#each $subtasks as subtask (subtask.id)}
		<div class="flex items-center gap-2 rounded-lg border border-gray-200 dark:border-gray-800 px-3 py-2">
			<Checkbox
				checked={subtask.completed}
				onCheckedChange={(v) => editSubtask(subtask.id, { completed: !!v })}
				class="size-4"
				aria-label="Toggle subtask completion"
			/>
			<span class="flex-1 min-w-0 text-sm {subtask.completed ? 'line-through text-gray-400' : ''}">
				{subtask.title}
			</span>
			<DropdownMenu.Root>
				<DropdownMenu.Trigger
					class="inline-flex items-center rounded-md p-0.5 hover:bg-gray-100 dark:hover:bg-gray-900"
					aria-label="Edit subtask assignees"
				>
					{#if (subtask.assignee_ids ?? []).length}
						<AssigneeAvatars ids={subtask.assignee_ids} size={20} max={3} />
					{:else}
						<span
							class="flex size-6 items-center justify-center rounded-full border-[1.5px] border-dashed border-gray-300 text-gray-400 dark:border-gray-700 dark:text-gray-500"
						>
							<Icon name="user-plus" size={13} />
						</span>
					{/if}
				</DropdownMenu.Trigger>
				<DropdownMenu.Content class="w-72 max-h-72 overflow-y-auto">
					<DropdownMenu.Label class="wos-caption text-gray-400">On this task</DropdownMenu.Label>
					{#each onTask as m (m.id)}
						<DropdownMenu.CheckboxItem
							checked={(subtask.assignee_ids ?? []).includes(m.id)}
							closeOnSelect={false}
							onCheckedChange={() => toggle(subtask, m.id)}
						>
							<span class="inline-flex items-center gap-2">
								<AssigneeAvatars ids={[m.id]} max={1} size={20} />
								{m.name}
							</span>
						</DropdownMenu.CheckboxItem>
					{/each}
					{#if !onTask.length}
						<DropdownMenu.Item disabled>No assignees on this task</DropdownMenu.Item>
					{/if}
					{#if canExpand && everyoneElse.length}
						<DropdownMenu.Separator />
						<DropdownMenu.Label class="wos-caption text-gray-400">Everyone else</DropdownMenu.Label>
						{#each everyoneElse as m (m.id)}
							<DropdownMenu.CheckboxItem
								checked={(subtask.assignee_ids ?? []).includes(m.id)}
								closeOnSelect={false}
								onCheckedChange={() => toggle(subtask, m.id)}
							>
								<span class="inline-flex min-w-0 flex-1 items-center gap-2">
									<AssigneeAvatars ids={[m.id]} max={1} size={20} />
									<span class="truncate">{m.name}</span>
									{#if (subtask.assignee_ids ?? []).includes(m.id)}
										<span
											class="wos-micro ml-auto rounded-full bg-amber-100 px-2 py-px text-amber-700 dark:bg-amber-950 dark:text-amber-400"
										>+ added to task</span>
									{/if}
								</span>
							</DropdownMenu.CheckboxItem>
						{/each}
						<DropdownMenu.Separator />
						<div class="flex items-center gap-1.5 px-2 py-1.5 text-[11px] text-gray-400 dark:text-gray-500">
							<Icon name="user-plus" size={12} /> Picking someone new also adds them to the task
						</div>
					{/if}
				</DropdownMenu.Content>
			</DropdownMenu.Root>
			<Button variant="ghost" size="icon-xs" class="text-gray-400 hover:text-red-500" title="Delete subtask" onclick={() => removeSubtask(subtask.id)}>
				<Icon name="trash" size={14} />
			</Button>
		</div>
	{/each}

	{#if creating}
		<!-- svelte-ignore a11y_autofocus -->
		<input
			class="w-full text-sm rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent px-3 py-2"
			placeholder="Subtask title..."
			bind:value={title}
			onkeydown={(e) => {
				if (e.key === 'Enter') submit();
				if (e.key === 'Escape') {
					creating = false;
					title = '';
				}
			}}
			autofocus
		/>
	{:else}
		<Button variant="ghost" size="sm" class="text-primary" onclick={() => (creating = true)}>
			<Icon name="plus" size={14} /> Add subtask
		</Button>
	{/if}

	{#if !$subtasks.length && !creating}
		<div class="text-xs text-gray-400 dark:text-gray-500 py-6 text-center">
			Break this task into smaller steps.
		</div>
	{/if}
</div>
