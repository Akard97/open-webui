<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { Button } from '$lib/components/ui/button';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import { subtasks, addSubtask, editSubtask, removeSubtask } from '../../lib/store';

	export let taskId: string;

	let title = '';
	let creating = false;

	async function submit() {
		if (!title.trim()) return;
		await addSubtask(taskId, title.trim());
		title = '';
		creating = false;
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
