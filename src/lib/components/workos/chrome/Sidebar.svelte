<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import SidebarIcon from '$lib/components/icons/Sidebar.svelte';
	import ThemeSwitcher from '$lib/components/app/ThemeSwitcher.svelte';
	import TeamSwitcher from './TeamSwitcher.svelte';
	import WorkstreamTree from './WorkstreamTree.svelte';
	import { user } from '$lib/stores';
	// Bundle the logo as a hashed build asset instead of loading it from the
	// backend's /static dir, which gets wiped when the backend image is rebuilt.
	import workosLogoDark from '../assets/workos-logo-dark.png';
	import workosLogoLight from '../assets/workos-logo-light.png';
	import { canUseAdmin } from '../lib/roles';
	import { currentTeam, view, unreadCount, navCollapsed } from '../lib/store';

	// Two-letter team mark for the collapsed rail (prefer the short key).
	$: teamBadge = (($currentTeam?.key || $currentTeam?.name || '?').trim().slice(0, 2)).toUpperCase();
</script>

{#if $navCollapsed}
	<!-- Collapsed: icon rail -->
	<aside
		class="w-14 flex-none h-full flex flex-col items-center gap-0.5 pt-2 pb-2 px-2 bg-gray-50 dark:bg-gray-950 border-e-[0.5px] border-gray-50 dark:border-gray-850/30 text-gray-600 dark:text-gray-400"
	>
		<!-- Logo / expand -->
		<button
			class="group size-9 rounded-xl flex items-center justify-center hover:bg-gray-100 dark:hover:bg-gray-850 transition"
			title="Expand sidebar"
			onclick={() => navCollapsed.set(false)}
		>
			<img src={workosLogoDark} class="size-7 object-contain group-hover:hidden block dark:hidden" alt="WorkOS" />
			<img src={workosLogoLight} class="size-7 object-contain group-hover:hidden hidden dark:block" alt="WorkOS" />
			<SidebarIcon className="size-5 hidden group-hover:flex" />
		</button>

		<button
			class="size-9 rounded-xl flex items-center justify-center hover:bg-gray-100 dark:hover:bg-gray-850 transition {$view === 'mywork' ? 'bg-gray-100 dark:bg-gray-850 text-gray-900 dark:text-white' : ''}"
			title="My Work"
			onclick={() => view.set('mywork')}
		>
			<Icon name="check" size={18} />
		</button>

		<button
			class="relative size-9 rounded-xl flex items-center justify-center hover:bg-gray-100 dark:hover:bg-gray-850 transition {$view === 'inbox' ? 'bg-gray-100 dark:bg-gray-850 text-gray-900 dark:text-white' : ''}"
			title="Inbox"
			onclick={() => view.set('inbox')}
		>
			<Icon name="message-square" size={18} />
			{#if $unreadCount > 0}
				<span class="absolute top-1 right-1 size-1.5 rounded-full bg-primary"></span>
			{/if}
		</button>

		<!-- Current team (click to expand and switch) -->
		<button
			class="size-9 rounded-xl flex items-center justify-center text-[11px] font-semibold bg-brand-600 text-white transition hover:bg-brand-700 dark:bg-brand-500 dark:text-brand-950 dark:hover:bg-brand-400"
			title={$currentTeam?.name ?? 'Team'}
			onclick={() => navCollapsed.set(false)}
		>
			{teamBadge}
		</button>

		<div class="flex-1"></div>

		{#if canUseAdmin($user)}
			<button class="size-9 rounded-xl flex items-center justify-center hover:bg-gray-100 dark:hover:bg-gray-850 transition" title="WorkOS admin" onclick={() => view.set('admin')}>
				<Icon name="settings" size={18} />
			</button>
		{/if}
		<ThemeSwitcher />
	</aside>
{:else}
	<aside class="w-64 flex-none h-full flex flex-col bg-gray-50 dark:bg-gray-950 border-e-[0.5px] border-gray-50 dark:border-gray-850/30">
		<!-- Header: mark + name + collapse -->
		<div class="px-[0.5625rem] pt-2 pb-1.5 flex justify-between space-x-1 text-gray-600 dark:text-gray-400">
			<div class="flex items-center size-8.5 justify-center">
				<img src={workosLogoDark} class="size-7 object-contain block dark:hidden" alt="WorkOS" />
				<img src={workosLogoLight} class="size-7 object-contain hidden dark:block" alt="WorkOS" />
			</div>
			<div class="flex flex-1 items-center px-0.5">
				<div class="self-center font-medium text-gray-850 dark:text-white font-primary">WorkOS</div>
			</div>
			<button
				class="flex rounded-xl size-8.5 justify-center items-center hover:bg-gray-100/50 dark:hover:bg-gray-850/50 transition"
				title="Collapse sidebar"
				onclick={() => navCollapsed.set(true)}
			>
				<div class="self-center p-1.5"><SidebarIcon /></div>
			</button>
		</div>

		<!-- My Work + Inbox -->
		<div class="text-gray-800 dark:text-gray-200">
			<div class="px-[0.4375rem] flex justify-center">
				<button
					class="group grow flex items-center space-x-3 rounded-xl px-2.5 py-2 hover:bg-gray-100 dark:hover:bg-gray-900 transition outline-none {$view === 'mywork' ? 'bg-gray-100 dark:bg-gray-900' : ''}"
					onclick={() => view.set('mywork')}
				>
					<div class="self-center"><Icon name="check" size={18} /></div>
					<div class="flex flex-1 self-center translate-y-[0.5px]">
						<div class="self-center text-sm font-primary {$view === 'mywork' ? 'font-medium' : ''}">My Work</div>
					</div>
				</button>
			</div>
			<div class="px-[0.4375rem] flex justify-center">
				<button
					class="group grow flex items-center space-x-3 rounded-xl px-2.5 py-2 hover:bg-gray-100 dark:hover:bg-gray-900 transition outline-none {$view === 'inbox' ? 'bg-gray-100 dark:bg-gray-900' : ''}"
					onclick={() => view.set('inbox')}
				>
					<div class="self-center"><Icon name="message-square" size={18} /></div>
					<div class="flex flex-1 self-center translate-y-[0.5px]">
						<div class="self-center text-sm font-primary {$view === 'inbox' ? 'font-medium' : ''}">Inbox</div>
					</div>
					{#if $unreadCount > 0}
						<span class="shrink-0 self-center text-[10px] min-w-4 h-4 px-1 rounded-full bg-primary text-primary-foreground flex items-center justify-center">{$unreadCount}</span>
					{/if}
				</button>
			</div>
		</div>

		<TeamSwitcher />

		<!-- Workspaces -->
		<div class="flex-1 overflow-y-auto scrollbar-hidden px-2 mt-4 pb-2">
			<WorkstreamTree />
		</div>

		<!-- Footer -->
		<div class="border-t border-gray-50 dark:border-gray-850/30 p-2 flex items-center gap-2 text-gray-800 dark:text-gray-200">
			<div class="flex-1 min-w-0 text-sm font-medium truncate">{$user?.name ?? ''}</div>
			{#if canUseAdmin($user)}
				<button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition" title="WorkOS admin" onclick={() => view.set('admin')}>
					<Icon name="settings" size={16} />
				</button>
			{/if}
			<ThemeSwitcher />
		</div>
	</aside>
{/if}
