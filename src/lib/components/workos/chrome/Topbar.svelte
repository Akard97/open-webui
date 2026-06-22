<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import { currentWorkstream, currentTeam, workspaces, view, addTask } from '../lib/store';

	let creating = false;
	let title = '';

	$: ws = $currentWorkstream;
	$: parentWorkspace = ws ? $workspaces.find((w) => w.id === ws.workspace_id) : null;

	async function submitNew() {
		if (!title.trim() || !ws) return;
		await addTask(ws.id, { title: title.trim() });
		title = '';
		creating = false;
	}
</script>

<header class="h-12 flex-none flex items-center gap-3 px-3.5 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
	<div class="flex items-center gap-1.5 min-w-0">
		<Icon name="layers" size={16} />
		<span class="text-sm font-semibold truncate">
			{parentWorkspace ? `${parentWorkspace.name} · ` : ''}{ws?.name ?? $currentTeam?.name ?? 'WorkOS'}
		</span>
	</div>

	{#if ws}
		<div class="ml-2 flex items-center gap-1 text-xs">
			<button class="px-2 py-1 rounded {$view === 'board' ? 'bg-gray-100 dark:bg-gray-800 font-medium' : 'text-gray-500'}" onclick={() => view.set('board')}>
				<span class="inline-flex items-center gap-1"><Icon name="columns" size={13} /> Board</span>
			</button>
			<button class="px-2 py-1 rounded {$view === 'list' ? 'bg-gray-100 dark:bg-gray-800 font-medium' : 'text-gray-500'}" onclick={() => view.set('list')}>
				<span class="inline-flex items-center gap-1"><Icon name="list" size={13} /> List</span>
			</button>
		</div>
	{/if}

	<div class="flex-1"></div>

	{#if ws}
		{#if creating}
			<input
				class="text-sm px-2 py-1 rounded border border-gray-300 dark:border-gray-700 bg-transparent w-56"
				placeholder="Task title…"
				bind:value={title}
				onkeydown={(e) => { if (e.key === 'Enter') submitNew(); if (e.key === 'Escape') { creating = false; title = ''; } }}
				autofocus
			/>
			<button class="text-sm px-3 py-1 rounded bg-teal-600 text-white disabled:opacity-50" disabled={!title.trim()} onclick={submitNew}>Add</button>
		{:else}
			<button class="text-sm px-3 py-1 rounded bg-teal-600 text-white inline-flex items-center gap-1" onclick={() => (creating = true)}>
				<Icon name="plus" size={15} /> New task
			</button>
		{/if}
	{/if}
</header>
