<script lang="ts">
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Select from '$lib/components/ui/select';
	import { Button } from '$lib/components/ui/button';
	import Icon from '../../ui/Icon.svelte';
	import RestrictConfirmDialog from './RestrictConfirmDialog.svelte';
	import * as api from '../../lib/api';
	import {
		openModal, token, teams, workspaces, directory, initials, loadBootstrap
	} from '../../lib/store';
	import { addableWorkspaceMembers } from '../../lib/members';
	import { avatarColors } from '../../lib/avatar';
	import type { Member, WorkspaceRole } from '../../lib/types';

	const ROLE_LABEL: Record<string, string> = { admin: 'Admin', member: 'Member' };

	$: req = $openModal?.kind === 'workspace-settings' ? $openModal : null;
	$: ws = req ? ($workspaces.find((w) => w.id === req.workspaceId) ?? null) : null;
	$: team = ws ? ($teams.find((t) => t.id === ws.team_id) ?? null) : null;

	let wsMembers: Member[] = [];
	let teamMembers: Member[] = [];
	let allUsers: { id: string; name: string }[] = [];
	let loaded = false;
	let loadedFor: string | null = null;
	let addUserId = '';
	let addRole: WorkspaceRole = 'member';
	let busy = false;
	let nameDraft = '';
	let confirmRestrict = false;
	let confirmDelete = false;

	// One reset+fetch per open; reactive re-runs with the same id are no-ops.
	$: void syncLoad(req?.workspaceId ?? null);
	async function syncLoad(id: string | null): Promise<void> {
		if (!id) { loadedFor = null; return; }
		if (loadedFor === id) return;
		loadedFor = id;
		addUserId = '';
		addRole = 'member';
		confirmRestrict = false;
		confirmDelete = false;
		nameDraft = get(workspaces).find((w) => w.id === id)?.name ?? '';
		await refresh(id);
	}

	async function refresh(id: string): Promise<void> {
		loaded = false;
		const w = get(workspaces).find((x) => x.id === id);
		const teamId = w?.team_id;
		const [wm, tm, us] = await Promise.all([
			w?.visibility === 'restricted'
				? api.listWorkspaceMembers(token(), id).catch(() => [] as Member[])
				: Promise.resolve([] as Member[]),
			teamId ? api.listTeamMembers(token(), teamId).catch(() => [] as Member[]) : Promise.resolve([] as Member[]),
			teamId
				? api.listAllUsers(token(), teamId).catch(() => [] as { id: string; name: string }[])
				: Promise.resolve([] as { id: string; name: string }[])
		]);
		if (loadedFor !== id) return; // dialog closed or retargeted mid-flight
		wsMembers = wm;
		teamMembers = tm;
		allUsers = us;
		loaded = true;
	}

	$: nameOf = (id: string) => allUsers.find((u) => u.id === id)?.name ?? $directory[id]?.name ?? id;
	// Picker offers team members only: the backend does not validate the target
	// is on the team, so the UI enforces the sane subset.
	$: candidates = addableWorkspaceMembers(teamMembers, wsMembers);

	function detail(e: any, fallback: string): string {
		return typeof e === 'string' ? e : (e?.detail ?? fallback);
	}

	function close(): void {
		openModal.set(null);
	}

	function requestVisibility(v: 'team' | 'restricted'): void {
		if (!ws || busy || ws.visibility === v) return;
		if (v === 'restricted') confirmRestrict = true; // destructive: locks people out
		else void setVisibility('team'); // opening up — no confirmation needed
	}

	async function setVisibility(v: 'team' | 'restricted'): Promise<void> {
		if (!req) return;
		const id = req.workspaceId;
		busy = true;
		try {
			await api.updateWorkspace(token(), id, { visibility: v });
			await loadBootstrap();
			// The flip can remove the workspace from the actor's own tree (a team
			// admin who is neither member nor creator) — close instead of a husk.
			if (!get(workspaces).some((x) => x.id === id)) {
				busy = false;
				confirmRestrict = false;
				close();
				return;
			}
			await refresh(id);
		} catch (e: any) {
			toast.error(detail(e, 'Could not change visibility.'));
		} finally {
			busy = false;
			confirmRestrict = false;
		}
	}

	async function mutateMembers(fn: () => Promise<unknown>, fallback: string): Promise<void> {
		if (!req) return;
		const id = req.workspaceId;
		busy = true;
		try {
			await fn();
		} catch (e: any) {
			toast.error(detail(e, fallback));
		} finally {
			busy = false;
			await refresh(id); // refresh either way so a rejected change snaps back
		}
	}

	const changeMemberRole = (userId: string, role: WorkspaceRole) =>
		mutateMembers(() => api.updateWorkspaceMember(token(), req!.workspaceId, userId, { role }), 'Could not change role.');
	const removeMember = (userId: string) =>
		mutateMembers(() => api.removeWorkspaceMember(token(), req!.workspaceId, userId), 'Could not remove member.');
	const addMember = () => {
		if (!addUserId) return Promise.resolve();
		const id = addUserId;
		addUserId = '';
		return mutateMembers(
			() => api.addWorkspaceMember(token(), req!.workspaceId, { user_id: id, role: addRole }),
			'Could not add member.'
		);
	};

	async function saveRename(): Promise<void> {
		if (!req || !ws) return;
		const name = nameDraft.trim();
		if (!name || name === ws.name) return;
		busy = true;
		try {
			await api.updateWorkspace(token(), req.workspaceId, { name });
			await loadBootstrap();
		} catch (e: any) {
			toast.error(detail(e, 'Could not rename workspace.'));
		} finally {
			busy = false;
		}
	}

	async function deleteWorkspace(): Promise<void> {
		if (!req) return;
		busy = true;
		try {
			await api.deleteWorkspace(token(), req.workspaceId);
			close();
			await loadBootstrap();
		} catch (e: any) {
			toast.error(detail(e, 'Could not delete workspace.'));
		} finally {
			busy = false;
			confirmDelete = false;
		}
	}
