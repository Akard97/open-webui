<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import SidebarIcon from '$lib/components/icons/Sidebar.svelte';
	import ThemeSwitcher from '$lib/components/app/ThemeSwitcher.svelte';
	import AssigneeAvatars from '../views/AssigneeAvatars.svelte';
	import { get } from 'svelte/store';
	import * as api from '../lib/api';
	import { user } from '$lib/stores';
	// Bundle the logo as a hashed build asset instead of loading it from the
	// backend's /static dir, which gets wiped when the backend image is rebuilt.
	import workosLogoDark from '../assets/workos-logo-dark.png';
	import workosLogoLight from '../assets/workos-logo-light.png';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import * as ContextMenu from '$lib/components/ui/context-menu';
	import RestrictConfirmDialog from './access/RestrictConfirmDialog.svelte';
	import { toast } from 'svelte-sonner';
	import { canUseAdmin, canCreateWorkspace, canManageMembers } from '../lib/roles';
	import type { Workspace } from '../lib/types';
	import {
		teams, workspaces, workstreams, roles, currentTeam, currentTeamId, currentWorkstreamId,
		selectTeam, selectWorkstream, view, openModal, unreadCount, navCollapsed, token, loadBootstrap
	} from '../lib/store';

	let teamMenuOpen = false;
	let teamMenuEl: HTMLElement;
	let expanded: Record<string, boolean> = {};
	let memberIds: string[] = [];

	// Close the team switcher when clicking anywhere outside its container.
	function onWindowClick(e: MouseEvent): void {
		if (teamMenuOpen && teamMenuEl && !teamMenuEl.contains(e.target as Node)) teamMenuOpen = false;
	}

	$: teamWorkspaces = $workspaces.filter((w) => w.team_id === $currentTeamId);
	$: streamsByWs = (wsId: string) => $workstreams.filter((s) => s.workspace_id === wsId);
	$: myRole = $currentTeamId ? $roles[$currentTeamId] : undefined;

	// App-admins pass every server gate; the roles map may have no entry for them.
	$: canManage = $user?.role === 'admin' || canManageMembers(myRole);

	let pendingRestrict: Workspace | null = null;

	async function makeTeamVisible(ws: Workspace): Promise<void> {
		try {
			await api.updateWorkspace(token(), ws.id, { visibility: 'team' });
			await loadBootstrap();
		} catch (e: any) {
			toast.error(typeof e === 'string' ? e : (e?.detail ?? 'Could not change visibility.'));
		}
	}

	async function restrictWorkspace(ws: Workspace): Promise<void> {
		try {
			await api.updateWorkspace(token(), ws.id, { visibility: 'restricted' });
			await loadBootstrap();
		} catch (e: any) {
			toast.error(typeof e === 'string' ? e : (e?.detail ?? 'Could not change visibility.'));
		} finally {
			pendingRestrict = null;
		}
	}

	// One action list feeds both the kebab dropdown and the right-click menu.
	type WsAction = { icon: string; label: string; sep?: boolean; run?: () => void };
	function wsActions(ws: Workspace): WsAction[] {
		return [
			{ icon: 'settings', label: 'Workspace settings…', run: () => openModal.set({ kind: 'workspace-settings', workspaceId: ws.id }) },
			{ icon: 'plus', label: 'New workstream', run: () => openModal.set({ kind: 'workstream', workspaceId: ws.id }) },
			{ icon: '', label: '', sep: true },
			ws.visibility === 'restricted'
				? { icon: 'eye', label: 'Make team-visible', run: () => void makeTeamVisible(ws) }
				: { icon: 'lock', label: 'Restrict workspace…', run: () => (pendingRestrict = ws) }
		];
	}

	// Two-letter team mark for the collapsed rail (prefer the short key).
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

