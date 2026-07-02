<script lang="ts">
	import { onMount } from 'svelte';
	import { toast } from 'svelte-sonner';
	import * as Select from '$lib/components/ui/select';
	import Icon from '../../ui/Icon.svelte';
	import * as api from '../../lib/api';
	import { token, directory, initials } from '../../lib/store';
	import { addableWorkspaceMembers } from '../../lib/accessConsole';
	import type { Member, WorkspaceRole } from '../../lib/types';

	export let workspaceId: string;
	export let teamMembers: Member[] = [];
	export let allUsers: { id: string; name: string }[] = [];
	export let onChanged: () => Promise<void>;

	let wsMembers: Member[] = [];
	let loaded = false;
	let addUserId = '';
	let addRole: WorkspaceRole = 'member';
	let busy = false;

	$: nameOf = (id: string) => allUsers.find((u) => u.id === id)?.name ?? $directory[id]?.name ?? id;
	// Picker offers team members only: the backend does not validate the target is
	// on the team, so the UI enforces the sane subset.
	$: candidates = addableWorkspaceMembers(teamMembers, wsMembers);

	const ROLE_LABEL: Record<string, string> = { admin: 'Admin', member: 'Member' };

	function detail(e: any, fallback: string): string {
		return typeof e === 'string' ? e : (e?.detail ?? fallback);
	}

	async function load(): Promise<void> {
		wsMembers = await api.listWorkspaceMembers(token(), workspaceId).catch(() => wsMembers);
		loaded = true;
	}
	onMount(() => void load());

	async function mutate(fn: () => Promise<unknown>, fallback: string): Promise<void> {
		busy = true;
		try {
			await fn();
		} catch (e: any) {
			toast.error(detail(e, fallback));
		} finally {
			busy = false;
			await load();
			await onChanged(); // keep the overview's member_count fresh
		}
	}

	const changeRole = (userId: string, role: WorkspaceRole) =>
		mutate(() => api.updateWorkspaceMember(token(), workspaceId, userId, { role }), 'Could not change role.');
	const remove = (userId: string) =>
		mutate(() => api.removeWorkspaceMember(token(), workspaceId, userId), 'Could not remove member.');
	const add = () => {
		if (!addUserId) return Promise.resolve();
		const id = addUserId;
		addUserId = '';
		return mutate(() => api.addWorkspaceMember(token(), workspaceId, { user_id: id, role: addRole }), 'Could not add member.');
	};
</script>

{#if !loaded}
	<div class="py-2 text-xs text-gray-400">Loading…</div>
{:else}
	<div class="flex flex-col">
		{#each wsMembers as m (m.user_id)}
			<div class="flex items-center gap-2.5 py-1.5">
				<span class="size-6 rounded-full bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-300 text-[10px] font-semibold inline-flex items-center justify-center flex-none">{initials(m.user_id)}</span>
				<span class="flex-1 min-w-0 text-sm truncate">{nameOf(m.user_id)}</span>
				<Select.Root
					type="single"
					value={m.role}
					disabled={busy}
					onValueChange={(v) => v && v !== m.role && void changeRole(m.user_id, v as WorkspaceRole)}
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
					onclick={() => void remove(m.user_id)}
				>
					<Icon name="x" size={14} />
				</button>
			</div>
		{:else}
			<div class="text-[13px] text-gray-400 py-1">No explicit members — only the creator and admins can see this.</div>
		{/each}
	</div>
	<div class="flex items-center gap-2 mt-2.5 pt-2.5 border-t border-gray-100 dark:border-gray-800">
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
			class="text-sm font-medium px-3.5 py-2 rounded-lg bg-brand-900 text-white hover:bg-brand-800 dark:bg-brand-800 dark:hover:bg-brand-700 disabled:opacity-50 transition"
			disabled={busy || !addUserId}
			onclick={() => void add()}
		>
			Add
		</button>
	</div>
{/if}
