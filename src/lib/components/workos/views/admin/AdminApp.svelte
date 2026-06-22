<script lang="ts">
	import AccessTab from './AccessTab.svelte';
	import TeamsTab from './TeamsTab.svelte';
	import RulesTab from './RulesTab.svelte';
	import { view } from '../../lib/store';

	type Tab = 'teams' | 'rules' | 'access';
	let tab: Tab = 'teams';
	const TABS: { id: Tab; label: string }[] = [
		{ id: 'teams', label: 'Teams' },
		{ id: 'rules', label: 'Rules & defaults' },
		{ id: 'access', label: 'Access' }
	];
</script>

<div class="max-w-3xl mx-auto px-6 py-6">
	<div class="flex items-end justify-between mb-4">
		<div>
			<div class="text-[11px] uppercase tracking-wide text-gray-400">WorkOS · Admin</div>
			<h1 class="text-xl font-semibold mt-1">Administration</h1>
		</div>
		<button class="text-sm text-gray-500" onclick={() => view.set('board')}>← Back to board</button>
	</div>
	<nav class="flex gap-1 border-b border-gray-200 dark:border-gray-800 mb-5">
		{#each TABS as t (t.id)}
			<button class="px-3 py-2 text-sm border-b-2 {tab === t.id ? 'border-teal-500 font-medium' : 'border-transparent text-gray-500'}" onclick={() => (tab = t.id)}>{t.label}</button>
		{/each}
	</nav>
	{#if tab === 'teams'}<TeamsTab />{:else if tab === 'rules'}<RulesTab />{:else}<AccessTab />{/if}
</div>
