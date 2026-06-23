<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import { currentWorkstream, currentTeam, workspaces, view, tasks, initials, addTask } from '../lib/store';

	$: ws = $currentWorkstream;
	$: parentWorkspace = ws ? $workspaces.find((w) => w.id === ws.workspace_id) : null;

	// Decorative avatar stack: unique assignees on the current board (max 3).
	$: assignees = Array.from(new Set($tasks.map((t) => t.assignee_id).filter(Boolean))).slice(0, 3) as string[];

	const TABS = [
		{ key: 'overview', label: 'Overview', icon: 'layers', live: false },
		{ key: 'list', label: 'List', icon: 'list', live: true },
		{ key: 'board', label: 'Board', icon: 'columns', live: true },
		{ key: 'calendar', label: 'Calendar', icon: 'calendar', live: false },
		{ key: 'files', label: 'Files', icon: 'paperclip', live: false }
	];
	function selectTab(t: (typeof TABS)[number]) {
		if (t.live) view.set(t.key as 'board' | 'list');
	}

	// List view keeps an add entry point (board has its own in the filter bar).
	let creating = false;
	let title = '';
	async function submitNew() {
		if (!title.trim() || !ws) return;
		await addTask(ws.id, { title: title.trim() });
		title = '';
		creating = false;
	}
</script>

<header class="flex-none border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
	<!-- Title row -->
	<div class="h-14 flex items-center gap-3 px-4">
		<Icon name="layers" size={18} />
		<span class="text-base font-semibold truncate">
			{parentWorkspace ? `${parentWorkspace.name} · ` : ''}{ws?.name ?? $currentTeam?.name ?? 'WorkOS'}
		</span>
		{#if ws}
			<button class="text-gray-400 hover:text-gray-600" title="Rename" aria-disabled="true"><Icon name="pencil" size={15} /></button>
		{/if}

		<div class="flex-1"></div>

		{#if ws}
			{#if $view === 'list'}
				{#if creating}
					<input
						class="text-sm px-2 py-1 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent w-56"
						placeholder="Task title…"
						bind:value={title}
						onkeydown={(e) => { if (e.key === 'Enter') submitNew(); if (e.key === 'Escape') { creating = false; title = ''; } }}
						autofocus
					/>
				{:else}
					<button class="text-sm px-3 py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white inline-flex items-center gap-1" onclick={() => (creating = true)}>
						<Icon name="plus" size={15} /> New task
					</button>
				{/if}
			{/if}
			<div class="flex -space-x-2">
				{#each assignees as id (id)}
					<span class="w-7 h-7 rounded-full bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-200 border-2 border-white dark:border-gray-950 text-[10px] font-semibold inline-flex items-center justify-center" title={initials(id)}>{initials(id)}</span>
				{/each}
			</div>
			<button class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 inline-flex items-center gap-1.5 hover:bg-gray-100 dark:hover:bg-gray-900" aria-disabled="true"><Icon name="share-2" size={14} /> Share</button>
			<button class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 inline-flex items-center gap-1.5 hover:bg-gray-100 dark:hover:bg-gray-900" aria-disabled="true"><Icon name="zap" size={14} /> Automation</button>
		{/if}
	</div>

	<!-- Tab row -->
	{#if ws}
		<div class="flex items-center gap-1 px-4">
			{#each TABS as t (t.key)}
				<button
					class="px-3 py-2.5 text-sm inline-flex items-center gap-1.5 border-b-2 -mb-px {$view === t.key ? 'border-indigo-600 text-indigo-600 font-medium' : 'border-transparent text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}"
					class:opacity-60={!t.live}
					onclick={() => selectTab(t)}
					aria-disabled={!t.live}
				>
					<Icon name={t.icon} size={14} /> {t.label}
				</button>
			{/each}
		</div>
	{/if}
</header>
