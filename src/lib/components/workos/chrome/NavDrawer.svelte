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
