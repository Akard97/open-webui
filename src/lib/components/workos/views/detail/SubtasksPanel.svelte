<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
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
			<input
				type="checkbox"
				checked={subtask.completed}
				onchange={(e) => editSubtask(subtask.id, { completed: (e.target as HTMLInputElement).checked })}
				class="h-4 w-4"
				aria-label="Toggle subtask completion"
			/>
			<span class="flex-1 min-w-0 text-sm {subtask.completed ? 'line-through text-gray-400' : ''}">
				{subtask.title}
			</span>
			<button class="text-gray-400 hover:text-red-500" title="Delete subtask" onclick={() => removeSubtask(subtask.id)}>
				<Icon name="trash" size={14} />
			</button>
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
		<button
			class="inline-flex items-center gap-1.5 text-sm text-teal-600 dark:text-teal-400 hover:underline"
			onclick={() => (creating = true)}
		>
			<Icon name="plus" size={14} /> Add subtask
		</button>
	{/if}

	{#if !$subtasks.length && !creating}
		<div class="text-xs text-gray-400 dark:text-gray-500 py-6 text-center">
			Break this task into smaller steps.
		</div>
	{/if}
</div>
