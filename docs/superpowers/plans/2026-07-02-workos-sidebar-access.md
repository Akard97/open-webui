# WorkOS Sidebar-Integrated Access Management — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retire the Access console page; move workspace visibility, restricted-workspace membership, and team management into sidebar menus (hover kebab + right-click) that open two shadcn dialogs.

**Architecture:** Two new dialog components (`TeamSettingsDialog`, `WorkspaceSettingsDialog`) mounted in `WorkOSApp.svelte`, driven by two new `openModal` kinds. Sidebar workspace rows and the team card get shadcn `DropdownMenu` (kebab) + `ContextMenu` (right-click) with a shared action list. Console frontend deleted; backend untouched.

**Tech Stack:** Svelte 5 (legacy-mode `$:` reactivity + `onclick` event syntax — match existing files exactly), shadcn-svelte (bits-ui), Tailwind, svelte-sonner toasts, vitest.

**Spec:** `docs/superpowers/specs/2026-07-02-workos-sidebar-access-design.md` — read it first.

## Global Constraints

- Frontend only. **No backend changes.** `GET /access/overview` endpoint and `backend/open_webui/test/workos/test_router_access_overview.py` stay untouched.
- Server stays authoritative; every UI gate is a cosmetic mirror. Mutations use existing `api.ts` functions only.
- Design: professional, restrained, **not colorful** — neutral gray Tailwind palette (`gray-*`), near-black primary buttons (`bg-gray-900 text-white hover:bg-gray-800 dark:bg-gray-100 dark:text-gray-900 dark:hover:bg-gray-200`), red reserved for danger. No `brand-*` and no `amber-*` classes in the new components.
- Copy: sentence case, no exclamation marks. Destructive confirm wording is pinned in Task 4 — copy it verbatim.
- All new prose/code comments explain constraints, not narration.
- Working directory: repo root `C:\Projects\open-webui`. Frontend verification commands:
  - Type check: `npm run check` (slow; run at the listed checkpoints, not every step)
  - Unit tests: `npx vitest run src/lib/components/workos/lib`
- Do NOT start a Vite dev server — the user runs their own hot-reload server (standing rule).
- Icon component: `workos/ui/Icon.svelte` (`<Icon name="lock" size={13} />`). Names used in this plan (`lock`, `eye`, `settings`, `plus`, `more-horizontal`, `users`, `user-plus`, `x`, `pencil`, `archive`, `trash`, `chevron-down`, `chevron-right`, `layers`) all exist today.

---

### Task 1: Add shadcn-svelte `context-menu` component

**Files:**
- Create: `src/lib/components/ui/context-menu/` (CLI-generated)

**Interfaces:**
- Produces: `import * as ContextMenu from '$lib/components/ui/context-menu';` with `ContextMenu.Root`, `.Trigger`, `.Content`, `.Item`, `.Separator` — consumed by Task 5.

- [ ] **Step 1: Add the component via CLI**

Run: `npx shadcn-svelte@latest add context-menu --yes`

Expected: creates `src/lib/components/ui/context-menu/index.ts` plus `context-menu-*.svelte` files. If the CLI errors, invoke the `shadcn-svelte` skill for the project-specific procedure instead of hand-writing the component.

- [ ] **Step 2: Verify the barrel exports**

Run: `Get-Content src/lib/components/ui/context-menu/index.ts`
Expected: exports including `Root`, `Trigger`, `Content`, `Item`, `Separator`.

- [ ] **Step 3: Type check**

Run: `npm run check`
Expected: passes with no new errors (pre-existing error count unchanged).

- [ ] **Step 4: Commit**

```powershell
git add src/lib/components/ui/context-menu
git commit -m "feat(workos): add shadcn context-menu primitive"
```

---

### Task 2: New modal kinds in the store

**Files:**
- Modify: `src/lib/components/workos/lib/store.ts:20-24`

**Interfaces:**
- Produces: `ModalRequest` union members `{ kind: 'team-settings'; teamId: string }` and `{ kind: 'workspace-settings'; workspaceId: string }` — consumed by Tasks 4–6.
- Note: the legacy `{ kind: 'members'; teamId: string }` member **stays for now** (ModalHost still renders it); it is deleted in Task 7.

- [ ] **Step 1: Extend the union**

In `store.ts` replace:

```ts
export type ModalRequest =
	| { kind: 'team' }
	| { kind: 'workspace'; teamId: string }
	| { kind: 'workstream'; workspaceId: string }
	| { kind: 'members'; teamId: string };
```

