<script lang="ts">
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Tabs from '$lib/components/ui/tabs';
	import * as Select from '$lib/components/ui/select';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import Icon from '../../ui/Icon.svelte';
	import * as api from '../../lib/api';
	import {
		openModal, token, teams, roles, directory, initials, loadBootstrap, reloadDirectory
	} from '../../lib/store';
	import { user } from '$lib/stores';
	import { addableUsers, isLastOwner } from '../../lib/members';
	import type { Member, TeamRole } from '../../lib/types';

	const ROLE_LABEL: Record<string, string> = { owner: 'Owner', admin: 'Admin', member: 'Member' };

	$: req = $openModal?.kind === 'team-settings' ? $openModal : null;
	$: team = req ? ($teams.find((t) => t.id === req.teamId) ?? null) : null;
	// System admins pass every owner gate server-side (their team_role() is
	// 'admin' and require_team_role early-returns) — treat them as owners here.
	$: isOwner = $user?.role === 'admin' || (req ? $roles[req.teamId] === 'owner' : false);

	let tab = 'members';
	let members: Member[] = [];
	let allUsers: { id: string; name: string }[] = [];
	let loaded = false;
	let loadedFor: string | null = null;
	let addUserId = '';
	let addRole: TeamRole = 'member';
	let busy = false;
	let nameDraft = '';
	let confirmDelete = false;

	// One reset+fetch per open; reactive re-runs with the same id are no-ops.
	$: void syncLoad(req?.teamId ?? null);
	async function syncLoad(id: string | null): Promise<void> {
		if (!id) { loadedFor = null; return; }
		if (loadedFor === id) return;
		loadedFor = id;
		tab = 'members';
		addUserId = '';
		addRole = 'member';
		confirmDelete = false;
		nameDraft = get(teams).find((t) => t.id === id)?.name ?? '';
		await refresh(id);
	}

	async function refresh(id: string): Promise<void> {
		loaded = false;
		const [ms, us] = await Promise.all([
			api.listTeamMembers(token(), id).catch(() => [] as Member[]),
			api.listAllUsers(token(), id).catch(() => [] as { id: string; name: string }[])
		]);
		if (loadedFor !== id) return; // dialog closed or retargeted mid-flight
		members = ms;
		allUsers = us;
		loaded = true;
	}

	$: nameOf = (id: string) => allUsers.find((u) => u.id === id)?.name ?? $directory[id]?.name ?? id;
	$: candidates = addableUsers(allUsers, members);
	$: ownerIds = members.filter((m) => m.role === 'owner').map((m) => m.user_id);
	// Granting owner/admin is owner-only (team.members.grant_privileged);
	// demoting to member is plain member management.
	$: roleItems = [
		{ value: 'owner', disabled: !isOwner },
		{ value: 'admin', disabled: !isOwner },
		{ value: 'member', disabled: false }
	];
	$: addRoleItems = isOwner ? ['member', 'admin', 'owner'] : ['member'];

	function detail(e: any, fallback: string): string {
		return typeof e === 'string' ? e : (e?.detail ?? fallback);
	}

	function close(): void {
		openModal.set(null);
	}

	async function mutateRoster(fn: () => Promise<unknown>, fallback: string): Promise<void> {
		if (!req) return;
		const id = req.teamId;
		busy = true;
		try {
			await fn();
		} catch (e: any) {
			toast.error(detail(e, fallback));
		} finally {
			busy = false;
			await refresh(id); // refresh either way so a rejected change snaps back
			await reloadDirectory();
		}
	}

	const changeRole = (userId: string, role: TeamRole, prev: string) =>
		role === prev
			? Promise.resolve()
			: mutateRoster(() => api.updateTeamMember(token(), req!.teamId, userId, { role }), 'Could not change role.');
	const removeMember = (userId: string) =>
		mutateRoster(() => api.removeTeamMember(token(), req!.teamId, userId), 'Could not remove member.');
	const addMember = () => {
		if (!addUserId) return Promise.resolve();
		const id = addUserId;
		addUserId = '';
		return mutateRoster(
			() => api.addTeamMember(token(), req!.teamId, { user_id: id, role: addRole }),
			'Could not add member.'
		);
	};

	async function saveRename(): Promise<void> {
		if (!req || !team) return;
		const name = nameDraft.trim();
		if (!name || name === team.name) return;
		busy = true;
		try {
			await api.updateTeam(token(), req.teamId, { name });
			await loadBootstrap();
		} catch (e: any) {
			toast.error(detail(e, 'Could not rename team.'));
		} finally {
			busy = false;
		}
	}

	async function toggleArchived(): Promise<void> {
		if (!req || !team) return;
		busy = true;
		try {
			await api.updateTeam(token(), req.teamId, { archived: !team.archived });
			await loadBootstrap();
		} catch (e: any) {
			toast.error(detail(e, 'Could not update team.'));
		} finally {
			busy = false;
		}
	}

	async function deleteTeam(): Promise<void> {
		if (!req) return;
		busy = true;
		try {
			await api.deleteTeam(token(), req.teamId);
			close();
			await loadBootstrap();
		} catch (e: any) {
			toast.error(detail(e, 'Could not delete team.'));
		} finally {
			busy = false;
			confirmDelete = false;
		}
	}
