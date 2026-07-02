# WorkOS Responsive / Mobile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make WorkOS fully usable on phones: bottom-tab shell with a workstream drawer, per-view native adaptations, full-screen task detail.

**Architecture:** Approach B from the spec (docs/superpowers/specs/2026-07-02-workos-responsive-design.md): reuse OWUI's global `mobile` store (`window.innerWidth < 768`, maintained in `src/routes/+layout.svelte`) for structural swaps (`{#if $mobile}` branches), and plain Tailwind `max-md:`/`md:` classes for cosmetic stacking. Desktop (≥768px) rendering is byte-identical except where noted (pure extractions).

**Tech Stack:** Svelte 5 (legacy `$:` reactivity + new `onclick` event attrs — match surrounding style), Tailwind, shadcn-svelte dialogs (scoped to `.workos-root`), vitest for pure helpers.

## Global Constraints

- Frontend only. No backend/API changes.
- Desktop ≥768px must not change behavior; Task 1's extraction must be render-equivalent.
- `mobile` store import: `import { mobile } from '$lib/stores';` — never create a second viewport listener.
- Breakpoint is `md` (768px) everywhere; do not introduce other structural breakpoints.
- Do NOT start a Vite dev server (user runs their own hot-reload server — hard rule).
- Verification commands: `npx vitest run src/lib/components/workos` (all existing WorkOS tests must stay green) and `npm run check` (no NEW errors vs. before your change).
- Commit after every task with the message given in the task.
- Icons via the existing `ui/Icon.svelte` (`<Icon name="..." size={n} />`); names are feather-style, already used ones include `check`, `message-square`, `layers`, `settings`, `x`, `arrow-left`, `chevron-down`, `chevron-up`, `chevron-right`.

---

### Task 1: Extract TeamSwitcher + WorkstreamTree from Sidebar

Pure refactor so the mobile drawer (Task 2) can reuse the team switcher and workstream tree without duplication. Desktop must render identically.

**Files:**
- Create: `src/lib/components/workos/chrome/TeamSwitcher.svelte`
- Create: `src/lib/components/workos/chrome/WorkstreamTree.svelte`
- Modify: `src/lib/components/workos/chrome/Sidebar.svelte`

