<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import * as api from '../../lib/api';
	import { token } from '../../lib/store';
	import type { WorkosRules } from '../../lib/types';
	import { Button } from '$lib/components/ui/button';
	import { Input } from '$lib/components/ui/input';
	import { Checkbox } from '$lib/components/ui/checkbox';
	import * as Select from '$lib/components/ui/select';

	let rules: WorkosRules = { team_creation: 'all_users', default_workspace_visibility: 'team' };
	let loading = true;

	const TEAM_CREATION_LABEL: Record<string, string> = {
		all_users: 'All WorkOS users',
		admins_only: 'Admins only'
	};
	const VISIBILITY_LABEL: Record<string, string> = { team: 'Team', restricted: 'Restricted' };

	onMount(async () => {
		loading = true;
		try {
			rules = await api.getAdminSettings(token());
		} catch {
			toast.error('Failed to load rules. Showing defaults.');
		} finally {
			loading = false;
		}
	});

	async function save() {
		try {
			rules = await api.updateAdminSettings(token(), rules);
			toast.success('Saved');
		} catch {
			toast.error('Failed to save rules.');
		}
	}
</script>

{#if loading}
	<div class="text-sm text-gray-400">Loading…</div>
{:else}
<div class="space-y-4 max-w-md">
	<div>
		<label class="text-sm font-medium" for="tc">Who can create teams</label>
		<Select.Root type="single" bind:value={rules.team_creation}>
			<Select.Trigger id="tc" class="mt-1 w-full">{TEAM_CREATION_LABEL[rules.team_creation]}</Select.Trigger>
			<Select.Content>
				<Select.Item value="all_users" label="All WorkOS users" />
				<Select.Item value="admins_only" label="Admins only" />
			</Select.Content>
		</Select.Root>
	</div>
	<div>
		<label class="text-sm font-medium" for="vis">Default workspace visibility</label>
		<Select.Root type="single" bind:value={rules.default_workspace_visibility}>
			<Select.Trigger id="vis" class="mt-1 w-full">{VISIBILITY_LABEL[rules.default_workspace_visibility]}</Select.Trigger>
			<Select.Content>
				<Select.Item value="team" label="Team" />
				<Select.Item value="restricted" label="Restricted" />
			</Select.Content>
		</Select.Root>
	</div>
	<div class="pt-2 border-t border-gray-200 dark:border-gray-800">
		<div class="text-sm font-medium mb-1">Fixed sets (Phase 1)</div>
		<div class="text-xs text-gray-500">Statuses: Backlog, Todo, In Progress, In Review, Done, Canceled.</div>
		<div class="text-xs text-gray-500">Priorities: Urgent, High, Medium, Low.</div>
	</div>
	<div class="pt-2 border-t border-gray-200 dark:border-gray-800">
		<div class="text-sm font-medium mb-2">Notifications</div>
		{#each ['assigned', 'mentioned', 'replied', 'commented', 'status_changed'] as cat (cat)}
			<label class="flex items-center gap-2 h-8 text-sm">
				<Checkbox
					checked={rules.notifications?.[cat] !== false}
					onCheckedChange={(v) => {
						rules.notifications = { ...(rules.notifications ?? {}), [cat]: !!v };
					}}
					class="size-4"
				/>
				<span class="capitalize">{cat.replace('_', ' ')}</span>
			</label>
		{/each}
	</div>
	<div>
		<div class="text-sm font-medium mb-1">Max attachment size (MB)</div>
		<Input
			type="number"
			min="0"
			class="w-24"
			value={rules.max_attachment_mb ?? 25}
			onchange={(e) => { rules.max_attachment_mb = parseInt((e.target as HTMLInputElement).value, 10) || 0; }}
		/>
	</div>
	<div class="flex items-center gap-3">
		<Button size="sm" onclick={save}>Save</Button>
	</div>
</div>
{/if}