</script>

<Dialog.Root open={!!req} onOpenChange={(o) => { if (!o) close(); }}>
	<Dialog.Content class="sm:max-w-xl gap-6 rounded-2xl p-7">
		<div class="flex items-center gap-3.5">
			<div class="size-11 rounded-xl bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900 flex items-center justify-center text-lg font-semibold flex-none">
				{(team?.key || team?.name || '?').trim().slice(0, 1).toUpperCase()}
			</div>
			<div class="flex-1 min-w-0">
				<Dialog.Title class="text-lg">Team settings</Dialog.Title>
				<Dialog.Description class="truncate mt-0.5">
					{team?.name ?? ''}{loaded ? ` · ${members.length} member${members.length === 1 ? '' : 's'}` : ''}
				</Dialog.Description>
			</div>
		</div>

		<Tabs.Root bind:value={tab}>
			<Tabs.List>
				<Tabs.Trigger value="members">Members</Tabs.Trigger>
				{#if isOwner}
					<Tabs.Trigger value="general">General</Tabs.Trigger>
				{/if}
			</Tabs.List>

			<Tabs.Content value="members">
				{#if !loaded}
					<div class="py-8 text-sm text-gray-400">Loading…</div>
				{:else}
					<div class="flex flex-col max-h-80 overflow-y-auto -mx-1 px-1">
						{#each members as m (m.user_id)}
							{@const lastOwner = isLastOwner(ownerIds, m.user_id)}
							<div class="flex items-center gap-3 py-3 border-t border-gray-100 dark:border-gray-800 first:border-t-0">
								<span class="size-9 rounded-full bg-brand-100 text-brand-700 dark:bg-brand-900 dark:text-brand-200 text-[11px] font-semibold inline-flex items-center justify-center flex-none">{initials(m.user_id)}</span>
								<span class="flex-1 min-w-0 text-sm text-gray-900 dark:text-gray-100 truncate">{nameOf(m.user_id)}</span>
								{#if lastOwner}
									<span class="text-[13px] text-gray-400 flex items-center gap-1.5 px-1" title="The last owner cannot be demoted or removed">
										<Icon name="lock" size={13} /> Last owner
									</span>
								{:else}
									<Select.Root
										type="single"
										value={m.role}
										disabled={busy}
										onValueChange={(v) => v && void changeRole(m.user_id, v as TeamRole, m.role)}
									>
										<Select.Trigger size="sm" class="w-[116px]">{ROLE_LABEL[m.role] ?? m.role}</Select.Trigger>
										<Select.Content>
											{#each roleItems as r (r.value)}
												<Select.Item value={r.value} label={ROLE_LABEL[r.value]} disabled={r.disabled} />
											{/each}
										</Select.Content>
									</Select.Root>
									<DropdownMenu.Root>
										<DropdownMenu.Trigger
											class="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition disabled:opacity-50"
											title="More"
											disabled={busy}
										>
											<Icon name="more-horizontal" size={16} />
										</DropdownMenu.Trigger>
										<DropdownMenu.Content align="end">
											<DropdownMenu.Item class="text-red-600 dark:text-red-400" onSelect={() => void removeMember(m.user_id)}>
												<span class="inline-flex items-center gap-2"><Icon name="x" size={14} /> Remove from team</span>
											</DropdownMenu.Item>
										</DropdownMenu.Content>
									</DropdownMenu.Root>
								{/if}
							</div>
						{/each}
					</div>

					<div class="flex items-center gap-2 mt-4 pt-4 border-t border-gray-100 dark:border-gray-800">
						<span class="text-gray-400 flex-none"><Icon name="user-plus" size={16} /></span>
						<Select.Root type="single" bind:value={addUserId} disabled={busy || !candidates.length}>
							<Select.Trigger class="flex-1 min-w-0 h-9 justify-between font-normal">
								<span class="truncate {addUserId ? '' : 'text-gray-400'}">
									{addUserId ? nameOf(addUserId) : candidates.length ? 'Add a person…' : 'No more users to add'}
								</span>
							</Select.Trigger>
							<Select.Content>
								{#each candidates as u (u.id)}
									<Select.Item value={u.id} label={u.name} />
								{/each}
							</Select.Content>
						</Select.Root>
						<Select.Root type="single" bind:value={addRole} disabled={busy}>
							<Select.Trigger class="w-[116px] h-9">{ROLE_LABEL[addRole]}</Select.Trigger>
							<Select.Content>
								{#each addRoleItems as r (r)}
									<Select.Item value={r} label={ROLE_LABEL[r]} />
								{/each}
							</Select.Content>
						</Select.Root>
						<button
							class="text-sm font-medium px-4 py-2 rounded-lg bg-gray-900 text-white hover:bg-gray-800 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-200 disabled:opacity-50 transition"
							disabled={busy || !addUserId}
							onclick={() => void addMember()}
						>
							Add
						</button>
					</div>
				{/if}
			</Tabs.Content>

			{#if isOwner}
				<Tabs.Content value="general">
					<div class="flex flex-col gap-6 pt-2">
						<div>
							<div class="text-[13px] font-medium text-gray-800 dark:text-gray-200 mb-2.5">Team name</div>
							<div class="flex items-center gap-2.5">
								<input
									class="flex-1 text-sm text-gray-900 dark:text-gray-100 px-3.5 py-2.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent outline-none focus:border-gray-500 dark:focus:border-gray-500 transition"
									bind:value={nameDraft}
									onkeydown={(e) => { if (e.key === 'Enter') void saveRename(); }}
								/>
								<button
									class="text-sm px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-850 transition disabled:opacity-50 flex-none"
									disabled={busy || !nameDraft.trim() || nameDraft.trim() === team?.name}
									onclick={() => void saveRename()}
								>
									Save
								</button>
							</div>
						</div>

						<div class="flex items-center justify-between gap-3 rounded-xl border border-gray-200 dark:border-gray-800 px-4 py-3.5">
							<div class="min-w-0">
								<div class="text-sm font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2">
									<span class="size-2 rounded-full {team?.archived ? 'bg-gray-400' : 'bg-green-500'} flex-none"></span>
									{team?.archived ? 'Archived' : 'Active'}
								</div>
								<div class="text-[13px] text-gray-500 dark:text-gray-400 mt-1 leading-relaxed">Archiving hides the team without deleting anything.</div>
							</div>
							<button
								class="text-sm px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 inline-flex items-center gap-1.5 hover:bg-gray-50 dark:hover:bg-gray-850 transition disabled:opacity-50 flex-none"
								disabled={busy}
								onclick={() => void toggleArchived()}
							>
								<Icon name="archive" size={14} /> {team?.archived ? 'Unarchive' : 'Archive'}
							</button>
						</div>

						<div class="flex items-center gap-3.5 rounded-xl border border-red-200 dark:border-red-900/60 bg-red-50/50 dark:bg-red-950/20 px-4 py-3.5">
							<div class="flex-1 min-w-0">
								<div class="text-sm font-medium text-red-700 dark:text-red-400">Delete team</div>
								<div class="text-[13px] text-red-600/80 dark:text-red-400/70 mt-1 leading-relaxed">Removes all workspaces, workstreams and tasks. Cannot be undone.</div>
							</div>
							<button
								class="text-sm font-medium px-4 py-2 rounded-lg border border-red-300 dark:border-red-900/60 text-red-700 dark:text-red-400 hover:bg-red-100/70 dark:hover:bg-red-950/40 transition flex-none"
								disabled={busy}
								onclick={() => (confirmDelete = true)}
							>
								Delete…
							</button>
						</div>
					</div>
				</Tabs.Content>
			{/if}
		</Tabs.Root>
	</Dialog.Content>
</Dialog.Root>

<Dialog.Root bind:open={confirmDelete}>
	<Dialog.Content class="sm:max-w-md gap-4 rounded-2xl p-6">
		<Dialog.Title class="text-lg">Delete team?</Dialog.Title>
		<Dialog.Description class="leading-relaxed">
			This permanently deletes <span class="font-medium text-gray-700 dark:text-gray-200">{team?.name ?? ''}</span> with all of its
			workspaces, workstreams and tasks. This cannot be undone.
		</Dialog.Description>
		<div class="flex justify-end gap-2 mt-2">
			<button class="text-sm px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-850 transition" onclick={() => (confirmDelete = false)}>Cancel</button>
			<button class="text-sm font-medium px-4 py-2 rounded-lg bg-red-600 text-white hover:bg-red-700 transition" disabled={busy} onclick={() => void deleteTeam()}>Delete team</button>
		</div>
	</Dialog.Content>
</Dialog.Root>
