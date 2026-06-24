<script lang="ts">
	import { onMount } from 'svelte';
	import * as api from '../../lib/api';
	import { token } from '../../lib/store';
	import type { WorkosRules } from '../../lib/types';

	let rules: WorkosRules = { team_creation: 'all_users', default_workspace_visibility: 'team' };
	let toast = '';

	onMount(async () => {
		rules = await api.getAdminSettings(token()).catch(() => rules);
	});

	async function save() {
		rules = await api.updateAdminSettings(token(), rules);
		toast = 'Saved';
		setTimeout(() => (toast = ''), 2000);
	}
</script>

<div class="space-y-4 max-w-md">
	<div>
		<label class="text-sm font-medium" for="tc">Who can create teams</label>
		<select id="tc" class="mt-1 w-full text-sm border border-gray-200 dark:border-gray-700 rounded px-2 py-1.5 bg-transparent" bind:value={rules.team_creation}>
			<option value="all_users">All WorkOS users</option>
			<option value="admins_only">Admins only</option>
		</select>
	</div>
	<div>
		<label class="text-sm font-medium" for="vis">Default workspace visibility</label>
		<select id="vis" class="mt-1 w-full text-sm border border-gray-200 dark:border-gray-700 rounded px-2 py-1.5 bg-transparent" bind:value={rules.default_workspace_visibility}>
			<option value="team">Team</option>
			<option value="restricted">Restricted</option>
		</select>
	</div>
	<div class="pt-2 border-t border-gray-200 dark:border-gray-800">
		<div class="text-sm font-medium mb-1">Fixed sets (Phase 1)</div>
		<div class="text-xs text-gray-500">Statuses: Backlog, Todo, In Progress, In Review, Done, Canceled.</div>
		<div class="text-xs text-gray-500">Priorities: Urgent, High, Medium, Low.</div>
	</div>
	<div class="pt-2 border-t border-gray-200 dark:border-gray-800">
		<div class="text-sm font-medium mb-2">Notifications</div>
		{#each ['assigned', 'mentioned', 'commented', 'status_changed'] as cat (cat)}
			<label class="flex items-center gap-2 h-8 text-sm">
				<input
					type="checkbox"
					checked={rules.notifications?.[cat] !== false}
					onchange={(e) => {
						rules.notifications = { ...(rules.notifications ?? {}), [cat]: (e.target as HTMLInputElement).checked };
					}}
				/>
				<span class="capitalize">{cat.replace('_', ' ')}</span>
			</label>
		{/each}
	</div>
	<div>
		<div class="text-sm font-medium mb-1">Max attachment size (MB)</div>
		<input
			type="number"
			min="0"
			class="text-sm bg-transparent border border-gray-200 dark:border-gray-700 rounded px-2 py-1 w-24"
			value={rules.max_attachment_mb ?? 25}
			onchange={(e) => { rules.max_attachment_mb = parseInt((e.target as HTMLInputElement).value, 10) || 0; }}
		/>
	</div>
	<div class="flex items-center gap-3">
		<button class="text-sm px-3 py-1.5 rounded bg-teal-600 text-white" onclick={save}>Save</button>
		{#if toast}<span class="text-sm text-green-600">{toast}</span>{/if}
	</div>
</div>
