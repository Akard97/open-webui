<script lang="ts">
	import { onMount } from 'svelte';
	import * as api from '../../lib/api';
	import { token, directory } from '../../lib/store';

	let rows: { team: any; owner_ids: string[]; member_count: number }[] = [];
	let loading = true;

	async function load() {
		rows = await api.adminListTeams(token()).catch(() => []);
		loading = false;
	}
	onMount(load);

	async function archive(id: string) {
		await api.updateTeam(token(), id, { archived: true }).catch(() => {});
		await load();
	}
	async function del(id: string) {
		if (!confirm('Delete this team and everything in it?')) return;
		await api.deleteTeam(token(), id).catch(() => {});
		await load();
	}
</script>

{#if loading}
	<div class="text-sm text-gray-400">Loading…</div>
{:else}
	<div class="overflow-x-auto">
		<table class="w-full text-sm">
			<thead class="text-xs text-gray-400 text-left">
				<tr><th class="py-2">Team</th><th>Key</th><th>Owners</th><th>Members</th><th></th></tr>
			</thead>
			<tbody>
				{#each rows as r (r.team.id)}
					<tr class="border-t border-gray-100 dark:border-gray-800">
						<td class="py-2">{r.team.name}{r.team.archived ? ' (archived)' : ''}</td>
						<td class="font-mono text-xs">{r.team.key}</td>
						<td class="text-xs">{r.owner_ids.map((id) => $directory[id]?.name ?? id).join(', ')}</td>
						<td>{r.member_count}</td>
						<td class="text-right">
							<button class="text-xs text-gray-500 mr-2" onclick={() => archive(r.team.id)}>Archive</button>
							<button class="text-xs text-red-500" onclick={() => del(r.team.id)}>Delete</button>
						</td>
					</tr>
				{/each}
			</tbody>
		</table>
	</div>
{/if}
