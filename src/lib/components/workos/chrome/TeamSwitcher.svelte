<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import AssigneeAvatars from '../views/AssigneeAvatars.svelte';
	import * as ContextMenu from '$lib/components/ui/context-menu';
	import { get } from 'svelte/store';
	import * as api from '../lib/api';
	import { user } from '$lib/stores';
	import { canManageMembers } from '../lib/roles';
	import { teams, roles, currentTeam, currentTeamId, selectTeam, openModal, token } from '../lib/store';

	let teamMenuOpen = false;
	let teamMenuEl: HTMLElement;
	let memberIds: string[] = [];

	// Close the team switcher when clicking anywhere outside its container.
	function onWindowClick(e: MouseEvent): void {
		if (teamMenuOpen && teamMenuEl && !teamMenuEl.contains(e.target as Node)) teamMenuOpen = false;
	}

	$: myRole = $currentTeamId ? $roles[$currentTeamId] : undefined;
	// App-admins pass every server gate; the roles map may have no entry for them.
	$: canManage = $user?.role === 'admin' || canManageMembers(myRole);

	// Two-letter team mark (prefer the short key).
	$: teamBadge = (($currentTeam?.key || $currentTeam?.name || '?').trim().slice(0, 2)).toUpperCase();

	// Load the active team's roster so the switcher card can show its members.
	$: void loadMembers($currentTeamId);
	async function loadMembers(id: string | null): Promise<void> {
		if (!id) { memberIds = []; return; }
		const ms = await api.listTeamMembers(token(), id).catch(() => []);
		if (get(currentTeamId) !== id) return; // a newer team switch won the race
		memberIds = ms.map((m) => m.user_id);
	}
</script>

<svelte:window onclick={onWindowClick} onkeydown={(e) => { if (e.key === 'Escape') teamMenuOpen = false; }} />

<div class="mt-4 px-[0.4375rem] relative text-gray-800 dark:text-gray-200" bind:this={teamMenuEl}>
	<div class="py-1.5 pl-2.5 text-xs font-medium text-gray-600 dark:text-gray-400">Team</div>
	<ContextMenu.Root>
		<ContextMenu.Trigger class="block w-full" disabled={!canManage}>
			<button
				class="group w-full flex flex-col gap-2.5 rounded-xl px-3 py-2.5 transition outline-none bg-gray-100 dark:bg-gray-900 ring-1 ring-black/5 dark:ring-white/10 hover:bg-gray-200 dark:hover:bg-gray-850"
				onclick={() => (teamMenuOpen = !teamMenuOpen)}
			>
				<div class="flex items-center gap-2.5 w-full">
					<span class="flex-none size-7 rounded-lg flex items-center justify-center text-[11px] font-semibold bg-brand-600 text-white dark:bg-brand-500 dark:text-brand-950">{teamBadge}</span>
					<span class="flex-1 min-w-0 text-left text-sm font-semibold truncate translate-y-[0.5px] text-gray-900 dark:text-white">{$currentTeam?.name ?? 'No team'}</span>
					<span class="text-gray-400 dark:text-gray-500 transition group-hover:text-gray-600 dark:group-hover:text-gray-300"><Icon name="chevrons-up-down" size={15} /></span>
				</div>
				{#if memberIds.length}
					<div class="flex items-center gap-2 pl-0.5">
						<AssigneeAvatars ids={memberIds} max={4} size={20} />
						<span class="text-[11px] font-medium text-gray-500 dark:text-gray-400">{memberIds.length} member{memberIds.length === 1 ? '' : 's'}</span>
					</div>
				{/if}
			</button>
		</ContextMenu.Trigger>
		{#if canManage && $currentTeamId}
			<ContextMenu.Content class="w-52">
				<ContextMenu.Item onSelect={() => openModal.set({ kind: 'team-settings', teamId: $currentTeamId })}>
					<span class="inline-flex items-center gap-2"><Icon name="settings" size={14} /> Team settings…</span>
				</ContextMenu.Item>
			</ContextMenu.Content>
		{/if}
	</ContextMenu.Root>
	{#if teamMenuOpen}
		<div class="absolute left-[0.4375rem] right-[0.4375rem] mt-1 z-20 rounded-xl border border-gray-100 dark:border-gray-850 bg-white dark:bg-gray-900 shadow-lg p-1">
			{#each $teams as t (t.id)}
				<button
					class="flex items-center gap-2 w-full px-2.5 h-8 rounded-lg text-sm hover:bg-gray-100 dark:hover:bg-gray-850"
					onclick={() => { selectTeam(t.id); teamMenuOpen = false; }}
				>
					<span class="flex-1 text-left truncate">{t.name}</span>
					{#if t.id === $currentTeamId}<Icon name="check" size={14} />{/if}
				</button>
			{/each}
			{#if canManage && $currentTeamId}
				<button class="flex items-center gap-2 w-full px-2.5 h-8 rounded-lg text-sm hover:bg-gray-100 dark:hover:bg-gray-850" onclick={() => { openModal.set({ kind: 'team-settings', teamId: $currentTeamId }); teamMenuOpen = false; }}>
					<Icon name="settings" size={14} /> Team settings…
				</button>
			{/if}
			<button
				class="flex items-center gap-2 w-full px-2.5 h-8 rounded-lg text-sm text-primary hover:bg-gray-100 dark:hover:bg-gray-850"
				onclick={() => { openModal.set({ kind: 'team' }); teamMenuOpen = false; }}
			>
				<Icon name="plus" size={14} /> New team
			</button>
		</div>
	{/if}
</div>
