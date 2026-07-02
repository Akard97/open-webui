<script lang="ts">
	import { toast } from 'svelte-sonner';
	import * as Dialog from '$lib/components/ui/dialog';
	import Icon from '../../ui/Icon.svelte';
	import MemberRoster from './MemberRoster.svelte';
	import WorkspacePanel from './WorkspacePanel.svelte';
	import * as api from '../../lib/api';
	import { token, reloadDirectory, directory, initials } from '../../lib/store';
	import { user } from '$lib/stores';
	import type { AccessTeamOverview, Member } from '../../lib/types';

	export let row: AccessTeamOverview;
	export let onOverviewChanged: () => Promise<void>;
	export let onTreeChanged: () => Promise<void>;

	// System admins pass every owner gate server-side (their team_role() is 'admin',
	// but require_team_role early-returns) — treat them as owners in the UI too.
	$: isOwner = $user?.role === 'admin' || row.my_role === 'owner';

	let members: Member[] = [];
	let allUsers: { id: string; name: string }[] = [];
	let rosterLoaded = false;

	$: void loadRoster(row.team.id);
	async function loadRoster(id: string): Promise<void> {
		rosterLoaded = false;
		const [ms, us] = await Promise.all([
			api.listTeamMembers(token(), id).catch(() => [] as Member[]),
			api.listAllUsers(token(), id).catch(() => [] as { id: string; name: string }[])
		]);
		if (row.team.id !== id) return; // a newer team selection won the race
		members = ms;
		allUsers = us;
		rosterLoaded = true;
	}

	async function rosterChanged(): Promise<void> {
		await loadRoster(row.team.id);
		await reloadDirectory();
		await onOverviewChanged();
	}

	$: nameOf = (id: string) => allUsers.find((u) => u.id === id)?.name ?? $directory[id]?.name ?? id;
	$: ownerId = row.owner_ids[0];
	$: ownerName = ownerId ? nameOf(ownerId) : '—';
	$: createdLabel = new Date(row.team.created_at).toLocaleDateString(undefined, {
		year: 'numeric', month: 'long', day: 'numeric'
	});

	// Rename (owner-only)
	let renaming = false;
	let nameDraft = '';
	function startRename(): void {
		nameDraft = row.team.name;
		renaming = true;
	}
	async function saveRename(): Promise<void> {
		const name = nameDraft.trim();
		renaming = false;
		if (!name || name === row.team.name) return;
		try {
			await api.updateTeam(token(), row.team.id, { name });
			await onTreeChanged();
		} catch (e: any) {
			toast.error(typeof e === 'string' ? e : (e?.detail ?? 'Could not rename team.'));
		}
	}

	async function toggleArchived(): Promise<void> {
		try {
			await api.updateTeam(token(), row.team.id, { archived: !row.team.archived });
			await onTreeChanged();
		} catch (e: any) {
			toast.error(typeof e === 'string' ? e : (e?.detail ?? 'Could not update team.'));
		}
	}

	let confirmDelete = false;
	async function deleteTeam(): Promise<void> {
		confirmDelete = false;
		try {
			await api.deleteTeam(token(), row.team.id);
			await onTreeChanged();
		} catch (e: any) {
			toast.error(typeof e === 'string' ? e : (e?.detail ?? 'Could not delete team.'));
		}
	}
</script>

