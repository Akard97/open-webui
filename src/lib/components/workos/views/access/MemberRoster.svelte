<script lang="ts">
	import { toast } from 'svelte-sonner';
	import * as Select from '$lib/components/ui/select';
	import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
	import Icon from '../../ui/Icon.svelte';
	import * as api from '../../lib/api';
	import { token, directory, initials } from '../../lib/store';
	import { addableUsers, isLastOwner } from '../../lib/accessConsole';
	import type { Member, TeamRole } from '../../lib/types';

	export let teamId: string;
	export let members: Member[] = [];
	export let allUsers: { id: string; name: string }[] = [];
	export let isOwner = false;
	export let loaded = false;
	export let onChanged: () => Promise<void>;

	let addUserId = '';
	let addRole: TeamRole = 'member';
	let busy = false;

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

	const ROLE_LABEL: Record<string, string> = { owner: 'Owner', admin: 'Admin', member: 'Member' };

	function detail(e: any, fallback: string): string {
		return typeof e === 'string' ? e : (e?.detail ?? fallback);
	}

	async function changeRole(userId: string, role: TeamRole, prev: string): Promise<void> {
		if (role === prev) return;
		busy = true;
		try {
			await api.updateTeamMember(token(), teamId, userId, { role });
		} catch (e: any) {
			toast.error(detail(e, 'Could not change role.'));
		} finally {
			busy = false;
			await onChanged(); // refresh either way so a rejected change snaps back
		}
	}

	async function remove(userId: string): Promise<void> {
		busy = true;
		try {
			await api.removeTeamMember(token(), teamId, userId);
		} catch (e: any) {
			toast.error(detail(e, 'Could not remove member.'));
		} finally {
			busy = false;
			await onChanged();
		}
	}

	async function add(): Promise<void> {
		if (!addUserId) return;
		busy = true;
		try {
			await api.addTeamMember(token(), teamId, { user_id: addUserId, role: addRole });
			addUserId = '';
			addRole = 'member';
		} catch (e: any) {
			toast.error(detail(e, 'Could not add member.'));
		} finally {
			busy = false;
			await onChanged();
		}
	}
</script>

<div class="rounded-2xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5">
	<div class="flex items-center gap-2 mb-4">
		<span class="text-gray-500 dark:text-gray-400"><Icon name="users" size={17} /></span>
		<span class="text-[15px] font-semibold">Members</span>
		<span class="text-xs font-medium text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 rounded-full min-w-5 h-5 px-1.5 inline-flex items-center justify-center">{members.length}</span>
		<div class="flex-1"></div>
		<div class="flex -space-x-2">
			{#each members.slice(0, 5) as m (m.user_id)}
				<span class="size-7 rounded-full bg-brand-100 text-brand-700 dark:bg-brand-900 dark:text-brand-200 border-2 border-white dark:border-gray-900 text-[10px] font-semibold inline-flex items-center justify-center" title={nameOf(m.user_id)}>{initials(m.user_id)}</span>
			{/each}
		</div>
	</div>

	{#if !loaded}
		<div class="py-4 text-sm text-gray-400">Loading…</div>
	{:else}
		<div class="flex flex-col">
			{#each members as m (m.user_id)}
				{@const lastOwner = isLastOwner(ownerIds, m.user_id)}
				<div class="flex items-center gap-3 py-2.5 border-t border-gray-100 dark:border-gray-800 first:border-t-0">
					<span class="size-8 rounded-full bg-brand-100 text-brand-700 dark:bg-brand-900 dark:text-brand-200 text-[11px] font-semibold inline-flex items-center justify-center flex-none">{initials(m.user_id)}</span>
					<span class="flex-1 min-w-0 text-sm truncate">{nameOf(m.user_id)}</span>
					{#if m.role === 'owner'}
						<span class="text-[11px] font-medium px-2 py-0.5 rounded-md bg-brand-50 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300">Owner</span>
					{:else if m.role === 'admin'}
						<span class="text-[11px] font-medium px-2 py-0.5 rounded-md bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300">Admin</span>
					{/if}

					{#if lastOwner}
						<span class="text-[13px] text-gray-400 flex items-center gap-1.5 px-1" title="The last owner cannot be demoted or removed">
							<Icon name="lock" size={13} /> Owner
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
								<DropdownMenu.Item class="text-red-600 dark:text-red-400" onSelect={() => void remove(m.user_id)}>
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
						{addUserId ? nameOf(addUserId) : candidates.length ? 'Add a user by name…' : 'No more users to add'}
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
				class="text-sm font-medium px-4 py-2 rounded-lg bg-brand-900 text-white hover:bg-brand-800 dark:bg-brand-800 dark:hover:bg-brand-700 disabled:opacity-50 transition"
				disabled={busy || !addUserId}
				onclick={() => void add()}
			>
				Add
			</button>
		</div>
	{/if}
</div>
