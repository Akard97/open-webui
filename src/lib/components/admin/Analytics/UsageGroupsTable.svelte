<script lang="ts">
	import { getContext } from 'svelte';
	import { adoptionPct } from '$lib/utils/usageStats';

	export let groups: {
		group_id: string;
		name: string;
		members: number;
		active_users: number;
		events: number;
		top_tool: string | null;
	}[] = [];
	export let onSelect: (groupId: string) => void = () => {};

	const i18n = getContext('i18n');
</script>

<div class="scrollbar-hidden relative whitespace-nowrap overflow-x-auto max-w-full">
	<table class="w-full text-sm text-left text-gray-500 dark:text-gray-400 table-auto">
		<thead class="text-xs text-gray-800 uppercase bg-transparent dark:text-gray-200">
			<tr class="border-b-[1.5px] border-gray-50 dark:border-gray-850/30">
				<th scope="col" class="px-2.5 py-2">{$i18n.t('Group')}</th>
				<th scope="col" class="px-2.5 py-2 text-right">{$i18n.t('Members')}</th>
				<th scope="col" class="px-2.5 py-2 text-right">{$i18n.t('Active Users')}</th>
				<th scope="col" class="px-2.5 py-2 text-right">{$i18n.t('Adoption')}</th>
				<th scope="col" class="px-2.5 py-2 text-right">{$i18n.t('Events')}</th>
				<th scope="col" class="px-2.5 py-2">{$i18n.t('Top Tool')}</th>
			</tr>
		</thead>
		<tbody>
			{#each groups as g (g.group_id)}
				<tr
					class="bg-white dark:bg-gray-900 dark:border-gray-850 text-xs cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
					on:click={() => onSelect(g.group_id)}
				>
					<td class="px-3 py-1 font-medium text-gray-900 dark:text-white truncate max-w-[150px]">
						{g.name}
					</td>
					<td class="px-3 py-1 text-right">{g.members.toLocaleString()}</td>
					<td class="px-3 py-1 text-right">{g.active_users.toLocaleString()}</td>
					<td class="px-3 py-1 text-right">{adoptionPct(g.active_users, g.members)}</td>
					<td class="px-3 py-1 text-right">{g.events.toLocaleString()}</td>
					<td class="px-3 py-1 capitalize">{g.top_tool ?? '—'}</td>
				</tr>
			{/each}
			{#if groups.length === 0}
				<tr>
					<td colspan="6" class="px-3 py-2 text-center text-gray-400">{$i18n.t('No data')}</td>
				</tr>
			{/if}
		</tbody>
	</table>
</div>
