<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { filterOverview } from '../../lib/accessConsole';
	import { openModal } from '../../lib/store';
	import type { AccessTeamOverview } from '../../lib/types';

	export let rows: AccessTeamOverview[] = [];
	export let selectedId: string | null = null;
	export let onSelect: (id: string) => void;

	let query = '';
	$: visible = filterOverview(rows, query);

	const ROLE_LABEL: Record<string, string> = { owner: 'Owner', admin: 'Admin', member: 'Member' };
</script>

<div class="flex flex-col gap-3">
	<div class="text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500 px-1">Teams</div>

	<div class="relative">
		<span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"><Icon name="search" size={15} /></span>
		<input
			class="w-full text-sm ps-9 pe-3 py-2.5 rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 outline-none focus:border-gray-300 dark:focus:border-gray-700 placeholder:text-gray-400"
			placeholder="Search teams..."
			bind:value={query}
		/>
	</div>

	<div class="flex flex-col gap-2">
		{#each visible as r (r.team.id)}
			{@const restricted = r.workspaces.filter((w) => w.visibility === 'restricted').length}
			<button
				class="w-full text-left rounded-xl p-3 border transition
					{selectedId === r.team.id
					? 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800 shadow-sm ring-1 ring-brand-500/40 border-l-[3px] border-l-brand-600 dark:border-l-brand-500'
					: 'bg-white/60 dark:bg-gray-900/40 border-gray-200/70 dark:border-gray-800/70 hover:bg-white dark:hover:bg-gray-900'}"
				onclick={() => onSelect(r.team.id)}
			>
				<div class="flex items-center gap-2.5">
					<span class="flex-none size-8 rounded-lg flex items-center justify-center text-xs font-semibold bg-brand-900 text-white dark:bg-brand-800">
						{(r.team.key || r.team.name).trim().slice(0, 1).toUpperCase()}
					</span>
					<span class="flex-1 min-w-0 text-sm font-medium truncate {r.team.archived ? 'text-gray-400 dark:text-gray-500' : ''}">{r.team.name}</span>
					{#if restricted}
						<span class="flex-none inline-flex items-center gap-0.5 text-[11px] text-amber-600 dark:text-amber-400"><Icon name="lock" size={11} />{restricted}</span>
					{/if}
				</div>
				<div class="mt-2 flex items-center gap-2 text-[11px] text-gray-500 dark:text-gray-400">
					<span class="px-1.5 py-0.5 rounded-md {r.my_role === 'owner' ? 'bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300' : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'} font-medium">{ROLE_LABEL[r.my_role] ?? r.my_role}</span>
					<span>{r.member_count} member{r.member_count === 1 ? '' : 's'} · {r.workspaces.length} workspace{r.workspaces.length === 1 ? '' : 's'}</span>
					{#if r.team.archived}
						<span class="ms-auto px-1.5 py-0.5 rounded-full border border-gray-200 dark:border-gray-700 text-gray-400">archived</span>
					{/if}
				</div>
			</button>
		{:else}
			<div class="text-sm text-gray-400 px-2 py-4 text-center">No teams match.</div>
		{/each}
	</div>

	<button
		class="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-brand-900 hover:bg-brand-800 dark:bg-brand-800 dark:hover:bg-brand-700 text-white text-sm font-medium transition"
		onclick={() => openModal.set({ kind: 'team' })}
	>
		<Icon name="plus" size={16} /> New team
	</button>
</div>
