<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import { Button } from '$lib/components/ui/button';
	import { currentWorkstream, currentTeam, workspaces, view, tasks, initials } from '../lib/store';
	import { avatarColors } from '../lib/avatar';

	$: ws = $currentWorkstream;
	$: parentWorkspace = ws ? $workspaces.find((w) => w.id === ws.workspace_id) : null;

	// Decorative avatar stack: unique assignees on the current board (max 3).
	$: assignees = Array.from(new Set($tasks.flatMap((t) => t.assignee_ids ?? []))).slice(0, 3) as string[];

	const TABS = [
		{ key: 'overview', label: 'Overview', icon: 'layers', live: true },
		{ key: 'list', label: 'List', icon: 'list', live: true },
		{ key: 'board', label: 'Board', icon: 'columns', live: true },
		{ key: 'timeline', label: 'Timeline', icon: 'chart-gantt', live: true },
		{ key: 'calendar', label: 'Calendar', icon: 'calendar', live: true },
		{ key: 'files', label: 'Files', icon: 'paperclip', live: false }
	];
	function selectTab(t: (typeof TABS)[number]) {
		if (t.live) view.set(t.key as 'board' | 'list' | 'calendar' | 'overview' | 'timeline');
	}
</script>

<header class="flex-none border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
	<!-- Title row (desktop only — the mobile header row already shows the breadcrumb title) -->
	<div class="hidden md:flex h-14 items-center gap-3 px-4">
		<Icon name="layers" size={18} />
		<span class="text-base font-semibold truncate">
			{parentWorkspace ? `${parentWorkspace.name} · ` : ''}{ws?.name ?? $currentTeam?.name ?? 'WorkOS'}
		</span>
		{#if ws}
			<Button variant="ghost" size="sm" class="text-gray-400" title="Rename" disabled><Icon name="pencil" size={15} /></Button>
		{/if}

		<div class="flex-1"></div>

		{#if ws}
			<div class="hidden md:flex items-center gap-3">
				<div class="flex -space-x-2">
				{#each assignees as id (id)}
					{@const colors = avatarColors(id)}
					<span
						class="size-7 rounded-full border-2 border-white dark:border-gray-950 text-[10px] font-semibold inline-flex items-center justify-center"
						style="background:{colors.background};color:{colors.foreground}"
						title={initials(id)}
					>
						{initials(id)}
					</span>
				{/each}
			</div>
			<Button variant="ghost" size="sm" disabled><Icon name="share-2" size={14} /> Share</Button>
			<Button variant="ghost" size="sm" disabled><Icon name="zap" size={14} /> Automation</Button>
			</div>
		{/if}
	</div>

	<!-- Tab row -->
	{#if ws && $view !== 'admin'}
		<div class="flex items-center gap-1 px-4 overflow-x-auto scrollbar-hidden">
			{#each TABS as t (t.key)}
				<button
					class="flex-none whitespace-nowrap px-3 py-2.5 text-sm inline-flex items-center gap-1.5 border-b-2 -mb-px {$view === t.key ? 'border-primary text-primary font-medium' : 'border-transparent text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100'}"
					class:opacity-75={!t.live}
					onclick={() => selectTab(t)}
					aria-disabled={!t.live}
				>
					<Icon name={t.icon} size={14} /> {t.label}
				</button>
			{/each}
		</div>
	{/if}
</header>
