<script lang="ts">
	import { toast } from 'svelte-sonner';
	import * as Dialog from '$lib/components/ui/dialog';
	import Icon from '../../ui/Icon.svelte';
	import WorkspaceMembersPanel from './WorkspaceMembersPanel.svelte';
	import * as api from '../../lib/api';
	import { token, openModal } from '../../lib/store';
	import type { AccessWorkspaceSummary, Member } from '../../lib/types';

	export let teamId: string;
	export let workspaces: AccessWorkspaceSummary[] = [];
	export let teamMembers: Member[] = [];
	export let allUsers: { id: string; name: string }[] = [];
	export let onChanged: () => Promise<void>;

	let expanded: Record<string, boolean> = {};
	let pendingRestrict: AccessWorkspaceSummary | null = null;
	let busy = false;

	function detail(e: any, fallback: string): string {
		return typeof e === 'string' ? e : (e?.detail ?? fallback);
	}

	async function setVisibility(ws: AccessWorkspaceSummary, visibility: 'team' | 'restricted'): Promise<void> {
		busy = true;
		try {
			await api.updateWorkspace(token(), ws.id, { visibility });
		} catch (e: any) {
			toast.error(detail(e, 'Could not change visibility.'));
		} finally {
			busy = false;
			pendingRestrict = null;
			await onChanged();
		}
	}

	function requestFlip(ws: AccessWorkspaceSummary): void {
		if (ws.visibility === 'team') {
			pendingRestrict = ws; // destructive: confirm before locking people out
		} else {
			void setVisibility(ws, 'team'); // opening up — no confirmation needed
		}
	}
</script>

<div class="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
	<div class="flex items-center gap-2 mb-4">
		<span class="text-gray-500 dark:text-gray-400"><Icon name="layers" size={17} /></span>
		<span class="text-[15px] font-semibold">Workspaces</span>
		<span class="text-xs font-medium text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 rounded-full min-w-5 h-5 px-1.5 inline-flex items-center justify-center">{workspaces.length}</span>
		<div class="flex-1"></div>
		<button
			class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 inline-flex items-center gap-1.5 hover:bg-gray-50 dark:hover:bg-gray-850 transition"
			onclick={() => openModal.set({ kind: 'workspace', teamId })}
		>
			<Icon name="plus" size={14} /> New workspace
		</button>
	</div>

	{#if !workspaces.length}
		<div class="py-3 text-sm text-gray-400">No workspaces yet.</div>
	{:else}
		<div class="flex flex-col gap-2">
			{#each workspaces as ws (ws.id)}
				<div class="rounded-xl border border-gray-200 dark:border-gray-800 px-3 py-2.5">
					<div class="flex items-center gap-3">
						<span class="size-9 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 flex items-center justify-center flex-none">
							<Icon name="layers" size={16} />
						</span>
						<div class="flex-1 min-w-0">
							<div class="text-sm font-medium truncate {ws.archived ? 'text-gray-400 line-through' : ''}">{ws.name}</div>
							<div class="mt-1 flex items-center gap-2 text-[12px]">
								{#if ws.visibility === 'restricted'}
									<span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md font-medium bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-300 border border-amber-200/60 dark:border-amber-900/40">
										<Icon name="lock" size={11} /> Restricted
									</span>
									<span class="text-gray-400 dark:text-gray-500">· {ws.member_count ?? 0} member{ws.member_count === 1 ? '' : 's'}</span>
								{:else}
									<span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md font-medium bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300">
										<Icon name="globe" size={11} /> Team-visible
									</span>
								{/if}
							</div>
						</div>

						{#if ws.visibility === 'restricted'}
							<button
								class="text-[13px] px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 inline-flex items-center gap-1.5 hover:bg-gray-50 dark:hover:bg-gray-850 transition disabled:opacity-50"
								disabled={busy}
								onclick={() => (expanded[ws.id] = !expanded[ws.id])}
							>
								<Icon name="users" size={13} /> {expanded[ws.id] ? 'Hide' : 'Members'}
							</button>
							<button
								class="text-[13px] px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 inline-flex items-center gap-1.5 hover:bg-gray-50 dark:hover:bg-gray-850 transition disabled:opacity-50"
								disabled={busy}
								title="Everyone on the team will be able to see this workspace"
								onclick={() => requestFlip(ws)}
							>
								<Icon name="eye" size={13} /> Make team-visible
							</button>
						{:else}
							<button
								class="text-[13px] px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 inline-flex items-center gap-1.5 hover:bg-gray-50 dark:hover:bg-gray-850 transition disabled:opacity-50"
								disabled={busy}
								onclick={() => requestFlip(ws)}
							>
								<Icon name="lock" size={13} /> Restrict
							</button>
						{/if}
					</div>
					{#if ws.visibility === 'restricted' && expanded[ws.id]}
						<div class="mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
							<WorkspaceMembersPanel workspaceId={ws.id} {teamMembers} {allUsers} {onChanged} />
						</div>
					{/if}
				</div>
			{/each}
		</div>
		<p class="mt-3 text-[12px] text-gray-400 dark:text-gray-500">
			Restricted workspaces you're not a member of aren't listed — their creator always keeps access.
		</p>
	{/if}
</div>

<Dialog.Root open={pendingRestrict !== null} onOpenChange={(o) => { if (!o) pendingRestrict = null; }}>
	<Dialog.Content class="max-w-md">
		<Dialog.Title>Restrict this workspace?</Dialog.Title>
		<Dialog.Description>
			<span class="font-medium">{pendingRestrict?.name}</span> will only be visible to its explicit
			members and its creator. Everyone else on the team loses access immediately — it disappears
			from their sidebar and any live sessions are disconnected from its rooms. You can add
			members back afterwards from this panel.
		</Dialog.Description>
		<div class="flex justify-end gap-2 mt-4">
			<button class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-850 transition" onclick={() => (pendingRestrict = null)}>Cancel</button>
			<button
				class="text-sm font-medium px-3.5 py-1.5 rounded-lg bg-amber-600 text-white hover:bg-amber-700 transition"
				disabled={busy}
				onclick={() => pendingRestrict && void setVisibility(pendingRestrict, 'restricted')}
			>
				Restrict workspace
			</button>
		</div>
	</Dialog.Content>
</Dialog.Root>