**Interfaces:**
- Produces: `TeamSwitcher.svelte` (no props). `WorkstreamTree.svelte` with prop `export let onNavigate: () => void = () => {};` — called after a workstream is selected (Task 2's drawer passes its close function).

- [ ] **Step 1: Create `TeamSwitcher.svelte`**

Move the "Teams" block (currently `Sidebar.svelte` lines 194–248) plus its script state. Full file:

```svelte
<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import AssigneeAvatars from '../views/AssigneeAvatars.svelte';
	import * as ContextMenu from '$lib/components/ui/context-menu';
	import { get } from 'svelte/store';
	import * as api from '../lib/api';
	import { user } from '$lib/stores';
	import { canManageMembers } from '../lib/roles';
	import { teams, roles, currentTeam, currentTeamId, selectTeam, openModal, token } from '../lib/store';

	let teamMenuOpen = false;
	let teamMenuEl: HTMLElement;
	let memberIds: string[] = [];

	// Close the team switcher when clicking anywhere outside its container.
	function onWindowClick(e: MouseEvent): void {
		if (teamMenuOpen && teamMenuEl && !teamMenuEl.contains(e.target as Node)) teamMenuOpen = false;
	}

	$: myRole = $currentTeamId ? $roles[$currentTeamId] : undefined;
	// App-admins pass every server gate; the roles map may have no entry for them.
	$: canManage = $user?.role === 'admin' || canManageMembers(myRole);

	// Two-letter team mark (prefer the short key).
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

<div class="mt-4 px-[0.4375rem] relative text-gray-800 dark:text-gray-200" bind:this={teamMenuEl}>
	<div class="py-1.5 pl-2.5 text-xs font-medium text-gray-600 dark:text-gray-400">Team</div>
	<ContextMenu.Root>
		<ContextMenu.Trigger class="block w-full" disabled={!canManage}>
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
```

- [ ] **Step 2: Create `WorkstreamTree.svelte`**

Move the "Workspaces" block (currently `Sidebar.svelte` lines 250–336, minus the outer scroll container div), plus `wsActions`/visibility logic and the `.ws-tree` styles. Full file:

```svelte
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
	import {
		workspaces, workstreams, roles, currentTeamId, currentWorkstreamId,
		selectWorkstream, view, openModal, token, loadBootstrap, expandedWorkspaces
	} from '../lib/store';

	// Called after a workstream is picked — the mobile drawer closes itself here.
	export let onNavigate: () => void = () => {};

	$: teamWorkspaces = $workspaces.filter((w) => w.team_id === $currentTeamId);
	$: streamsByWs = (wsId: string) => $workstreams.filter((s) => s.workspace_id === wsId);
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
		<button class="z-10 mr-2 invisible group-hover:visible self-center p-0.5 hover:bg-gray-200 dark:hover:bg-gray-850 rounded-lg transition" title="New workspace" onclick={() => openModal.set({ kind: 'workspace', teamId: $currentTeamId })}>
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
				{#if $expandedWorkspaces[ws.id]}
					<div class="ws-tree">
						{#each streamsByWs(ws.id) as s (s.id)}
							<button
								class="ws-tree-item w-full flex items-center rounded-lg pl-2 pr-[11px] py-[6px] text-sm transition {$currentWorkstreamId === s.id ? 'bg-gray-100 dark:bg-gray-900 font-medium' : 'hover:bg-gray-100 dark:hover:bg-gray-900'}"
								onclick={() => { selectWorkstream(s.id); view.set('board'); onNavigate(); }}
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
```

Note the ONE functional addition vs. the original: `onNavigate()` after `selectWorkstream(...); view.set('board');` — defaults to a no-op, so desktop behavior is unchanged.

- [ ] **Step 3: Rewrite `Sidebar.svelte` to consume both**

The collapsed-rail branch (lines 92–144) is untouched. In the expanded branch, replace the Teams block with `<TeamSwitcher />` and the Workspaces tree content with `<WorkstreamTree />` (keeping the scroll container in Sidebar). Remove everything that moved: `AssigneeAvatars`, `ContextMenu`/`DropdownMenu` (dropdown only if now unused), `RestrictConfirmDialog`, `toast`, `api`, `get`, the `teamMenuOpen`/`teamMenuEl`/`memberIds`/`onWindowClick`/`loadMembers` state, `teamWorkspaces`/`streamsByWs`/`canManage`/`pendingRestrict`/`makeTeamVisible`/`restrictWorkspace`/`wsActions`, the `<svelte:window>` line, the trailing `<RestrictConfirmDialog …/>`, and the entire `<style>` block. Keep: `teamBadge` (the rail uses it), `myRole` only if still referenced (it is not — remove), `canUseAdmin`, `navCollapsed`, `view`, `unreadCount`, logos, `ThemeSwitcher`, `SidebarIcon`.

Resulting expanded branch skeleton (header + My Work/Inbox blocks unchanged, then):

```svelte
		<TeamSwitcher />

		<!-- Workspaces -->
		<div class="flex-1 overflow-y-auto scrollbar-hidden px-2 mt-4 pb-2">
			<WorkstreamTree />
		</div>

		<!-- Footer (unchanged) -->
```

And the script imports shrink to:

```svelte
<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import SidebarIcon from '$lib/components/icons/Sidebar.svelte';
	import ThemeSwitcher from '$lib/components/app/ThemeSwitcher.svelte';
	import TeamSwitcher from './TeamSwitcher.svelte';
	import WorkstreamTree from './WorkstreamTree.svelte';
	import { user } from '$lib/stores';
	import workosLogoDark from '../assets/workos-logo-dark.png';
	import workosLogoLight from '../assets/workos-logo-light.png';
	import { canUseAdmin } from '../lib/roles';
	import { currentTeam, view, unreadCount, navCollapsed } from '../lib/store';

	// Two-letter team mark for the collapsed rail (prefer the short key).
	$: teamBadge = (($currentTeam?.key || $currentTeam?.name || '?').trim().slice(0, 2)).toUpperCase();
</script>
```

- [ ] **Step 4: Verify**

Run: `npx vitest run src/lib/components/workos` — Expected: all pass (no tests touch Sidebar markup, this guards the lib).
Run: `npm run check` — Expected: no NEW errors (record the baseline count first with the same command before editing).

- [ ] **Step 5: Commit**

```bash
git add -A src/lib/components/workos docs
git commit -m "refactor(workos): extract TeamSwitcher + WorkstreamTree from Sidebar"
```

---

### Task 2: Mobile shell — BottomNav, NavDrawer, WorkOSApp wiring

**Files:**
- Modify: `src/lib/components/workos/lib/store.ts` (one store)
- Create: `src/lib/components/workos/chrome/BottomNav.svelte`
- Create: `src/lib/components/workos/chrome/NavDrawer.svelte`
- Modify: `src/lib/components/workos/WorkOSApp.svelte`

**Interfaces:**
- Consumes: `TeamSwitcher`, `WorkstreamTree` (`onNavigate` prop) from Task 1.
- Produces: `mobileNavOpen: Writable<boolean>` exported from `lib/store.ts` (BottomNav opens, NavDrawer closes, WorkOSApp force-closes on desktop resize).

- [ ] **Step 1: Add the drawer store**

In `lib/store.ts`, after the `navCollapsed` block (line ~55):

```ts
// Mobile Browse drawer (bottom-nav → workstream tree). Ephemeral by design.
export const mobileNavOpen: Writable<boolean> = writable(false);
```

- [ ] **Step 2: Create `BottomNav.svelte`**

```svelte
<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import { view, unreadCount, mobileNavOpen } from '../lib/store';

	// Workstream-scoped views (and admin, reached via the drawer) light up Browse.
	$: browseActive = ['board', 'list', 'calendar', 'overview', 'admin'].includes($view);
</script>

<nav class="flex-none flex border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 pb-[env(safe-area-inset-bottom)]">
	<button
		class="flex-1 flex flex-col items-center gap-0.5 py-2 text-[10px] font-medium {$view === 'mywork' ? 'text-primary' : 'text-gray-500 dark:text-gray-400'}"
		onclick={() => view.set('mywork')}
	>
		<Icon name="check" size={20} /> My Work
	</button>
	<button
		class="relative flex-1 flex flex-col items-center gap-0.5 py-2 text-[10px] font-medium {$view === 'inbox' ? 'text-primary' : 'text-gray-500 dark:text-gray-400'}"
		onclick={() => view.set('inbox')}
	>
		<Icon name="message-square" size={20} /> Inbox
		{#if $unreadCount > 0}
			<span class="absolute top-1.5 right-[32%] size-1.5 rounded-full bg-sky-500"></span>
		{/if}
	</button>
	<button
		class="flex-1 flex flex-col items-center gap-0.5 py-2 text-[10px] font-medium {browseActive ? 'text-primary' : 'text-gray-500 dark:text-gray-400'}"
		onclick={() => mobileNavOpen.set(true)}
	>
		<Icon name="layers" size={20} /> Browse
	</button>
</nav>
```

- [ ] **Step 3: Create `NavDrawer.svelte`**

```svelte
<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import ThemeSwitcher from '$lib/components/app/ThemeSwitcher.svelte';
	import TeamSwitcher from './TeamSwitcher.svelte';
	import WorkstreamTree from './WorkstreamTree.svelte';
	import { canUseAdmin } from '../lib/roles';
	import { user } from '$lib/stores';
	import { mobileNavOpen, view } from '../lib/store';

	const close = () => mobileNavOpen.set(false);
</script>

<svelte:window onkeydown={(e) => { if (e.key === 'Escape' && $mobileNavOpen) close(); }} />

{#if $mobileNavOpen}
	<div class="fixed inset-0 z-40">
		<button class="absolute inset-0 bg-black/40" aria-label="Close navigation" onclick={close}></button>
		<aside class="absolute inset-y-0 left-0 w-[82vw] max-w-[320px] flex flex-col bg-gray-50 dark:bg-gray-950 shadow-xl">
			<TeamSwitcher />
			<div class="flex-1 overflow-y-auto scrollbar-hidden px-2 mt-4 pb-2">
				<WorkstreamTree onNavigate={close} />
			</div>
			<div class="border-t border-gray-50 dark:border-gray-850/30 p-2 pb-[calc(0.5rem+env(safe-area-inset-bottom))] flex items-center gap-2 text-gray-800 dark:text-gray-200">
				{#if canUseAdmin($user)}
					<button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition" title="WorkOS admin" onclick={() => { view.set('admin'); close(); }}>
						<Icon name="settings" size={16} />
					</button>
				{/if}
				<ThemeSwitcher />
				<div class="flex-1"></div>
				<button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition" title="Close" onclick={close}>
					<Icon name="x" size={16} />
				</button>
			</div>
		</aside>
	</div>
{/if}
```

- [ ] **Step 4: Wire `WorkOSApp.svelte`**

Add imports and the resize guard to the script:

```ts
import BottomNav from './chrome/BottomNav.svelte';
import NavDrawer from './chrome/NavDrawer.svelte';
import { mobile } from '$lib/stores';   // merge into the existing $lib/stores import ({ user, mobile })
import { mobileNavOpen } from './lib/store';  // merge into the existing ./lib/store import

// Crossing back to desktop must not leave a phantom drawer overlay.
$: if (!$mobile) mobileNavOpen.set(false);
```

Change the markup (sidebar swap + bottom nav after the content area):

```svelte
<div class="workos-root text-gray-800 dark:text-gray-100">
	{#if !$mobile}
		<Sidebar />
	{/if}
	<div class="flex-1 flex flex-col min-w-0">
		{#if $view === 'board' || $view === 'list' || $view === 'calendar' || $view === 'overview'}
			<Topbar />
		{/if}
		<div class="flex-1 relative min-h-0 bg-gray-50 dark:bg-gray-900">
			<!-- …existing view switch, unchanged… -->
		</div>
		{#if $mobile}
			<BottomNav />
		{/if}
	</div>
	{#if $mobile}
		<NavDrawer />
	{/if}
	<ModalHost />
	<TeamSettingsDialog />
	<WorkspaceSettingsDialog />
</div>
```

- [ ] **Step 5: Verify** — `npx vitest run src/lib/components/workos` all pass; `npm run check` no new errors.

- [ ] **Step 6: Commit**

```bash
git add -A src/lib/components/workos
git commit -m "feat(workos): mobile shell - bottom nav + workstream drawer"
```

---

### Task 3: Topbar mobile row

**Files:**
- Modify: `src/lib/components/workos/chrome/Topbar.svelte`

- [ ] **Step 1: Compact the title row and hide decorative controls below `md`**

Title row (line 25): `class="h-14 flex items-center gap-3 px-4"` → `class="h-12 md:h-14 flex items-center gap-3 px-4"`.

Wrap the avatar stack + Share + Automation block (lines 36–44) in a `hidden md:flex` container — replace:

```svelte
	{#if ws}
		<div class="flex -space-x-2">
```

with:

```svelte
	{#if ws}
		<div class="hidden md:flex items-center gap-3">
			<div class="flex -space-x-2">
```

and close the extra `</div>` after the Automation button. (The two buttons keep their own classes; they simply live inside the new hidden-on-mobile wrapper.)

- [ ] **Step 2: Make the tab row scrollable**

Line 49: `class="flex items-center gap-1 px-4"` → `class="flex items-center gap-1 px-4 overflow-x-auto scrollbar-hidden"`.
Each tab button additionally gets `flex-none whitespace-nowrap` prepended to its class string so labels never wrap mid-scroll.

- [ ] **Step 3: Verify + commit**

`npm run check` no new errors.

```bash
git add src/lib/components/workos/chrome/Topbar.svelte
git commit -m "feat(workos): responsive topbar - scrollable tabs, mobile-compact title row"
```

---

### Task 4: Board — snap-swipe columns on mobile

**Files:**
- Modify: `src/lib/components/workos/views/BoardView.svelte`

- [ ] **Step 1: Stack the toolbar row on mobile**

Line 128: `class="flex-none flex items-stretch"` → `class="flex-none flex flex-col md:flex-row md:items-stretch"`.
Line 130 (the Add New container): `class="flex items-center px-4 border-b …"` → `class="flex items-center px-4 py-2 md:py-0 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950"`.

- [ ] **Step 2: Snap columns**

Scroller (line 142): append `max-md:snap-x max-md:snap-mandatory max-md:gap-3 max-md:p-3` to the class.
Column (line 144): `class="w-72 flex-none …"` → `class="w-72 max-md:w-[82vw] max-md:snap-center flex-none flex flex-col rounded-lg bg-gray-50/70 dark:bg-gray-900/40 p-2.5"`.

No JS changes — SortableJS drag still works with mouse on desktop; mobile status changes go through the task detail (spec non-goal).

- [ ] **Step 3: Verify + commit**

`npm run check` no new errors.

```bash
git add src/lib/components/workos/views/BoardView.svelte
git commit -m "feat(workos): board snap-swipe columns on mobile"
```

---

### Task 5: List — card rows on mobile

**Files:**
- Modify: `src/lib/components/workos/views/ListView.svelte`

**Interfaces:**
- Consumes: `mobile` from `$lib/stores`; `isOverdue(task, now)` from `../lib/calendar`; `formatDateShort(ts)` from `../lib/format`; existing `AssigneeAvatars`, `Pills` components; `openTask` from store.

- [ ] **Step 1: Add imports**

```ts
import { mobile } from '$lib/stores';          // merge with existing $lib/stores import ({ user, mobile })
import AssigneeAvatars from './AssigneeAvatars.svelte';
import Pills from '../ui/Pills.svelte';
import { isOverdue } from '../lib/calendar';
import { formatDateShort } from '../lib/format';
```

- [ ] **Step 2: Branch the group body**

Inside `{#if !collapsed[status]}` (line 116), wrap the existing column header + task rows in `{#if !$mobile}…{:else}…{/if}`. The desktop branch is the existing markup verbatim (column header div, task-row `{#each}`, but NOT the "Add task" footer — that stays shared below both branches). The mobile branch:

```svelte
{:else}
	{#each byStatus[status] as task (task.id)}
		<button
			class="w-full flex items-start gap-2.5 px-3 py-2.5 border-t border-gray-100 dark:border-gray-900 text-left active:bg-gray-50 dark:active:bg-gray-900/50"
			onclick={() => openTask(task.id)}
		>
			<span class="mt-0.5 flex-none"><StatusDot shape={statusShape(task.status)} color={STATUS_COLOR[task.status]} size={16} /></span>
			<span class="flex-1 min-w-0">
				<span class="block text-sm font-medium truncate">{task.title}</span>
				<span class="mt-1 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
					<span class="flex-none">{task.key}</span>
					{#if task.due_date != null}
						<span class="flex-none {isOverdue(task, Date.now()) ? 'text-red-600 dark:text-red-400 font-medium' : ''}">{formatDateShort(task.due_date)}</span>
					{/if}
					{#if task.priority}<Pills priority={task.priority} />{/if}
				</span>
			</span>
			{#if task.assignee_ids?.length}
				<span class="flex-none mt-0.5"><AssigneeAvatars ids={task.assignee_ids} max={3} size={20} /></span>
			{/if}
		</button>
	{/each}
{/if}
```

The "Add task" quick-add footer (lines 193–209) stays outside the branch so mobile keeps task creation. Its desktop-only left pad currently lives in an inline `style` attribute; move it into responsive classes so mobile gets the plain pad — replace the footer div's opening tag with:

```svelte
<div class="border-t border-gray-100 dark:border-gray-900 px-3 py-2 md:pl-[calc(0.75rem+26px)]">
```

(delete the `style="padding-left: calc(0.75rem + 26px);"` attribute).

- [ ] **Step 3: Verify + commit**

`npx vitest run src/lib/components/workos` all pass; `npm run check` no new errors.

```bash
git add src/lib/components/workos/views/ListView.svelte
git commit -m "feat(workos): list view card rows on mobile"
```

---

### Task 6: Calendar — agenda on mobile (TDD)

**Files:**
- Modify: `src/lib/components/workos/lib/calendar.ts`
- Test: `src/lib/components/workos/lib/calendar.test.ts`
- Modify: `src/lib/components/workos/views/CalendarView.svelte`

**Interfaces:**
- Produces: `agendaDays(tasks: Task[], cursor: Date): AgendaDay[]` where `AgendaDay = { day: number; date: Date; tasks: Task[] }`, exported from `lib/calendar.ts`. Day-ascending; only due-dated tasks inside the cursor's local month; empty days omitted.

- [ ] **Step 1: Write the failing tests**

Append to `calendar.test.ts` (match the file's existing test style/imports — it already imports from `./calendar`):

```ts
describe('agendaDays', () => {
	const mk = (id: string, due: number | null): Task =>
		({ id, due_date: due, status: 'todo' }) as Task;
	const cursor = new Date(2026, 6, 15); // July 2026

	it('groups tasks by local day, ascending', () => {
		const a = mk('a', new Date(2026, 6, 20, 9).getTime());
		const b = mk('b', new Date(2026, 6, 3, 23).getTime());
		const c = mk('c', new Date(2026, 6, 20, 18).getTime());
		const days = agendaDays([a, b, c], cursor);
		expect(days.map((d) => d.date.getDate())).toEqual([3, 20]);
		expect(days[1].tasks.map((t) => t.id)).toEqual(['a', 'c']);
	});

	it('excludes undated tasks and other months', () => {
		const inJuly = mk('x', new Date(2026, 6, 1).getTime());
		const june = mk('y', new Date(2026, 5, 30).getTime());
		const undated = mk('z', null);
		const days = agendaDays([inJuly, june, undated], cursor);
		expect(days).toHaveLength(1);
		expect(days[0].tasks.map((t) => t.id)).toEqual(['x']);
	});

	it('returns empty for a month with no due tasks', () => {
		expect(agendaDays([mk('a', null)], cursor)).toEqual([]);
	});
});
```

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/lib/components/workos/lib/calendar.test.ts`
Expected: FAIL — `agendaDays is not defined` (add it to the import list in the test file first).

- [ ] **Step 3: Implement**

Append to `calendar.ts`:

```ts
export interface AgendaDay {
	day: number; // dayKey
	date: Date;
	tasks: Task[];
}

// Mobile agenda: due-dated tasks inside the cursor's local month, grouped by
// day and sorted ascending. Days with no tasks are omitted.
export function agendaDays(tasks: Task[], cursor: Date): AgendaDay[] {
	const y = cursor.getFullYear();
	const m = cursor.getMonth();
	const byDay = new Map<number, Task[]>();
	for (const t of tasks) {
		if (t.due_date == null) continue;
		const d = new Date(t.due_date);
		if (d.getFullYear() !== y || d.getMonth() !== m) continue;
		const k = dayKey(t.due_date);
		(byDay.get(k) ?? byDay.set(k, []).get(k)!).push(t);
	}
	return [...byDay.entries()]
		.sort((a, b) => a[0] - b[0])
		.map(([day, ts]) => ({ day, date: new Date(day), tasks: ts }));
}
```

- [ ] **Step 4: Run to verify pass**

Run: `npx vitest run src/lib/components/workos/lib/calendar.test.ts`
Expected: PASS (all, including pre-existing).

- [ ] **Step 5: Mobile branch in `CalendarView.svelte`**

Script additions:

```ts
import { mobile } from '$lib/stores';
import { agendaDays } from '../lib/calendar';   // merge into the existing ../lib/calendar import
import { openTask } from '../lib/store';         // merge into the existing ../lib/store import
import StatusDot from '../ui/StatusDot.svelte';
import { STATUS_COLOR, statusShape } from '../lib/colors';

let showUnscheduled = false;
$: agenda = agendaDays($filteredTasks, cursor);
```

Template: wrap the toolbar + grid. The toolbar keeps prev/next/Today but hides the Month/Week segmented control on mobile — wrap that segmented-control div (lines 141–144) in `class="hidden md:inline-flex …"` (change its `inline-flex` to `hidden md:inline-flex`). Then replace the grid container region (lines 148–170) with:

```svelte
{#if $mobile}
	<!-- Agenda: month list grouped by day; tap opens the task. -->
	<div class="flex-1 overflow-y-auto p-3 bg-white dark:bg-gray-900">
		{#if unscheduled.length}
			<button
				class="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-800 text-sm font-medium mb-3"
				onclick={() => (showUnscheduled = !showUnscheduled)}
			>
				Unscheduled <span class="text-xs text-gray-400">{unscheduled.length}</span>
				<span class="flex-1"></span>
				<Icon name={showUnscheduled ? 'chevron-up' : 'chevron-down'} size={14} />
			</button>
			{#if showUnscheduled}
				<div class="mb-3 rounded-lg border border-gray-200 dark:border-gray-800 divide-y divide-gray-100 dark:divide-gray-900">
					{#each unscheduled as t (t.id)}
						<button class="w-full flex items-center gap-2.5 px-3 py-2.5 text-left" onclick={() => openTask(t.id)}>
							<StatusDot shape={statusShape(t.status)} color={STATUS_COLOR[t.status]} size={14} />
							<span class="flex-1 min-w-0 text-sm truncate">{t.title}</span>
							<span class="text-xs text-gray-400">{t.key}</span>
						</button>
					{/each}
				</div>
			{/if}
		{/if}

		{#each agenda as d (d.day)}
			<div class="mb-3">
				<div class="px-1 pb-1.5 text-xs font-semibold {isToday(d.day, Date.now()) ? 'text-primary' : 'text-gray-500 dark:text-gray-400'}">
					{d.date.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}
					{#if isToday(d.day, Date.now())}· Today{/if}
				</div>
				<div class="rounded-lg border border-gray-200 dark:border-gray-800 divide-y divide-gray-100 dark:divide-gray-900">
					{#each d.tasks as t (t.id)}
						<button class="w-full flex items-center gap-2.5 px-3 py-2.5 text-left" onclick={() => openTask(t.id)}>
							<StatusDot shape={statusShape(t.status)} color={STATUS_COLOR[t.status]} size={14} />
							<span class="flex-1 min-w-0 text-sm truncate">{t.title}</span>
							<span class="text-xs text-gray-400">{t.key}</span>
						</button>
					{/each}
				</div>
			</div>
		{/each}
		{#if !agenda.length}
			<div class="py-10 text-center text-sm text-gray-400">No scheduled tasks this month</div>
		{/if}
	</div>
{:else}
	<!-- …existing grid container (lines 148–170) verbatim… -->
{/if}
```

Guard the Sortable wiring so it never runs on mobile (the grid isn't mounted): in `initSortables()` add `if (get(mobile)) return;` as the first line (import `mobile` is already there; `get` is already imported).

- [ ] **Step 6: Verify + commit**

`npx vitest run src/lib/components/workos` all pass; `npm run check` no new errors.

```bash
git add src/lib/components/workos/lib/calendar.ts src/lib/components/workos/lib/calendar.test.ts src/lib/components/workos/views/CalendarView.svelte
git commit -m "feat(workos): mobile agenda calendar with unscheduled section"
```

---

### Task 7: FilterBar — stacked search + wrapping chips

**Files:**
- Modify: `src/lib/components/workos/chrome/FilterBar.svelte`

Design note: the spec said "chips scroll horizontally", but the facet menus are `position:absolute` children — an `overflow-x-auto` chip row would clip the open menus. Chips WRAP on mobile instead (2 rows worst case). Same information density, menus stay visible. Record this deviation in the commit body.

- [ ] **Step 1: Restructure the container**

Replace the outer div + search block (keep every chip block untouched inside the new chips row):

```svelte
<div class="flex-none flex flex-col md:flex-row md:items-center gap-2 px-4 py-3 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
	<!-- Search: full-width row on mobile, right-aligned on desktop -->
	<div class="relative md:order-2">
		<input
			class="text-sm pl-8 pr-2 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 bg-transparent w-full md:w-56"
			placeholder="Search title or key…"
			value={$filter.text}
			oninput={(e) => filter.update((f) => ({ ...f, text: (e.target as HTMLInputElement).value }))}
		/>
		<span class="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"><Icon name="search" size={14} /></span>
	</div>

	<!-- Facet chips: wrap on mobile, single row + spacer role on desktop -->
	<div class="flex flex-wrap items-center gap-2 md:order-1 md:flex-1 md:flex-nowrap">
		<!-- …the four existing facet divs (Status/Priority/Label/Assignee), unchanged… -->
	</div>

	<!-- Optional trailing controls (List's Columns picker + Add new) -->
	<div class="flex items-center gap-2 md:order-3">
		<slot />
	</div>
</div>
```

Delete the old `<div class="flex-1"></div>` spacer (the chips row's `md:flex-1` replaces it).

- [ ] **Step 2: Verify + commit**

`npm run check` no new errors. Confirm desktop DOM order via reading: chips → search → slot left-to-right comes from `md:order-1/2/3`.

```bash
git add src/lib/components/workos/chrome/FilterBar.svelte
git commit -m "feat(workos): responsive filter bar

Mobile: search on its own full-width row, facet chips wrap. Spec said
scroll-x chips; wrapped instead because the absolute-positioned facet
menus would be clipped by an overflow container."
```

---

### Task 8: Task detail — full-screen on mobile

**Files:**
- Modify: `src/lib/components/workos/views/TaskDetail.svelte`
- Modify: `src/lib/components/workos/views/detail/DetailHeader.svelte`

- [ ] **Step 1: Full-screen dialog frame**

`TaskDetail.svelte` line 232 — extend the `Dialog.Content` class:

```
class="flex flex-col gap-0 p-0 overflow-hidden w-[95vw] max-w-[1100px] sm:max-w-[1100px] max-h-[85vh] max-md:w-screen max-md:max-w-none max-md:h-dvh max-md:max-h-dvh max-md:rounded-none max-md:border-0 bg-white dark:bg-gray-950"
```

(If the shadcn Dialog applies `sm:max-w-*` internally, the `max-md:` overrides above still win below 768px because `max-md` covers `sm`..`<md`. Verify visually at 375px.)

- [ ] **Step 2: Back arrow in `DetailHeader.svelte`**

Before the existing maximize button (line 30), add:

```svelte
<Button variant="ghost" size="icon-sm" title="Back" class="md:hidden text-gray-500" onclick={closeTask}>
	<Icon name="arrow-left" size={18} />
</Button>
```

And hide the desktop-only affordances on mobile: maximize button class → `class="hidden md:inline-flex text-gray-400"`, close (X) button class → `class="max-md:hidden text-gray-500"`.

- [ ] **Step 3: "Details" accordion on mobile**

In `TaskDetail.svelte` script, add: `let showDetails = false;`

In the LEFT column (starts line 241): the title block stays always-visible. Immediately after the title block, insert the toggle; then wrap everything from `<!-- Properties -->` through `<AttachmentsPanel />` (lines 261–511) in a visibility div:

```svelte
<!-- Mobile: properties/description/attachments collapse behind one toggle -->
<button
	class="md:hidden w-full flex items-center gap-2 rounded-lg border border-gray-200 dark:border-gray-800 px-3 py-2 text-sm font-medium mb-4"
	onclick={() => (showDetails = !showDetails)}
>
	Details
	<span class="text-xs font-normal text-gray-400">status, dates, assignees…</span>
	<span class="flex-1"></span>
	<Icon name={showDetails ? 'chevron-up' : 'chevron-down'} size={14} />
</button>
<div class="{showDetails ? 'block' : 'hidden'} md:block">
	<!-- …existing Properties + Description + AttachmentsPanel, unchanged… -->
</div>
```

Also scale the column paddings: left column `px-7 py-5` → `px-4 py-4 md:px-7 md:py-5`; right column (line 515) same swap.

- [ ] **Step 4: Sticky composer**

In the comments tab (line 534), wrap the composer:

```svelte
<div class="max-md:sticky max-md:bottom-0 max-md:bg-white max-md:dark:bg-gray-950 max-md:pb-[env(safe-area-inset-bottom)]">
	<CommentComposer taskId={t.id} />
</div>
```

- [ ] **Step 5: Verify + commit**

`npm run check` no new errors.

```bash
git add src/lib/components/workos/views/TaskDetail.svelte src/lib/components/workos/views/detail/DetailHeader.svelte
git commit -m "feat(workos): full-screen task detail on mobile with details accordion"
```

---

### Task 9: My Work / Overview / Inbox cosmetic pass

**Files:**
- Modify: `src/lib/components/workos/views/MyWorkView.svelte`

- [ ] **Step 1: MyWorkView paddings + focus-list overflow**

Line 183: `class="max-w-[1240px] mx-auto px-9 pt-7 pb-14"` → `class="max-w-[1240px] mx-auto px-4 md:px-9 pt-5 md:pt-7 pb-14"`.
Line 288 (`<div class="px-2 pt-1 pb-2">`, the focus-list body that renders `style={GRID}` rows): → `class="px-2 pt-1 pb-2 overflow-x-auto"` — the grid rows scroll sideways rather than crush (My Work stays cosmetic-tier per spec; the KPI strip is already `grid-cols-2 md:grid-cols-4` and the main grid already `grid-cols-1 lg:…`).

- [ ] **Step 2: Overview + Inbox — verify, no expected edits**

OverviewView's shells are already `grid-cols-1 xl:…` inside `max-w-[1240px] mx-auto p-4`; KpiBand is `grid-cols-2 sm:grid-cols-3 xl:grid-cols-5`. InboxView is a plain list. Read both files at 375px-mindset; only if something hard-overflows (fixed width, long flex row) apply the same `px-4 md:px-…` / `overflow-x-auto` treatment — otherwise leave untouched. Do not restyle.

- [ ] **Step 3: Verify + commit**

`npm run check` no new errors.

```bash
git add src/lib/components/workos/views
git commit -m "style(workos): mobile padding + overflow tweaks for My Work"
```

---

### Task 10: Admin — don't-break tier

**Files:**
- Modify: `src/lib/components/workos/views/admin/TeamsTab.svelte`

- [ ] **Step 1: Wrap the roster table**

Line 29's `<table class="w-full text-sm">` gets an overflow wrapper:

```svelte
<div class="overflow-x-auto">
	<table class="w-full text-sm">
		…
	</table>
</div>
```

Scan `AdminApp.svelte`, `RulesTab.svelte`, `AccessTab.svelte` for other fixed-width rows or tables; apply the same wrapper where found (expected: none or one).

- [ ] **Step 2: Verify + commit**

`npm run check` no new errors.

```bash
git add src/lib/components/workos/views/admin
git commit -m "fix(workos): admin tables scroll instead of overflowing on mobile"
```

---

### Task 11: Access dialogs — height caps

**Files:**
- Modify: `src/lib/components/workos/chrome/access/TeamSettingsDialog.svelte`
- Modify: `src/lib/components/workos/chrome/access/WorkspaceSettingsDialog.svelte`

- [ ] **Step 1: Cap heights**

TeamSettingsDialog line 158: `class="sm:max-w-xl gap-6 rounded-2xl p-7"` → `class="sm:max-w-xl gap-6 rounded-2xl p-5 md:p-7 max-h-[90dvh] overflow-y-auto"`.
WorkspaceSettingsDialog line 170: same transformation.
(The small confirm dialogs at lines 318/322 are already `sm:max-w-md` and short — leave them.)
ModalHost's plain modal is `w-[420px] max-w-[92%]` — already phone-safe, leave it.

- [ ] **Step 2: Verify + commit**

`npm run check` no new errors.

```bash
git add src/lib/components/workos/chrome/access
git commit -m "fix(workos): cap access dialog heights on small screens"
```

---

### Task 12: Full verification sweep

**Files:** none (verification only) + possibly `docs/superpowers/specs/2026-06-26-workos-access-control.md`

- [ ] **Step 1: Full test run**

Run: `npx vitest run src/lib/components/workos`
Expected: ALL pass (including the 3 new agendaDays tests).

Run: `npm run check`
Expected: error count ≤ the baseline recorded before Task 1.

- [ ] **Step 2: Reference-doc check**

Grep `docs/superpowers/specs/2026-06-26-workos-access-control.md` for `Sidebar` / component-path references. The extraction moved the access entry points (workspace kebab/context menus, team settings menu) into `WorkstreamTree.svelte`/`TeamSwitcher.svelte` — if the doc names the old locations, update the file names (no logic changed, so only pointers move). Commit any doc edit as `docs(workos): update access-control doc pointers after sidebar extraction`.

- [ ] **Step 3: Report for manual smoke**

Do NOT start a dev server. Report to the user that the work is ready for browser smoke on their own Vite server, listing the checkpoints: 375px — bottom nav switch, drawer open/pick workstream/close, board swipe, list cards tap-through, calendar agenda + unscheduled toggle, task detail full-screen + details accordion + comment, dialogs fit; 768px+ — everything identical to before (especially sidebar tree menus and drag-and-drop).