<div class="flex flex-col gap-5 min-w-0">
	<!-- Team header card -->
	<div class="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
		<div class="flex flex-wrap items-start gap-4">
			<div class="size-14 rounded-2xl bg-brand-900 dark:bg-brand-800 flex items-center justify-center text-white text-xl font-semibold flex-none">
				{(row.team.key || row.team.name).trim().slice(0, 1).toUpperCase()}
			</div>
			<div class="flex-1 min-w-0">
				{#if renaming}
					<input
						class="text-xl font-semibold bg-transparent border-b border-gray-300 dark:border-gray-700 outline-none w-full max-w-sm"
						bind:value={nameDraft}
						onkeydown={(e) => { if (e.key === 'Enter') void saveRename(); if (e.key === 'Escape') renaming = false; }}
						onblur={() => void saveRename()}
						autofocus
					/>
				{:else}
					<div class="flex items-center gap-2 min-w-0">
						<span class="text-xl font-semibold truncate">{row.team.name}</span>
						{#if isOwner}
							<button class="p-1 rounded text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 flex-none" title="Rename team" onclick={startRename}>
								<Icon name="pencil" size={14} />
							</button>
						{/if}
					</div>
				{/if}
				<div class="text-[13px] text-gray-500 dark:text-gray-400 mt-1">
					{row.member_count} member{row.member_count === 1 ? '' : 's'} · {row.workspaces.length} workspace{row.workspaces.length === 1 ? '' : 's'}
				</div>
			</div>

			<!-- Meta columns -->
			<div class="flex items-start gap-8 flex-none">
				<div>
					<div class="text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">Team owner</div>
					<div class="mt-1.5 flex items-center gap-1.5">
						{#if ownerId}
							<span class="size-6 rounded-full bg-brand-100 text-brand-700 dark:bg-brand-900 dark:text-brand-200 text-[10px] font-semibold inline-flex items-center justify-center">{initials(ownerId)}</span>
						{/if}
						<span class="text-sm truncate max-w-[10rem]">{ownerName}</span>
					</div>
				</div>
				<div>
					<div class="text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">Created</div>
					<div class="mt-1.5 text-sm">{createdLabel}</div>
				</div>
				<div>
					<div class="text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">Team status</div>
					<div class="mt-1.5 flex items-center gap-1.5 text-sm">
						<span class="size-2 rounded-full {row.team.archived ? 'bg-gray-400' : 'bg-green-500'}"></span>
						{row.team.archived ? 'Archived' : 'Active'}
					</div>
				</div>
			</div>

			{#if isOwner}
				<div class="flex items-center gap-2 flex-none">
					<button
						class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 inline-flex items-center gap-1.5 hover:bg-gray-50 dark:hover:bg-gray-850 transition"
						onclick={() => void toggleArchived()}
					>
						<Icon name="archive" size={14} /> {row.team.archived ? 'Unarchive' : 'Archive'}
					</button>
					<button
						class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 text-red-600 dark:text-red-400 inline-flex items-center gap-1.5 hover:bg-red-50 dark:hover:bg-red-950/40 hover:border-red-200 dark:hover:border-red-900/60 transition"
						onclick={() => (confirmDelete = true)}
					>
						<Icon name="trash" size={14} /> Delete
					</button>
				</div>
			{/if}
		</div>
	</div>

	<MemberRoster
		teamId={row.team.id}
		{members}
		{allUsers}
		{isOwner}
		loaded={rosterLoaded}
		onChanged={rosterChanged}
	/>

	<WorkspacePanel
		teamId={row.team.id}
		workspaces={row.workspaces}
		teamMembers={members}
		{allUsers}
		onChanged={onOverviewChanged}
	/>
</div>

<Dialog.Root bind:open={confirmDelete}>
	<Dialog.Content class="max-w-md">
		<Dialog.Title>Delete team?</Dialog.Title>
		<Dialog.Description>
			This permanently deletes <span class="font-medium">{row.team.name}</span> with all of its
			workspaces, workstreams and tasks. This cannot be undone.
		</Dialog.Description>
		<div class="flex justify-end gap-2 mt-4">
			<button class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-850 transition" onclick={() => (confirmDelete = false)}>Cancel</button>
			<button class="text-sm px-3.5 py-1.5 rounded-lg bg-red-600 text-white hover:bg-red-700 font-medium transition" onclick={() => void deleteTeam()}>Delete team</button>
		</div>
	</Dialog.Content>
</Dialog.Root>