with:

```ts
export type ModalRequest =
	| { kind: 'team' }
	| { kind: 'workspace'; teamId: string }
	| { kind: 'workstream'; workspaceId: string }
	| { kind: 'members'; teamId: string }
	| { kind: 'team-settings'; teamId: string }
	| { kind: 'workspace-settings'; workspaceId: string };
```

- [ ] **Step 2: Commit**

```powershell
git add src/lib/components/workos/lib/store.ts
git commit -m "feat(workos): modal kinds for team/workspace settings dialogs"
```

(No check run needed — additive union change; Task 4's checkpoint covers it.)

---

### Task 3: `lib/members.ts` — surviving pure helpers (TDD)

**Files:**
- Create: `src/lib/components/workos/lib/members.ts`
- Test: `src/lib/components/workos/lib/members.test.ts`

**Interfaces:**
- Produces (exact signatures, consumed by Tasks 4–5):
  - `addableUsers(roster: { id: string; name: string }[], members: Member[]): { id: string; name: string }[]`
  - `addableWorkspaceMembers(teamMembers: Member[], wsMembers: Member[]): Member[]`
  - `isLastOwner(ownerIds: string[], userId: string): boolean`
- Note: this duplicates three helpers from `lib/accessConsole.ts` for one transient window; `accessConsole.ts` (and its console-only `filterOverview`) is deleted whole in Task 7. Do not import `accessConsole.ts` from any new file.

- [ ] **Step 1: Write the failing test**

Create `src/lib/components/workos/lib/members.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import { addableUsers, addableWorkspaceMembers, isLastOwner } from './members';
import type { Member } from './types';

const member = (user_id: string, role: string): Member =>
	({ id: `m-${user_id}`, user_id, role, created_at: 0 }) as Member;

describe('addableUsers', () => {
	it('excludes existing members from the roster', () => {
		const roster = [
			{ id: 'u1', name: 'Lara' },
			{ id: 'u2', name: 'Yusuf' }
		];
		expect(addableUsers(roster, [member('u1', 'owner')])).toEqual([{ id: 'u2', name: 'Yusuf' }]);
		expect(addableUsers(roster, [])).toHaveLength(2);
	});
});

describe('addableWorkspaceMembers', () => {
	it('offers team members not yet on the workspace', () => {
		const team = [member('u1', 'owner'), member('u2', 'member')];
		const ws = [member('u1', 'admin')];
		expect(addableWorkspaceMembers(team, ws).map((m) => m.user_id)).toEqual(['u2']);
	});
	it('empty when everyone is already added', () => {
		const team = [member('u1', 'owner')];
		expect(addableWorkspaceMembers(team, [member('u1', 'admin')])).toEqual([]);
	});
});

describe('isLastOwner', () => {
	it('true only for the sole owner', () => {
		expect(isLastOwner(['u1'], 'u1')).toBe(true);
		expect(isLastOwner(['u1'], 'u2')).toBe(false);
		expect(isLastOwner(['u1', 'u2'], 'u1')).toBe(false);
		expect(isLastOwner([], 'u1')).toBe(false);
	});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/lib/components/workos/lib/members.test.ts`
Expected: FAIL — cannot resolve `./members`.

- [ ] **Step 3: Write the implementation**

Create `src/lib/components/workos/lib/members.ts`:

```ts
import type { Member } from './types';

// Pure helpers for the sidebar access dialogs. The server stays the authority
// on every rule mirrored here (last-owner guard, membership checks); these
// only shape the UI (picker candidates, pre-emptively disabled controls).

// App users not yet on the team — candidates for the team add-member picker.
export function addableUsers(
	roster: { id: string; name: string }[],
	members: Member[]
): { id: string; name: string }[] {
	const existing = new Set(members.map((m) => m.user_id));
	return roster.filter((u) => !existing.has(u.id));
}

// Team members not yet on the restricted workspace — candidates for the
// workspace add-member picker. Sourced from the team (never the app roster):
// the backend does not validate the target is a team member, so the UI
// enforces the sane subset.
export function addableWorkspaceMembers(teamMembers: Member[], wsMembers: Member[]): Member[] {
	const existing = new Set(wsMembers.map((m) => m.user_id));
	return teamMembers.filter((m) => !existing.has(m.user_id));
}

// UI hint mirroring the server's is_last_owner guard: true when `userId` is
// the sole owner, so demote/remove controls can disable pre-emptively.
export function isLastOwner(ownerIds: string[], userId: string): boolean {
	return ownerIds.length === 1 && ownerIds[0] === userId;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npx vitest run src/lib/components/workos/lib`
Expected: `members.test.ts` PASS (and existing suites still green, including the old `accessConsole.test.ts` — untouched until Task 7).

- [ ] **Step 5: Commit**

```powershell
git add src/lib/components/workos/lib/members.ts src/lib/components/workos/lib/members.test.ts
git commit -m "feat(workos): extract member-picker helpers for sidebar access dialogs"
```

---

### Task 4: `TeamSettingsDialog.svelte` + mount

**Files:**
- Create: `src/lib/components/workos/chrome/access/TeamSettingsDialog.svelte`
- Modify: `src/lib/components/workos/WorkOSApp.svelte` (mount only — imports + one line next to `<ModalHost />`)

**Interfaces:**
- Consumes: `openModal` kind `'team-settings'` (Task 2); `addableUsers`, `isLastOwner` from `lib/members` (Task 3); existing `api.listTeamMembers/listAllUsers/addTeamMember/updateTeamMember/removeTeamMember/updateTeam/deleteTeam`; store exports `token()`, `teams`, `roles`, `directory`, `initials(id)`, `loadBootstrap()`, `reloadDirectory()`.
- Produces: a self-opening dialog — any code can `openModal.set({ kind: 'team-settings', teamId })` (Task 5 does).

- [ ] **Step 1: Create the component**

Create `src/lib/components/workos/chrome/access/TeamSettingsDialog.svelte`:

```svelte
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
	<Dialog.Content class="max-w-lg">
		<div class="flex items-center gap-3">
			<div class="size-9 rounded-lg bg-gray-900 text-white dark:bg-gray-100 dark:text-gray-900 flex items-center justify-center text-sm font-semibold flex-none">
				{(team?.key || team?.name || '?').trim().slice(0, 1).toUpperCase()}
			</div>
			<div class="flex-1 min-w-0">
				<Dialog.Title>Team settings</Dialog.Title>
				<Dialog.Description class="truncate">
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
					<div class="flex flex-col max-h-80 overflow-y-auto">
						{#each members as m (m.user_id)}
							{@const lastOwner = isLastOwner(ownerIds, m.user_id)}
							<div class="flex items-center gap-3 py-2.5 border-t border-gray-100 dark:border-gray-800 first:border-t-0">
								<span class="size-8 rounded-full bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300 text-[11px] font-semibold inline-flex items-center justify-center flex-none">{initials(m.user_id)}</span>
								<span class="flex-1 min-w-0 text-sm truncate">{nameOf(m.user_id)}</span>
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

					<div class="flex items-center gap-2 mt-3 pt-3 border-t border-gray-100 dark:border-gray-800">
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
					<div class="flex flex-col gap-4 pt-1">
						<div>
							<div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">Team name</div>
							<div class="flex items-center gap-2">
								<input
									class="flex-1 text-sm px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-800 bg-transparent outline-none focus:border-gray-400 dark:focus:border-gray-600"
									bind:value={nameDraft}
									onkeydown={(e) => { if (e.key === 'Enter') void saveRename(); }}
								/>
								<button
									class="text-sm px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-850 transition disabled:opacity-50"
									disabled={busy || !nameDraft.trim() || nameDraft.trim() === team?.name}
									onclick={() => void saveRename()}
								>
									Save
								</button>
							</div>
						</div>

						<div class="flex items-center justify-between gap-3 rounded-lg border border-gray-200 dark:border-gray-800 px-3 py-2.5">
							<div class="min-w-0">
								<div class="text-sm font-medium flex items-center gap-1.5">
									<span class="size-2 rounded-full {team?.archived ? 'bg-gray-400' : 'bg-green-500'} flex-none"></span>
									{team?.archived ? 'Archived' : 'Active'}
								</div>
								<div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Archiving hides the team without deleting anything.</div>
							</div>
							<button
								class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 inline-flex items-center gap-1.5 hover:bg-gray-50 dark:hover:bg-gray-850 transition disabled:opacity-50 flex-none"
								disabled={busy}
								onclick={() => void toggleArchived()}
							>
								<Icon name="archive" size={14} /> {team?.archived ? 'Unarchive' : 'Archive'}
							</button>
						</div>

						<div class="flex items-center gap-3 rounded-lg border border-red-200 dark:border-red-900/60 px-3 py-2.5">
							<div class="flex-1 min-w-0">
								<div class="text-sm font-medium text-red-600 dark:text-red-400">Delete team</div>
								<div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Removes all workspaces, workstreams and tasks. Cannot be undone.</div>
							</div>
							<button
								class="text-sm px-3 py-1.5 rounded-lg border border-red-200 dark:border-red-900/60 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 transition flex-none"
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
	<Dialog.Content class="max-w-md">
		<Dialog.Title>Delete team?</Dialog.Title>
		<Dialog.Description>
			This permanently deletes <span class="font-medium">{team?.name ?? ''}</span> with all of its
			workspaces, workstreams and tasks. This cannot be undone.
		</Dialog.Description>
		<div class="flex justify-end gap-2 mt-4">
			<button class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-850 transition" onclick={() => (confirmDelete = false)}>Cancel</button>
			<button class="text-sm font-medium px-3.5 py-1.5 rounded-lg bg-red-600 text-white hover:bg-red-700 transition" disabled={busy} onclick={() => void deleteTeam()}>Delete team</button>
		</div>
	</Dialog.Content>
</Dialog.Root>
```

- [ ] **Step 2: Mount in WorkOSApp**

In `src/lib/components/workos/WorkOSApp.svelte` add the import next to the `ModalHost` import:

```ts
import TeamSettingsDialog from './chrome/access/TeamSettingsDialog.svelte';
```

and render it next to `<ModalHost />`:

```svelte
	<ModalHost />
	<TeamSettingsDialog />
```

- [ ] **Step 3: Type check**

Run: `npm run check`
Expected: passes with no new errors.

- [ ] **Step 4: Commit**

```powershell
git add src/lib/components/workos/chrome/access/TeamSettingsDialog.svelte src/lib/components/workos/WorkOSApp.svelte
git commit -m "feat(workos): team settings dialog (members roster + general tab)"
```

---

### Task 5: `WorkspaceSettingsDialog.svelte` + `RestrictConfirmDialog.svelte` + mount

**Files:**
- Create: `src/lib/components/workos/chrome/access/RestrictConfirmDialog.svelte`
- Create: `src/lib/components/workos/chrome/access/WorkspaceSettingsDialog.svelte`
- Modify: `src/lib/components/workos/WorkOSApp.svelte` (mount)

**Interfaces:**
- Consumes: `openModal` kind `'workspace-settings'` (Task 2); `addableWorkspaceMembers` from `lib/members` (Task 3); `api.updateWorkspace/deleteWorkspace/listWorkspaceMembers/listTeamMembers/listAllUsers/addWorkspaceMember/updateWorkspaceMember/removeWorkspaceMember`.
- Produces:
  - `RestrictConfirmDialog` props: `open: boolean`, `name: string`, `busy: boolean`, `onCancel: () => void`, `onConfirm: () => void` — reused by Task 6's quick-flip.
  - Dialog opens via `openModal.set({ kind: 'workspace-settings', workspaceId })`.

- [ ] **Step 1: Create the shared restrict-confirm dialog**

Create `src/lib/components/workos/chrome/access/RestrictConfirmDialog.svelte`. The wording is load-bearing (mirrors the server's eviction behavior) — keep it verbatim:

```svelte
<script lang="ts">
	import * as Dialog from '$lib/components/ui/dialog';

	export let open = false;
	export let name = '';
	export let busy = false;
	export let onCancel: () => void;
	export let onConfirm: () => void;
</script>

<Dialog.Root {open} onOpenChange={(o) => { if (!o) onCancel(); }}>
	<Dialog.Content class="max-w-md">
		<Dialog.Title>Restrict this workspace?</Dialog.Title>
		<Dialog.Description>
			<span class="font-medium">{name}</span> will only be visible to its explicit
			members and its creator. Everyone else on the team loses access immediately — it disappears
			from their sidebar and any live sessions are disconnected from its rooms. If you are not a
			member or the creator, that includes you. You can add members afterwards from workspace
			settings.
		</Dialog.Description>
		<div class="flex justify-end gap-2 mt-4">
			<button class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-850 transition" onclick={onCancel}>Cancel</button>
			<button
				class="text-sm font-medium px-3.5 py-1.5 rounded-lg bg-red-600 text-white hover:bg-red-700 transition disabled:opacity-50"
				disabled={busy}
				onclick={onConfirm}
			>
				Restrict workspace
			</button>
		</div>
	</Dialog.Content>
</Dialog.Root>
```

- [ ] **Step 2: Create the workspace settings dialog**

Create `src/lib/components/workos/chrome/access/WorkspaceSettingsDialog.svelte`:

```svelte
<script lang="ts">
	import { get } from 'svelte/store';
	import { toast } from 'svelte-sonner';
	import * as Dialog from '$lib/components/ui/dialog';
	import * as Select from '$lib/components/ui/select';
	import Icon from '../../ui/Icon.svelte';
	import RestrictConfirmDialog from './RestrictConfirmDialog.svelte';
	import * as api from '../../lib/api';
	import {
		openModal, token, teams, workspaces, directory, initials, loadBootstrap
	} from '../../lib/store';
	import { addableWorkspaceMembers } from '../../lib/members';
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
	<Dialog.Content class="max-w-lg">
		<div class="flex items-center gap-3">
			<div class="size-9 rounded-lg bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 flex items-center justify-center flex-none">
				<Icon name="layers" size={16} />
			</div>
			<div class="flex-1 min-w-0">
				<Dialog.Title>Workspace settings</Dialog.Title>
				<Dialog.Description class="truncate">{ws?.name ?? ''}{team ? ` · ${team.name}` : ''}</Dialog.Description>
			</div>
		</div>

		<div class="flex flex-col gap-4">
			<div>
				<div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">Visibility</div>
				<div class="grid grid-cols-2 gap-2">
					<button
						class="rounded-lg border p-3 text-left transition disabled:opacity-60 {ws?.visibility === 'team'
							? 'border-gray-900 dark:border-gray-100 ring-1 ring-gray-900 dark:ring-gray-100 bg-gray-50 dark:bg-gray-900'
							: 'border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'}"
						disabled={busy}
						onclick={() => requestVisibility('team')}
					>
						<div class="text-sm font-medium flex items-center gap-1.5"><Icon name="users" size={14} /> Team-visible</div>
						<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">Everyone on the team can see it.</div>
					</button>
					<button
						class="rounded-lg border p-3 text-left transition disabled:opacity-60 {ws?.visibility === 'restricted'
							? 'border-gray-900 dark:border-gray-100 ring-1 ring-gray-900 dark:ring-gray-100 bg-gray-50 dark:bg-gray-900'
							: 'border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'}"
						disabled={busy}
						onclick={() => requestVisibility('restricted')}
					>
						<div class="text-sm font-medium flex items-center gap-1.5"><Icon name="lock" size={14} /> Restricted</div>
						<div class="text-xs text-gray-500 dark:text-gray-400 mt-1">Only explicit members and the creator.</div>
					</button>
				</div>
			</div>

			{#if ws?.visibility === 'restricted'}
				<div>
					<div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">
						Members{loaded ? ` · ${wsMembers.length}` : ''}
					</div>
					<div class="rounded-lg border border-gray-200 dark:border-gray-800 px-3 py-1">
						{#if !loaded}
							<div class="py-2 text-xs text-gray-400">Loading…</div>
						{:else}
							{#each wsMembers as m (m.user_id)}
								<div class="flex items-center gap-2.5 py-1.5 border-t border-gray-100 dark:border-gray-800 first:border-t-0">
									<span class="size-6 rounded-full bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-300 text-[10px] font-semibold inline-flex items-center justify-center flex-none">{initials(m.user_id)}</span>
									<span class="flex-1 min-w-0 text-sm truncate">{nameOf(m.user_id)}</span>
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
								<div class="text-[13px] text-gray-400 py-2">No explicit members — only the creator and admins can see this.</div>
							{/each}
							<div class="flex items-center gap-2 py-2 border-t border-gray-100 dark:border-gray-800">
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
				<div class="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5">Workspace name</div>
				<div class="flex items-center gap-2">
					<input
						class="flex-1 text-sm px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-800 bg-transparent outline-none focus:border-gray-400 dark:focus:border-gray-600"
						bind:value={nameDraft}
						onkeydown={(e) => { if (e.key === 'Enter') void saveRename(); }}
					/>
					<button
						class="text-sm px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-850 transition disabled:opacity-50"
						disabled={busy || !nameDraft.trim() || nameDraft.trim() === ws?.name}
						onclick={() => void saveRename()}
					>
						Save
					</button>
				</div>
			</div>

			<div class="flex items-center gap-3 rounded-lg border border-red-200 dark:border-red-900/60 px-3 py-2.5">
				<div class="flex-1 min-w-0">
					<div class="text-sm font-medium text-red-600 dark:text-red-400">Delete workspace</div>
					<div class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">Removes all workstreams and tasks. Cannot be undone.</div>
				</div>
				<button
					class="text-sm px-3 py-1.5 rounded-lg border border-red-200 dark:border-red-900/60 text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/40 transition flex-none"
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
	<Dialog.Content class="max-w-md">
		<Dialog.Title>Delete workspace?</Dialog.Title>
		<Dialog.Description>
			This permanently deletes <span class="font-medium">{ws?.name ?? ''}</span> with all of its
			workstreams and tasks. This cannot be undone.
		</Dialog.Description>
		<div class="flex justify-end gap-2 mt-4">
			<button class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-850 transition" onclick={() => (confirmDelete = false)}>Cancel</button>
			<button class="text-sm font-medium px-3.5 py-1.5 rounded-lg bg-red-600 text-white hover:bg-red-700 transition" disabled={busy} onclick={() => void deleteWorkspace()}>Delete workspace</button>
		</div>
	</Dialog.Content>
</Dialog.Root>
```

- [ ] **Step 3: Mount in WorkOSApp**

In `src/lib/components/workos/WorkOSApp.svelte`:

```ts
import WorkspaceSettingsDialog from './chrome/access/WorkspaceSettingsDialog.svelte';
```

```svelte
	<ModalHost />
	<TeamSettingsDialog />
	<WorkspaceSettingsDialog />
```

- [ ] **Step 4: Type check**

Run: `npm run check`
Expected: passes with no new errors.

- [ ] **Step 5: Commit**

```powershell
git add src/lib/components/workos/chrome/access src/lib/components/workos/WorkOSApp.svelte
git commit -m "feat(workos): workspace settings dialog (visibility, members, danger zone)"
```

---

### Task 6: Sidebar integration — menus, lock badge, team settings entry

**Files:**
- Modify: `src/lib/components/workos/chrome/Sidebar.svelte`

**Interfaces:**
- Consumes: `openModal.set({ kind: 'team-settings' | 'workspace-settings', ... })` (Tasks 4–5); `RestrictConfirmDialog` (Task 5); `ContextMenu` (Task 1); existing `canManageMembers`, `canCreateWorkspace`, `canUseAdmin` predicates.
- Produces: the only UI entry points for access management. Shield buttons (Access console) are removed here.

- [ ] **Step 1: Rework Sidebar.svelte**

Apply all of the following to `src/lib/components/workos/chrome/Sidebar.svelte`:

**(a) Imports** — replace the roles import line and add menus + api types:

```ts
import * as DropdownMenu from '$lib/components/ui/dropdown-menu';
import * as ContextMenu from '$lib/components/ui/context-menu';
import RestrictConfirmDialog from './access/RestrictConfirmDialog.svelte';
import { toast } from 'svelte-sonner';
import { canUseAdmin, canCreateWorkspace, canManageMembers } from '../lib/roles';
import type { Workspace } from '../lib/types';
```

(`canUseAccessConsole` is gone from this file; also add `loadBootstrap` to the existing `../lib/store` import list.)

**(b) Script additions** — after the `myRole` reactive line add:

```ts
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
```

**(c) Collapsed rail** — delete the whole `{#if canUseAccessConsole($user, $roles)} … shield … {/if}` block (lines 95–99 in the current file).

**(d) Team switcher menu** — replace the "Manage members" item:

```svelte
						{#if canManage && $currentTeamId}
							<button class="flex items-center gap-2 w-full px-2.5 h-8 rounded-lg text-sm hover:bg-gray-100 dark:hover:bg-gray-850" onclick={() => { openModal.set({ kind: 'team-settings', teamId: $currentTeamId }); teamMenuOpen = false; }}>
								<Icon name="settings" size={14} /> Team settings…
							</button>
						{/if}
```

(The gate changes from `canManageMembers(myRole)` to `canManage` so app-admins see it too.)

**(e) Team card right-click** — wrap the team switcher `<button class="group w-full flex flex-col …">` (the card, not the dropdown) in a context menu:

```svelte
			<ContextMenu.Root>
				<ContextMenu.Trigger class="block w-full">
					<!-- existing team card <button> unchanged -->
				</ContextMenu.Trigger>
				{#if canManage && $currentTeamId}
					<ContextMenu.Content class="w-52">
						<ContextMenu.Item onSelect={() => openModal.set({ kind: 'team-settings', teamId: $currentTeamId })}>
							<span class="inline-flex items-center gap-2"><Icon name="settings" size={14} /> Team settings…</span>
						</ContextMenu.Item>
					</ContextMenu.Content>
				{/if}
			</ContextMenu.Root>
```

**(f) Workspace rows** — replace the current `{#each teamWorkspaces as ws (ws.id)}` block body with a row that has: right-click context menu, hover kebab, lock badge. The expand button loses `w-full` and becomes `flex-1` so the kebab can sit beside it (no nested buttons):

```svelte
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
```

**(g) Footer** — delete the `{#if canUseAccessConsole($user, $roles)} … shield … {/if}` block (lines 248–252 in the current file).

**(h) Restrict confirm** — at the very end of the file (outside both `{#if}` branches, after the closing `{/if}`):

```svelte
<RestrictConfirmDialog
	open={pendingRestrict !== null}
	name={pendingRestrict?.name ?? ''}
	busy={false}
	onCancel={() => (pendingRestrict = null)}
	onConfirm={() => pendingRestrict && void restrictWorkspace(pendingRestrict)}
/>
```

- [ ] **Step 2: Type check + unit tests**

Run: `npm run check`
Expected: passes with no new errors.
Run: `npx vitest run src/lib/components/workos/lib`
Expected: all green.

- [ ] **Step 3: Commit**

```powershell
git add src/lib/components/workos/chrome/Sidebar.svelte
git commit -m "feat(workos): sidebar access menus - kebab + context menu, lock badge, team settings entry"
```

---

### Task 7: Delete the Access console frontend

**Files:**
- Delete: `src/lib/components/workos/views/access/` (all 6 files)
- Delete: `src/lib/components/workos/lib/accessConsole.ts`, `src/lib/components/workos/lib/accessConsole.test.ts`
- Modify: `src/lib/components/workos/WorkOSApp.svelte`, `src/lib/components/workos/lib/store.ts`, `src/lib/components/workos/views/ModalHost.svelte`, `src/lib/components/workos/lib/roles.ts`, `src/lib/components/workos/lib/roles.test.ts`, `src/lib/components/workos/lib/api.ts`, `src/lib/components/workos/lib/types.ts`

Backend files are NOT touched (`GET /access/overview` + `test_router_access_overview.py` stay).

- [ ] **Step 1: Delete console files**

```powershell
git rm -r src/lib/components/workos/views/access
git rm src/lib/components/workos/lib/accessConsole.ts src/lib/components/workos/lib/accessConsole.test.ts
```

- [ ] **Step 2: WorkOSApp.svelte**

Remove:
- `import AccessConsole from './views/access/AccessConsole.svelte';`
- `canUseAccessConsole` from the roles import (keep `canUseAdmin`)
- the guard line: `$: if ($view === 'access' && $teams.length && !canUseAccessConsole($user, $roles)) view.set('board');`
- the `{:else if $view === 'access'}<AccessConsole />` branch
- `roles` from the store import if now unused in this file (check remaining usages).

- [ ] **Step 3: store.ts**

- `ViewKey`: remove `'access'` →
  ```ts
  export type ViewKey = 'board' | 'list' | 'admin' | 'inbox' | 'mywork' | 'calendar' | 'overview';
  ```
- `ModalRequest`: remove the `| { kind: 'members'; teamId: string }` member (the two settings kinds from Task 2 stay).

- [ ] **Step 4: ModalHost.svelte**

Remove the `members` modal entirely:
- the members state block (`teamMembers`, `allUsers`, `addUserId`, `addRole`) and the `r.kind === 'members'` branch in `reset`
- `addMember`, `changeRole`, `removeMember` functions
- the `{#if req.kind === 'members'} … {:else}` template branch (keep the create-form branch as the only content)
- `members: 'Team members'` from `TITLES`
- now-unused imports (`canManageMembers`, `directory`, `reloadDirectory`, `TeamRole` — verify each is actually unused before removing; `svelte-check` will confirm).

- [ ] **Step 5: roles.ts + roles.test.ts**

- Delete the `canUseAccessConsole` function (roles.ts:31-41 including its comment).
- In `roles.test.ts`: remove `canUseAccessConsole` from the import and delete its test block (lines 52-61 area — the `describe`/`it`s exercising it).

- [ ] **Step 6: api.ts + types.ts**

- `api.ts`: delete the `// Access console` section (the `accessOverview` export) and remove `AccessTeamOverview` from the types import.
- `types.ts`: delete `AccessWorkspaceSummary` and `AccessTeamOverview` interfaces (lines 160-178 including the comment).

- [ ] **Step 7: Sweep for stragglers**

Run: `Select-String -Path src -Pattern "accessConsole|AccessConsole|canUseAccessConsole|AccessTeamOverview|AccessWorkspaceSummary|accessOverview|'access'" -Recurse` — via Grep tool over `src/`.
Expected: zero hits inside `src/lib/components/workos/` (a `'access'` string elsewhere in the repo is unrelated — only WorkOS files matter).

- [ ] **Step 8: Type check + unit tests**

Run: `npm run check`
Expected: passes with no new errors.
Run: `npx vitest run src/lib/components/workos/lib`
Expected: all green — `members.test.ts` + `roles.test.ts` (minus deleted block) + the rest.

- [ ] **Step 9: Commit**

```powershell
git add -A src/lib/components/workos
git commit -m "refactor(workos): remove access console frontend - superseded by sidebar dialogs"
```

---

### Task 8: Sync the access-control reference doc

**Files:**
- Modify: `docs/superpowers/specs/2026-06-26-workos-access-control.md` (§6 Frontend consumption + header changelog)

- [ ] **Step 1: Update §6 and the header**

In the HTML comment header, add a dated line:

```
2026-07-02 (later still): Access console page REMOVED (frontend only) — replaced by
sidebar-integrated access management: kebab/right-click menus on workspace rows and
the team card opening TeamSettingsDialog / WorkspaceSettingsDialog
(chrome/access/*). GET /access/overview endpoint + tests kept (currently no
frontend caller). §6 updated.
```

In §6:
- Replace the "Access console (`views/access/`, view key `'access'`, sidebar shield button)" bullet with:

```
- **Sidebar access management** (`chrome/access/`, since 2026-07-02, replaces the Access
  console page): workspace rows and the team card carry kebab (⋯) + right-click menus,
  gated by `canManageMembers(teamRole) || app-admin`, opening `TeamSettingsDialog`
  (members roster + rename/archive/delete, owner-only General tab) and
  `WorkspaceSettingsDialog` (visibility flip + restricted-members + rename/delete).
  All mutations go through the existing gated endpoints — role gates, the last-owner
  guard, and realtime emit/eviction come from the server unchanged. UI mirrors:
  owner-grant selects disabled for non-owners, last-owner row locked,
  restricted-workspace add-picker sourced from team members only, and the
  `team→restricted` flip sits behind a destructive-confirm dialog
  (`RestrictConfirmDialog`, shared by the dialog and the sidebar quick-flip). The flip
  can evict the acting admin's own client (non-member, non-creator) — the dialog
  detects the workspace vanishing from bootstrap and closes. Restricted rows show a
  lock badge (visibility ships in `/bootstrap`).
```

- In the `lib/roles.ts` predicates bullet: remove the `canUseAccessConsole` mention; fix the stale claim that `canManageWorkspace` is "defined+tested but **unused** (dead predicate)" — it is used by `canEditTask`/`canEditSubtask` (roles.ts:68).
- §4 Access console table: add a note that the endpoint currently has **no frontend caller** (kept deliberately).

- [ ] **Step 2: Commit**

```powershell
git add docs/superpowers/specs/2026-06-26-workos-access-control.md
git commit -m "docs(workos): sync access-control reference with sidebar access management"
```

---

### Task 9: Final verification

- [ ] **Step 1: Full frontend test run**

Run: `npx vitest run src/lib/components/workos`
Expected: all suites green.

- [ ] **Step 2: Full type check**

Run: `npm run check`
Expected: no new errors vs. the branch baseline.

- [ ] **Step 3: Manual browser smoke (user's server — do not start one)**

Ask the user to smoke on their running Vite server:
1. Sidebar: hover a workspace row → kebab appears; right-click → same menu; restricted rows show lock.
2. Workspace settings: flip visibility both ways (restrict shows confirm), add/remove restricted member, rename, delete (on a throwaway workspace).
3. Team settings: roster add/change-role/remove, last-owner locked, non-owner sees no General tab, rename/archive/delete (throwaway team).
4. Non-manager account: no kebab, no context menu items, no shield anywhere.
5. Second browser session as a plain member: restrict a workspace they can see → it disappears live from their sidebar.