</script>

<Dialog.Root open={!!req} onOpenChange={(o) => { if (!o) close(); }}>
	<Dialog.Content class="sm:max-w-xl gap-6 rounded-2xl p-5 md:p-7 max-h-[90dvh] overflow-y-auto">
		<div class="flex items-center gap-3.5">
			<div class="size-11 rounded-xl bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 flex items-center justify-center flex-none">
				<Icon name="layers" size={20} />
			</div>
			<div class="flex-1 min-w-0">
				<Dialog.Title class="text-lg">Workspace settings</Dialog.Title>
				<Dialog.Description class="truncate mt-0.5">{ws?.name ?? ''}{team ? ` · ${team.name}` : ''}</Dialog.Description>
			</div>
		</div>

		<div class="flex flex-col gap-6">
			<div>
				<div class="text-[13px] font-medium text-gray-800 dark:text-gray-200 mb-2.5">Visibility</div>
				<div class="grid grid-cols-2 gap-3">
					<button
						class="rounded-xl border p-4 text-left transition disabled:opacity-60 {ws?.visibility === 'team'
							? 'border-gray-900 dark:border-gray-100 ring-1 ring-gray-900 dark:ring-gray-100 bg-gray-50 dark:bg-gray-900'
							: 'border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'}"
						disabled={busy}
						onclick={() => requestVisibility('team')}
					>
						<div class="text-sm font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2"><Icon name="users" size={16} /> Team-visible</div>
						<div class="text-[13px] text-gray-500 dark:text-gray-400 mt-1.5 leading-relaxed">Everyone on the team can see it.</div>
					</button>
					<button
						class="rounded-xl border p-4 text-left transition disabled:opacity-60 {ws?.visibility === 'restricted'
							? 'border-gray-900 dark:border-gray-100 ring-1 ring-gray-900 dark:ring-gray-100 bg-gray-50 dark:bg-gray-900'
							: 'border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'}"
						disabled={busy}
						onclick={() => requestVisibility('restricted')}
					>
						<div class="text-sm font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2"><Icon name="lock" size={16} /> Restricted</div>
						<div class="text-[13px] text-gray-500 dark:text-gray-400 mt-1.5 leading-relaxed">Only explicit members and the creator.</div>
					</button>
				</div>
			</div>

			{#if ws?.visibility === 'restricted'}
				<div>
					<div class="text-[13px] font-medium text-gray-800 dark:text-gray-200 mb-2.5">
						Members{loaded ? ` · ${wsMembers.length}` : ''}
					</div>
					<div class="rounded-xl border border-gray-200 dark:border-gray-800 px-4 py-1">
						{#if !loaded}
							<div class="py-2.5 text-[13px] text-gray-400">Loading…</div>
						{:else}
							{#each wsMembers as m (m.user_id)}
								{@const colors = avatarColors(m.user_id)}
								<div class="flex items-center gap-3 py-2.5 border-t border-gray-100 dark:border-gray-800 first:border-t-0">
									<span
										class="size-7 rounded-full text-[11px] font-semibold inline-flex items-center justify-center flex-none"
										style="background:{colors.background};color:{colors.foreground}"
									>
										{initials(m.user_id)}
									</span>
									<span class="flex-1 min-w-0 text-sm text-gray-900 dark:text-gray-100 truncate">{nameOf(m.user_id)}</span>
									<Select.Root
										type="single"
										value={m.role}
										disabled={busy}
										onValueChange={(v) => v && v !== m.role && void changeMemberRole(m.user_id, v as WorkspaceRole)}
									>
										<Select.Trigger size="sm" class="w-[110px]">{ROLE_LABEL[m.role] ?? m.role}</Select.Trigger>
										<Select.Content>
											<Select.Item value="admin" label="Admin" />
											<Select.Item value="member" label="Member" />
										</Select.Content>
									</Select.Root>
									<button
										class="p-1.5 rounded-lg text-gray-400 hover:text-red-600 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 transition disabled:opacity-50"
										title="Remove from workspace — non-creators lose access immediately"
										disabled={busy}
										onclick={() => void removeMember(m.user_id)}
									>
										<Icon name="x" size={14} />
									</button>
								</div>
							{:else}
								<div class="text-[13px] text-gray-500 dark:text-gray-400 py-3 leading-relaxed">No explicit members — only the creator and admins can see this.</div>
							{/each}
							<div class="flex items-center gap-2 py-2.5 border-t border-gray-100 dark:border-gray-800">
								<Select.Root type="single" bind:value={addUserId} disabled={busy || !candidates.length}>
									<Select.Trigger size="sm" class="flex-1 min-w-0 justify-between font-normal">
										<span class="truncate {addUserId ? '' : 'text-gray-400'}">
											{addUserId ? nameOf(addUserId) : candidates.length ? 'Add a team member…' : 'All team members added'}
										</span>
									</Select.Trigger>
									<Select.Content>
										{#each candidates as m (m.user_id)}
											<Select.Item value={m.user_id} label={nameOf(m.user_id)} />
										{/each}
									</Select.Content>
								</Select.Root>
								<Select.Root type="single" bind:value={addRole} disabled={busy}>
									<Select.Trigger size="sm" class="w-[110px]">{ROLE_LABEL[addRole]}</Select.Trigger>
									<Select.Content>
										<Select.Item value="member" label="Member" />
										<Select.Item value="admin" label="Admin" />
									</Select.Content>
								</Select.Root>
								<button
									class="text-sm font-medium px-3.5 py-1.5 rounded-lg bg-gray-900 text-white hover:bg-gray-800 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-200 disabled:opacity-50 transition"
									disabled={busy || !addUserId}
									onclick={() => void addMember()}
								>
									Add
								</button>
							</div>
						{/if}
					</div>
				</div>
			{/if}

			<div>
				<div class="text-[13px] font-medium text-gray-800 dark:text-gray-200 mb-2.5">Workspace name</div>
				<div class="flex items-center gap-2.5">
					<input
						class="flex-1 text-sm text-gray-900 dark:text-gray-100 px-3.5 py-2.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent outline-none focus:border-gray-500 dark:focus:border-gray-500 transition"
						bind:value={nameDraft}
						onkeydown={(e) => { if (e.key === 'Enter') void saveRename(); }}
					/>
					<button
						class="text-sm px-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-850 transition disabled:opacity-50 flex-none"
						disabled={busy || !nameDraft.trim() || nameDraft.trim() === ws?.name}
						onclick={() => void saveRename()}
					>
						Save
					</button>
				</div>
			</div>

			<div class="flex items-center gap-3.5 rounded-xl border border-red-200 dark:border-red-900/60 bg-red-50/50 dark:bg-red-950/20 px-4 py-3.5">
				<div class="flex-1 min-w-0">
					<div class="text-sm font-medium text-red-700 dark:text-red-400">Delete workspace</div>
					<div class="text-[13px] text-red-600/80 dark:text-red-400/70 mt-1 leading-relaxed">Removes all workstreams and tasks. Cannot be undone.</div>
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
	</Dialog.Content>
</Dialog.Root>

<RestrictConfirmDialog
	open={confirmRestrict}
	name={ws?.name ?? ''}
	{busy}
	onCancel={() => (confirmRestrict = false)}
	onConfirm={() => void setVisibility('restricted')}
/>

<Dialog.Root bind:open={confirmDelete}>
	<Dialog.Content class="sm:max-w-md gap-4 rounded-2xl p-6">
		<Dialog.Title class="text-lg">Delete workspace?</Dialog.Title>
		<Dialog.Description class="leading-relaxed">
			This permanently deletes <span class="font-medium text-gray-700 dark:text-gray-200">{ws?.name ?? ''}</span> with all of its
			workstreams and tasks. This cannot be undone.
		</Dialog.Description>
		<div class="flex justify-end gap-2 mt-2">
			<Button variant="outline" size="sm" onclick={() => (confirmDelete = false)}>Cancel</Button>
			<Button variant="destructive" size="sm" disabled={busy} onclick={() => void deleteWorkspace()}>Delete workspace</Button>
		</div>
	</Dialog.Content>
</Dialog.Root>
