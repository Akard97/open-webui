<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import ThemeSwitcher from '$lib/components/app/ThemeSwitcher.svelte';
	import { user } from '$lib/stores';
	import { canUseAdmin, canCreateWorkspace, canManageMembers } from '../lib/roles';
	import {
		teams, workspaces, workstreams, roles, currentTeam, currentTeamId, currentWorkstreamId,
		selectTeam, selectWorkstream, view, openModal, unreadCount
	} from '../lib/store';

	let teamMenuOpen = false;
	let expanded: Record<string, boolean> = {};

	$: teamWorkspaces = $workspaces.filter((w) => w.team_id === $currentTeamId);
	$: streamsByWs = (wsId: string) => $workstreams.filter((s) => s.workspace_id === wsId);
	$: myRole = $currentTeamId ? $roles[$currentTeamId] : undefined;
</script>

<aside class="w-64 flex-none h-full flex flex-col border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
	<!-- Team switcher -->
	<div class="p-2.5 relative">
		<button
			class="flex items-center gap-2 w-full h-10 px-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-900"
			onclick={() => (teamMenuOpen = !teamMenuOpen)}
		>
			<div class="flex-1 text-left min-w-0">
				<div class="text-sm font-semibold truncate">{$currentTeam?.name ?? 'No team'}</div>
				<div class="text-[11px] text-gray-400">{$currentTeam?.key ?? ''}</div>
			</div>
			<Icon name="chevrons-up-down" size={15} />
		</button>
		{#if teamMenuOpen}
			<div class="absolute left-2.5 right-2.5 mt-1 z-20 rounded-lg border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shadow-lg p-1">
				{#each $teams as t (t.id)}
					<button
						class="flex items-center gap-2 w-full px-2 h-8 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-800"
						onclick={() => { selectTeam(t.id); teamMenuOpen = false; }}
					>
						<span class="flex-1 text-left truncate">{t.name}</span>
						{#if t.id === $currentTeamId}<Icon name="check" size={14} />{/if}
					</button>
				{/each}
				{#if canManageMembers(myRole) && $currentTeamId}
					<button class="flex items-center gap-2 w-full px-2 h-8 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-800" onclick={() => { openModal.set({ kind: 'members', teamId: $currentTeamId }); teamMenuOpen = false; }}>
						<Icon name="users" size={14} /> Manage members
					</button>
				{/if}
				<button
					class="flex items-center gap-2 w-full px-2 h-8 rounded text-sm text-teal-600 hover:bg-gray-100 dark:hover:bg-gray-800"
					onclick={() => { openModal.set({ kind: 'team' }); teamMenuOpen = false; }}
				>
					<Icon name="plus" size={14} /> New team
				</button>
			</div>
		{/if}
	</div>

	<!-- Workspaces -->
	<div class="flex-1 overflow-y-auto px-2 pb-2">
		<button
			class="flex items-center gap-2 w-full h-8 px-2 mb-1 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-900"
			class:bg-teal-50={$view === 'inbox'}
			onclick={() => view.set('inbox')}
		>
			<Icon name="message-square" size={15} />
			<span class="flex-1 text-left">Inbox</span>
			{#if $unreadCount > 0}
				<span class="text-[11px] min-w-5 h-5 px-1.5 rounded-full bg-teal-600 text-white flex items-center justify-center">{$unreadCount}</span>
			{/if}
		</button>
		<div class="flex items-center justify-between px-2 py-1.5">
			<span class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold">Workspaces</span>
			{#if canCreateWorkspace(myRole) && $currentTeamId}
				<button class="text-gray-400 hover:text-gray-600" onclick={() => openModal.set({ kind: 'workspace', teamId: $currentTeamId })}>
					<Icon name="plus" size={14} />
				</button>
			{/if}
		</div>
		{#each teamWorkspaces as ws (ws.id)}
			<div>
				<button
					class="flex items-center gap-1.5 w-full h-8 px-2 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-900"
					onclick={() => (expanded[ws.id] = !expanded[ws.id])}
				>
					<Icon name={expanded[ws.id] ? 'chevron-down' : 'chevron-right'} size={14} />
					<span class="flex-1 text-left truncate">{ws.name}</span>
				</button>
				{#if expanded[ws.id]}
					{#each streamsByWs(ws.id) as s (s.id)}
						<button
							class="flex items-center gap-2 w-full h-8 pl-8 pr-2 rounded text-sm hover:bg-gray-100 dark:hover:bg-gray-900"
							class:bg-teal-50={$currentWorkstreamId === s.id}
							onclick={() => { selectWorkstream(s.id); view.set('board'); }}
						>
							<span class="w-1.5 h-1.5 rounded-sm bg-teal-500 flex-none"></span>
							<span class="flex-1 text-left truncate">{s.name}</span>
						</button>
					{/each}
					{#if canCreateWorkspace(myRole)}
						<button
							class="flex items-center gap-2 w-full h-7 pl-8 pr-2 rounded text-xs text-gray-400 hover:text-gray-600"
							onclick={() => openModal.set({ kind: 'workstream', workspaceId: ws.id })}
						>
							<Icon name="plus" size={12} /> New workstream
						</button>
					{/if}
				{/if}
			</div>
		{/each}
	</div>

	<!-- Footer -->
	<div class="border-t border-gray-200 dark:border-gray-800 p-2 flex items-center gap-2">
		<div class="flex-1 min-w-0 text-sm font-medium truncate">{$user?.name ?? ''}</div>
		{#if canUseAdmin($user)}
			<button class="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-900" title="WorkOS admin" onclick={() => view.set('admin')}>
				<Icon name="settings" size={16} />
			</button>
		{/if}
		<ThemeSwitcher />
	</div>
</aside>
