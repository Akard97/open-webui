<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import ThemeSwitcher from '$lib/components/app/ThemeSwitcher.svelte';
	import TeamSwitcher from './TeamSwitcher.svelte';
	import WorkstreamTree from './WorkstreamTree.svelte';
	import { canUseAdmin } from '../lib/roles';
	import { user } from '$lib/stores';
	import { mobileNavOpen, view, unreadCount } from '../lib/store';

	const close = () => mobileNavOpen.set(false);
</script>

<svelte:window onkeydown={(e) => { if (e.key === 'Escape' && $mobileNavOpen) close(); }} />

{#if $mobileNavOpen}
	<div class="fixed inset-0 z-40">
		<button class="absolute inset-0 bg-black/40" aria-label="Close navigation" onclick={close}></button>
		<aside class="absolute inset-y-0 left-0 w-[82vw] max-w-[320px] flex flex-col bg-gray-50 dark:bg-gray-950 shadow-xl" role="dialog" aria-modal="true">
			<!-- My Work + Inbox (mirrors the desktop sidebar panel; the bottom tab bar is gone) -->
			<div class="mt-2 text-gray-800 dark:text-gray-200">
				<div class="px-[0.4375rem] flex justify-center">
					<button
						class="group grow flex items-center space-x-3 rounded-xl px-2.5 py-2 hover:bg-gray-100 dark:hover:bg-gray-900 transition outline-none {$view === 'mywork' ? 'bg-gray-100 dark:bg-gray-900' : ''}"
						onclick={() => { view.set('mywork'); close(); }}
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
						onclick={() => { view.set('inbox'); close(); }}
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
