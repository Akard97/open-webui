<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import { page } from '$app/stores';
	import { fade, fly } from 'svelte/transition';

	import { config, showRailDrawer, user } from '$lib/stores';

	import XMark from '$lib/components/icons/XMark.svelte';

	import { railItems, activeRailItem } from './railItems';

	const i18n = getContext<any>('i18n');

	$: visibleItems = railItems.filter((item) => item.visible({ user: $user, config: $config }));

	$: activeId = activeRailItem($page.url.pathname, visibleItems)?.id;

	const close = () => showRailDrawer.set(false);

	beforeNavigate(() => {
		if ($showRailDrawer) {
			close();
		}
	});

	onMount(() => {
		const onKeyDown = (e: KeyboardEvent) => {
			if (e.key === 'Escape' && $showRailDrawer) {
				close();
			}
		};
		window.addEventListener('keydown', onKeyDown);
		return () => window.removeEventListener('keydown', onKeyDown);
	});
</script>

{#if $showRailDrawer}
	<div class="fixed inset-0 z-50 flex" role="dialog" aria-modal="true">
		<!-- svelte-ignore a11y-click-events-have-key-events -->
		<!-- svelte-ignore a11y-no-static-element-interactions -->
		<div
			class="absolute inset-0 bg-black/40 dark:bg-black/60"
			transition:fade={{ duration: 150 }}
			on:click={close}
		/>

		<aside
			class="relative h-full w-[280px] max-w-[80vw] bg-white dark:bg-gray-900 border-e border-gray-100 dark:border-gray-850 flex flex-col shadow-xl"
			transition:fly={{ x: -280, duration: 200 }}
			aria-label={$i18n?.t('App navigation') ?? 'App navigation'}
		>
			<div
				class="flex items-center justify-between px-3 h-11 border-b border-gray-100 dark:border-gray-850"
			>
				<div class="font-medium text-sm text-gray-700 dark:text-gray-200">
					{$i18n?.t('Navigate') ?? 'Navigate'}
				</div>
				<button
					type="button"
					aria-label={$i18n?.t('Close') ?? 'Close'}
					class="flex items-center justify-center size-8 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition cursor-pointer"
					on:click={close}
				>
					<XMark className="size-5" strokeWidth="2" />
				</button>
			</div>

			<nav class="flex-1 overflow-y-auto p-2 flex flex-col gap-1">
				{#each visibleItems as item (item.id)}
					<a
						href={item.href}
						aria-current={item.id === activeId ? 'page' : undefined}
						class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition
							{item.id === activeId
							? 'bg-gray-100 dark:bg-gray-800 text-black dark:text-white font-medium'
							: 'text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-gray-850'}"
					>
						<span class="flex items-center justify-center size-6 shrink-0">
							<svelte:component this={item.icon} className="size-5" strokeWidth="1.75" />
						</span>
						<span class="truncate">{$i18n?.t(item.label) ?? item.label}</span>
					</a>
				{/each}
			</nav>
		</aside>
	</div>
{/if}