{#if $navCollapsed}
	<!-- Collapsed: icon rail -->
	<aside
		class="w-14 flex-none h-full flex flex-col items-center gap-0.5 pt-2 pb-2 px-2 bg-gray-50 dark:bg-gray-950 border-e-[0.5px] border-gray-50 dark:border-gray-850/30 text-gray-600 dark:text-gray-400"
	>
		<!-- Logo / expand -->
		<button
			class="group size-9 rounded-xl flex items-center justify-center hover:bg-gray-100 dark:hover:bg-gray-850 transition"
			title="Expand sidebar"
			onclick={() => navCollapsed.set(false)}
		>
			<img src={workosLogoDark} class="size-7 object-contain group-hover:hidden block dark:hidden" alt="WorkOS" />
			<img src={workosLogoLight} class="size-7 object-contain group-hover:hidden hidden dark:block" alt="WorkOS" />
			<SidebarIcon className="size-5 hidden group-hover:flex" />
		</button>

		<button
			class="size-9 rounded-xl flex items-center justify-center hover:bg-gray-100 dark:hover:bg-gray-850 transition {$view === 'mywork' ? 'bg-gray-100 dark:bg-gray-850 text-gray-900 dark:text-white' : ''}"
			title="My Work"
			onclick={() => view.set('mywork')}
		>
			<Icon name="check" size={18} />
		</button>

		<button
			class="relative size-9 rounded-xl flex items-center justify-center hover:bg-gray-100 dark:hover:bg-gray-850 transition {$view === 'inbox' ? 'bg-gray-100 dark:bg-gray-850 text-gray-900 dark:text-white' : ''}"
			title="Inbox"
			onclick={() => view.set('inbox')}
		>
			<Icon name="message-square" size={18} />
			{#if $unreadCount > 0}
				<span class="absolute top-1 right-1 size-1.5 rounded-full bg-sky-500"></span>
			{/if}
		</button>

		<!-- Current team (click to expand and switch) -->
		<button
			class="size-9 rounded-xl flex items-center justify-center text-[11px] font-semibold bg-brand-600 text-white transition hover:bg-brand-700 dark:bg-brand-500 dark:text-brand-950 dark:hover:bg-brand-400"
			title={$currentTeam?.name ?? 'Team'}
			onclick={() => navCollapsed.set(false)}
		>
			{teamBadge}
		</button>

		<div class="flex-1"></div>

		{#if canUseAdmin($user)}
			<button class="size-9 rounded-xl flex items-center justify-center hover:bg-gray-100 dark:hover:bg-gray-850 transition" title="WorkOS admin" onclick={() => view.set('admin')}>
				<Icon name="settings" size={18} />
			</button>
		{/if}
		<ThemeSwitcher />
	</aside>
{:else}
	<aside class="w-64 flex-none h-full flex flex-col bg-gray-50 dark:bg-gray-950 border-e-[0.5px] border-gray-50 dark:border-gray-850/30">
		<!-- Header: mark + name + collapse -->
		<div class="px-[0.5625rem] pt-2 pb-1.5 flex justify-between space-x-1 text-gray-600 dark:text-gray-400">
			<div class="flex items-center size-8.5 justify-center">
				<img src={workosLogoDark} class="size-7 object-contain block dark:hidden" alt="WorkOS" />
				<img src={workosLogoLight} class="size-7 object-contain hidden dark:block" alt="WorkOS" />
			</div>
			<div class="flex flex-1 items-center px-0.5">
				<div class="self-center font-medium text-gray-850 dark:text-white font-primary">WorkOS</div>
			</div>
			<button
				class="flex rounded-xl size-8.5 justify-center items-center hover:bg-gray-100/50 dark:hover:bg-gray-850/50 transition"
				title="Collapse sidebar"
				onclick={() => navCollapsed.set(true)}
			>
				<div class="self-center p-1.5"><SidebarIcon /></div>
			</button>
		</div>

		<!-- My Work + Inbox -->
		<div class="text-gray-800 dark:text-gray-200">
			<div class="px-[0.4375rem] flex justify-center">
				<button
					class="group grow flex items-center space-x-3 rounded-xl px-2.5 py-2 hover:bg-gray-100 dark:hover:bg-gray-900 transition outline-none {$view === 'mywork' ? 'bg-gray-100 dark:bg-gray-900' : ''}"
					onclick={() => view.set('mywork')}
				>
					<div class="self-center"><Icon name="check" size={18} /></div>
					<div class="flex flex-1 self-center translate-y-[0.5px]">
						<div class="self-center text-sm font-primary {$view === 'mywork' ? 'font-medium' : ''}">My Work</div>
					</div>
				</button>
			</div>
			<div class="px-[0.4375rem] flex justify-center">
				<button
					class="group grow flex items-center space-x-3 rounded-xl px-2.5 py-2 hover:bg-gray-100 dark:hover:bg-gray-900 transition outline-none {$view === 'inbox' ? 'bg-gray-100 dark:bg-gray-900' : ''}"
					onclick={() => view.set('inbox')}
				>
					<div class="self-center"><Icon name="message-square" size={18} /></div>
					<div class="flex flex-1 self-center translate-y-[0.5px]">
						<div class="self-center text-sm font-primary {$view === 'inbox' ? 'font-medium' : ''}">Inbox</div>
					</div>
					{#if $unreadCount > 0}
						<span class="shrink-0 self-center text-[10px] min-w-4 h-4 px-1 rounded-full bg-sky-500 text-white flex items-center justify-center">{$unreadCount}</span>
					{/if}
				</button>
			</div>
		</div>

		<!-- Teams (directly above Workspaces) -->
		<div class="mt-1 px-[0.4375rem] relative text-gray-800 dark:text-gray-200" bind:this={teamMenuEl}>
			<div class="py-1.5 pl-2.5 text-xs font-medium text-gray-600 dark:text-gray-400">Team</div>
			<ContextMenu.Root>
				<ContextMenu.Trigger class="block w-full">
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

		<!-- Workspaces -->
		<div class="flex-1 overflow-y-auto scrollbar-hidden px-2 mt-1 pb-2">
			<div class="group w-full rounded-xl flex items-center justify-between hover:bg-gray-100 dark:hover:bg-gray-900 transition text-gray-600 dark:text-gray-400">
				<div class="w-full py-1.5 pl-2 flex items-center gap-1.5 text-xs font-medium">
					<div class="translate-y-[0.5px] pl-0.5">Workspaces</div>
				</div>
				{#if canCreateWorkspace(myRole) && $currentTeamId}
					<button class="z-10 mr-2 invisible group-hover:visible self-center p-0.5 hover:bg-gray-200 dark:hover:bg-gray-850 rounded-lg transition" title="New workspace" onclick={() => openModal.set({ kind: 'workspace', teamId: $currentTeamId })}>
						<Icon name="plus" size={12} strokeWidth={2.5} />
					</button>
				{/if}
			</div>
			{#each teamWorkspaces as ws (ws.id)}
				<ContextMenu.Root>
					<ContextMenu.Trigger class="block w-full">
						<div class="text-gray-800 dark:text-gray-200">
							<div class="group/ws w-full flex items-center rounded-xl hover:bg-gray-100 dark:hover:bg-gray-900 transition">
								<button
									class="flex-1 min-w-0 flex items-center gap-1.5 px-[11px] py-[6px] text-sm"
									onclick={() => (expanded[ws.id] = !expanded[ws.id])}
								>
									<Icon name={expanded[ws.id] ? 'chevron-down' : 'chevron-right'} size={12} />
									<span class="flex-1 text-left truncate">{ws.name}</span>
									{#if ws.visibility === 'restricted'}
										<span class="text-gray-400 dark:text-gray-500 flex-none" title="Restricted workspace"><Icon name="lock" size={12} /></span>
									{/if}
								</button>
								{#if canManage}
									<DropdownMenu.Root>
										<DropdownMenu.Trigger
											class="mr-1.5 p-1 rounded-lg text-gray-500 dark:text-gray-400 opacity-0 group-hover/ws:opacity-100 data-[state=open]:opacity-100 hover:bg-gray-200 dark:hover:bg-gray-850 transition"
											title="Workspace actions"
										>
											<Icon name="more-horizontal" size={14} />
										</DropdownMenu.Trigger>
										<DropdownMenu.Content align="start" class="w-52">
											{#each wsActions(ws) as a, i (i)}
												{#if a.sep}
													<DropdownMenu.Separator />
												{:else}
													<DropdownMenu.Item onSelect={a.run}>
														<span class="inline-flex items-center gap-2"><Icon name={a.icon} size={14} /> {a.label}</span>
													</DropdownMenu.Item>
												{/if}
											{/each}
										</DropdownMenu.Content>
									</DropdownMenu.Root>
								{/if}
							</div>
							{#if expanded[ws.id]}
								{#each streamsByWs(ws.id) as s (s.id)}
									<button
										class="w-full flex items-center gap-2 rounded-xl pl-7 pr-[11px] py-[6px] text-sm transition {$currentWorkstreamId === s.id ? 'bg-gray-100 dark:bg-gray-900 font-medium' : 'hover:bg-gray-100 dark:hover:bg-gray-900'}"
										onclick={() => { selectWorkstream(s.id); view.set('board'); }}
									>
										<span class="size-1.5 rounded-full bg-gray-400 dark:bg-gray-600 flex-none"></span>
										<span class="flex-1 text-left truncate">{s.name}</span>
									</button>
								{/each}
								{#if canCreateWorkspace(myRole)}
									<button
										class="w-full flex items-center gap-2 rounded-xl pl-7 pr-[11px] py-1.5 text-xs text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-900 transition"
										onclick={() => openModal.set({ kind: 'workstream', workspaceId: ws.id })}
									>
										<Icon name="plus" size={12} /> New workstream
									</button>
								{/if}
							{/if}
						</div>
					</ContextMenu.Trigger>
					{#if canManage}
						<ContextMenu.Content class="w-52">
							{#each wsActions(ws) as a, i (i)}
								{#if a.sep}
									<ContextMenu.Separator />
								{:else}
									<ContextMenu.Item onSelect={a.run}>
										<span class="inline-flex items-center gap-2"><Icon name={a.icon} size={14} /> {a.label}</span>
									</ContextMenu.Item>
								{/if}
							{/each}
						</ContextMenu.Content>
					{/if}
				</ContextMenu.Root>
			{/each}
		</div>

		<!-- Footer -->
		<div class="border-t border-gray-50 dark:border-gray-850/30 p-2 flex items-center gap-2 text-gray-800 dark:text-gray-200">
			<div class="flex-1 min-w-0 text-sm font-medium truncate">{$user?.name ?? ''}</div>
			{#if canUseAdmin($user)}
				<button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition" title="WorkOS admin" onclick={() => view.set('admin')}>
					<Icon name="settings" size={16} />
				</button>
			{/if}
			<ThemeSwitcher />
		</div>
	</aside>
{/if}

<RestrictConfirmDialog
	open={pendingRestrict !== null}
	name={pendingRestrict?.name ?? ''}
	busy={false}
	onCancel={() => (pendingRestrict = null)}
	onConfirm={() => pendingRestrict && void restrictWorkspace(pendingRestrict)}
/>
