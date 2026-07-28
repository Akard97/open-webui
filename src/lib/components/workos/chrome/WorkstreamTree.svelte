<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import * as ContextMenu from '$lib/components/ui/context-menu';
	import RestrictConfirmDialog from './access/RestrictConfirmDialog.svelte';
	import { toast } from 'svelte-sonner';
	import * as api from '../lib/api';
	import { user } from '$lib/stores';
	import { canCreateWorkspace, canManageMembers } from '../lib/roles';
	import type { Workspace } from '../lib/types';
	import { WORKSTREAM_VIEWS } from '../lib/urlState';
	import {
		workspaces, workstreams, roles, currentTeamId, currentWorkstreamId,
		selectWorkstream, view, openModal, token, loadBootstrap, expandedWorkspaces
	} from '../lib/store';

	// Called after a workstream is picked — the mobile drawer closes itself here.
	export let onNavigate: () => void = () => {};

	$: teamWorkspaces = $workspaces.filter((w) => w.team_id === $currentTeamId);
	$: streamsByWs = (wsId: string) => $workstreams.filter((s) => s.workspace_id === wsId);
	// A workstream is "selected" in the tree only while a workstream-scoped view is
	// open. On My Work / Inbox / admin, `currentWorkstreamId` is still set (bootstrap
	// preselects the first stream), so gate the highlight to avoid a phantom selection.
	$: onStreamView = $view !== 'mywork' && $view !== 'inbox' && $view !== 'admin';
	$: myRole = $currentTeamId ? $roles[$currentTeamId] : undefined;
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
</script>

<div class="group w-full rounded-xl flex items-center justify-between hover:bg-gray-100 dark:hover:bg-gray-900 transition text-gray-600 dark:text-gray-400">
	<div class="w-full py-1.5 pl-2 flex items-center gap-1.5 text-xs font-medium">
		<div class="translate-y-[0.5px] pl-0.5">Workspaces</div>
	</div>
	{#if canCreateWorkspace(myRole) && $currentTeamId}
		<button class="z-10 mr-2 invisible group-hover:visible max-md:visible self-center p-0.5 hover:bg-gray-200 dark:hover:bg-gray-850 rounded-lg transition" title="New workspace" onclick={() => openModal.set({ kind: 'workspace', teamId: $currentTeamId })}>
			<Icon name="plus" size={12} strokeWidth={2.5} />
		</button>
	{/if}
</div>
{#each teamWorkspaces as ws (ws.id)}
	<ContextMenu.Root>
		<ContextMenu.Trigger class="block w-full" disabled={!canManage}>
			<div class="text-gray-800 dark:text-gray-200">
				<div class="group/ws w-full flex items-center rounded-xl hover:bg-gray-100 dark:hover:bg-gray-900 transition">
					<button
						class="flex-1 min-w-0 flex items-center gap-1.5 px-[11px] py-[6px] text-sm"
						onclick={() => expandedWorkspaces.update((m) => ({ ...m, [ws.id]: !m[ws.id] }))}
					>
						<Icon name={$expandedWorkspaces[ws.id] ? 'chevron-down' : 'chevron-right'} size={12} />
						<span class="flex-1 text-left truncate">{ws.name}</span>
						{#if ws.visibility === 'restricted'}
							<span class="text-gray-400 dark:text-gray-500 flex-none" title="Restricted workspace"><Icon name="lock" size={12} /></span>
						{/if}
					</button>
					{#if canManage}
						<DropdownMenu.Root>
							<DropdownMenu.Trigger
								class="mr-1.5 p-1 rounded-lg text-gray-500 dark:text-gray-400 opacity-0 group-hover/ws:opacity-100 max-md:opacity-100 data-[state=open]:opacity-100 hover:bg-gray-200 dark:hover:bg-gray-850 transition"
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
				{#if $expandedWorkspaces[ws.id]}
					<div class="ws-tree">
						{#each streamsByWs(ws.id) as s (s.id)}
							<button
								class="ws-tree-item w-full flex items-center rounded-lg pl-2 pr-[11px] py-[6px] text-sm transition {onStreamView && $currentWorkstreamId === s.id ? 'bg-gray-100 dark:bg-gray-900 font-medium' : 'hover:bg-gray-100 dark:hover:bg-gray-900'}"
								onclick={() => { selectWorkstream(s.id); if (!WORKSTREAM_VIEWS.has($view)) view.set('board'); onNavigate(); }}
							>
								<span class="flex-1 text-left truncate">{s.name}</span>
							</button>
						{/each}
						{#if canCreateWorkspace(myRole)}
							<button
								class="ws-tree-item w-full flex items-center gap-1.5 rounded-lg pl-2 pr-[11px] py-1.5 text-xs text-gray-400 dark:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-900 transition"
								onclick={() => openModal.set({ kind: 'workstream', workspaceId: ws.id })}
							>
								<Icon name="square-plus-dashed" size={16} /> New workstream
							</button>
						{/if}
					</div>
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

<RestrictConfirmDialog
	open={pendingRestrict !== null}
	name={pendingRestrict?.name ?? ''}
	busy={false}
	onCancel={() => (pendingRestrict = null)}
	onConfirm={() => pendingRestrict && void restrictWorkspace(pendingRestrict)}
/>

<style>
	/* File-explorer-style tree guides under a workspace. Item left edge sits at
	   22px, and the 2px line is centred at 17px — directly under the workspace
	   chevron's centre. */
	.ws-tree {
		margin-left: 0.5rem; /* 8px  */
		padding-left: 1.25rem; /* 20px -> item left edge at 28px */
	}
	.ws-tree-item {
		position: relative;
	}
	/* Per-item vertical segment: they stack into one continuous line, and the
	   last item stops at its own centre so the run terminates in an elbow. */
	.ws-tree-item::before {
		content: '';
		position: absolute;
		left: -11px; /* line at 17px — under the chevron centre */
		top: 0;
		bottom: 0;
		width: 1px;
		background: rgb(229 231 235); /* gray-200 */
	}
	.ws-tree-item:last-child::before {
		bottom: 50%;
	}
	/* Horizontal elbow from the vertical line to the item. */
	.ws-tree-item::after {
		content: '';
		position: absolute;
		left: -11px;
		top: 50%;
		width: 11px;
		height: 1px;
		background: rgb(229 231 235); /* gray-200 */
	}
	:global(.dark) .ws-tree-item::before,
	:global(.dark) .ws-tree-item::after {
		background: rgb(31 41 55); /* gray-800 */
	}
</style>
