<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import * as api from '../lib/api';
	import {
		openModal, token, loadBootstrap, directory
	} from '../lib/store';
	import { canManageMembers } from '../lib/roles';
	import type { TeamRole } from '../lib/types';

	let name = '';
	let key = '';
	let visibility: 'team' | 'restricted' = 'team';
	let busy = false;
	let err = '';

	// Members manager state
	let teamMembers: { user_id: string; role: string }[] = [];
	let addUserId = '';
	let addRole: TeamRole = 'member';

	$: req = $openModal;
	$: if (req) reset(req);

	async function reset(r: NonNullable<typeof req>) {
		name = '';
		key = '';
		visibility = 'team';
		err = '';
		if (r.kind === 'members') {
			teamMembers = (await api.listTeamMembers(token(), r.teamId).catch(() => [])).map((m) => ({ user_id: m.user_id, role: m.role }));
		}
	}

	function close() {
		openModal.set(null);
	}

	async function submit() {
		if (!req) return;
		busy = true;
		err = '';
		try {
			if (req.kind === 'team') {
				await api.createTeam(token(), { name, key: key.toUpperCase() });
			} else if (req.kind === 'workspace') {
				await api.createWorkspace(token(), req.teamId, { name, visibility });
			} else if (req.kind === 'workstream') {
				await api.createWorkstream(token(), req.workspaceId, { name });
			}
			await loadBootstrap();
			close();
		} catch (e: any) {
			err = typeof e === 'string' ? e : (e?.detail ?? 'Something went wrong.');
		} finally {
			busy = false;
		}
	}

	async function addMember(teamId: string) {
		if (!addUserId) return;
		try {
			await api.addTeamMember(token(), teamId, { user_id: addUserId, role: addRole });
			teamMembers = (await api.listTeamMembers(token(), teamId)).map((m) => ({ user_id: m.user_id, role: m.role }));
			addUserId = '';
		} catch (e: any) {
			err = typeof e === 'string' ? e : (e?.detail ?? 'Could not add member.');
		}
	}

	async function changeRole(teamId: string, userId: string, role: TeamRole) {
		await api.updateTeamMember(token(), teamId, userId, { role }).catch(() => {});
		teamMembers = (await api.listTeamMembers(token(), teamId)).map((m) => ({ user_id: m.user_id, role: m.role }));
	}

	async function removeMember(teamId: string, userId: string) {
		await api.removeTeamMember(token(), teamId, userId).catch(() => {});
		teamMembers = teamMembers.filter((m) => m.user_id !== userId);
	}

	const TITLES = { team: 'New team', workspace: 'New workspace', workstream: 'New workstream', members: 'Team members' };
</script>

{#if req}
	<div class="fixed inset-0 z-40 flex items-center justify-center">
		<div class="absolute inset-0 bg-black/40" onclick={close} role="presentation"></div>
		<div class="relative w-[420px] max-w-[92%] rounded-xl bg-white dark:bg-gray-950 border border-gray-200 dark:border-gray-800 shadow-2xl p-5">
			<div class="flex items-center mb-4">
				<h2 class="text-base font-semibold flex-1">{TITLES[req.kind]}</h2>
				<button class="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-900" onclick={close}><Icon name="x" size={16} /></button>
			</div>

			{#if err}<div class="mb-3 text-sm text-red-600">{err}</div>{/if}

			{#if req.kind === 'members'}
				<div class="space-y-2 max-h-72 overflow-y-auto">
					{#each teamMembers as m (m.user_id)}
						<div class="flex items-center gap-2">
							<span class="flex-1 text-sm truncate">{$directory[m.user_id]?.name ?? m.user_id}</span>
							<select class="text-xs border border-gray-200 dark:border-gray-700 rounded px-1 py-0.5 bg-transparent" value={m.role} onchange={(e) => changeRole(req.teamId, m.user_id, (e.target as HTMLSelectElement).value as TeamRole)}>
								<option value="owner">owner</option>
								<option value="admin">admin</option>
								<option value="member">member</option>
							</select>
							<button class="text-red-500 p-1" onclick={() => removeMember(req.teamId, m.user_id)}><Icon name="x" size={14} /></button>
						</div>
					{/each}
				</div>
				<div class="flex items-center gap-2 mt-4 pt-3 border-t border-gray-200 dark:border-gray-800">
					<select class="flex-1 text-sm border border-gray-200 dark:border-gray-700 rounded px-2 py-1 bg-transparent" bind:value={addUserId}>
						<option value="">Add a user…</option>
						{#each Object.entries($directory) as [id, u] (id)}<option value={id}>{u.name}</option>{/each}
					</select>
					<select class="text-sm border border-gray-200 dark:border-gray-700 rounded px-2 py-1 bg-transparent" bind:value={addRole}>
						<option value="member">member</option>
						<option value="admin">admin</option>
						<option value="owner">owner</option>
					</select>
					<button class="text-sm px-3 py-1 rounded bg-teal-600 text-white" onclick={() => addMember(req.teamId)}>Add</button>
				</div>
			{:else}
				<div class="space-y-3">
					<input class="w-full text-sm px-3 py-2 rounded border border-gray-300 dark:border-gray-700 bg-transparent" placeholder="Name" bind:value={name} autofocus />
					{#if req.kind === 'team'}
						<input class="w-full text-sm px-3 py-2 rounded border border-gray-300 dark:border-gray-700 bg-transparent font-mono uppercase" placeholder="Key (e.g. OSL)" bind:value={key} maxlength="6" />
						<p class="text-xs text-gray-400">The key prefixes task numbers, e.g. {(key || 'OSL').toUpperCase()}-1.</p>
					{:else if req.kind === 'workspace'}
						<select class="w-full text-sm px-3 py-2 rounded border border-gray-300 dark:border-gray-700 bg-transparent" bind:value={visibility}>
							<option value="team">Visible to whole team</option>
							<option value="restricted">Restricted to members</option>
						</select>
					{/if}
				</div>
				<div class="flex justify-end gap-2 mt-5">
					<button class="text-sm px-3 py-1.5 rounded border border-gray-300 dark:border-gray-700" onclick={close}>Cancel</button>
					<button class="text-sm px-3 py-1.5 rounded bg-teal-600 text-white disabled:opacity-50" disabled={busy || !name.trim() || (req.kind === 'team' && !key.trim())} onclick={submit}>Create</button>
				</div>
			{/if}
		</div>
	</div>
{/if}
