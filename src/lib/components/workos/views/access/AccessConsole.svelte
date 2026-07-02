<script lang="ts">
	import { onMount } from 'svelte';
	import Icon from '../../ui/Icon.svelte';
	import TeamList from './TeamList.svelte';
	import TeamDetail from './TeamDetail.svelte';
	import * as api from '../../lib/api';
	import type { AccessTeamOverview } from '../../lib/types';
	import { token, loadBootstrap, openModal } from '../../lib/store';

	let rows: AccessTeamOverview[] = [];
	let selectedTeamId: string | null = null;
	let loaded = false;

	async function refreshOverview(): Promise<void> {
		rows = await api.accessOverview(token()).catch(() => rows);
		if (!selectedTeamId || !rows.some((r) => r.team.id === selectedTeamId)) {
			selectedTeamId = rows[0]?.team.id ?? null;
		}
		loaded = true;
	}

	// Team-level mutations (create/rename/archive/delete) emit no nav event, so the
	// sidebar tree has to be refreshed alongside the console's own data.
	async function refreshAll(): Promise<void> {
		await Promise.all([refreshOverview(), loadBootstrap()]);
	}

	// The "New team" button hands off to the shared create-team modal; when any
	// modal closes, pick up whatever it changed.
	let modalWasOpen = false;
	$: if ($openModal) {
		modalWasOpen = true;
	} else if (modalWasOpen) {
		modalWasOpen = false;
		void refreshOverview();
	}

	onMount(() => void refreshOverview());

	$: selected = rows.find((r) => r.team.id === selectedTeamId) ?? null;
	$: memberTotal = rows.reduce((n, r) => n + r.member_count, 0);
	$: restrictedTotal = rows.reduce(
		(n, r) => n + r.workspaces.filter((w) => w.visibility === 'restricted').length,
		0
	);
</script>

<div class="h-full flex flex-col min-h-0 bg-gray-50 dark:bg-gray-950 text-gray-900 dark:text-gray-100">
	<!-- Title row -->
	<header class="flex-none flex items-center gap-3 px-6 h-16">
		<div class="size-9 rounded-xl bg-brand-900 dark:bg-brand-800 flex items-center justify-center text-white flex-none">
			<Icon name="shield" size={18} />
		</div>
		<div class="flex-1 min-w-0">
			<h1 class="text-lg font-semibold leading-tight">Access console</h1>
			<div class="text-[13px] text-gray-500 dark:text-gray-400 truncate">Manage membership, roles and workspace visibility</div>
		</div>
		<div class="flex items-center gap-2 text-[13px] font-medium text-gray-600 dark:text-gray-300">
			<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800">
				<Icon name="users" size={14} /> {memberTotal}
			</span>
			<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800">
				<Icon name="layers" size={14} /> {rows.length}
			</span>
			<span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800">
				<Icon name="lock" size={14} /> {restrictedTotal}
			</span>
		</div>
	</header>

	<div class="flex-1 overflow-y-auto px-6 pb-6">
		{#if !loaded}
			<div class="py-16 flex items-center justify-center text-sm text-gray-400">Loading…</div>
		{:else if !rows.length}
			<div class="py-16 flex flex-col items-center gap-2 text-center">
				<div class="text-base font-medium">No teams to manage</div>
				<div class="text-sm text-gray-500 max-w-sm">
					You need an owner or admin role in a team for it to show up here.
				</div>
			</div>
		{:else}
			<div class="grid gap-5 items-start" style="grid-template-columns: 272px minmax(0, 1fr);">
				<TeamList
					{rows}
					selectedId={selectedTeamId}
					onSelect={(id) => (selectedTeamId = id)}
				/>
				{#if selected}
					<TeamDetail
						row={selected}
						onOverviewChanged={refreshOverview}
						onTreeChanged={refreshAll}
					/>
				{/if}
			</div>
		{/if}
	</div>
</div>
