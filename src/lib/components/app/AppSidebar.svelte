<script lang="ts">
	import { getContext } from 'svelte';
	import { page } from '$app/stores';

	import { WEBUI_NAME, config, showArchivedChats, user } from '$lib/stores';
	import { WEBUI_API_BASE_URL, WEBUI_BASE_URL } from '$lib/constants';

	import UserMenu from '$lib/components/layout/Sidebar/UserMenu.svelte';

	import { railItems, activeRailItem } from './railItems';

	const i18n = getContext<any>('i18n');

	let showUserMenu = false;

	$: visibleItems = railItems.filter((item) => item.visible({ user: $user, config: $config }));

	$: activeId = activeRailItem($page.url.pathname, visibleItems)?.id;
</script>

<!-- Spacer keeps the collapsed gap in the parent flex row. -->
<div class="w-[3.6rem] shrink-0 h-screen" aria-hidden="true"></div>

<nav
	aria-label={$i18n?.t('App navigation') ?? 'App navigation'}
	class="group/rail fixed start-0 top-0 h-screen z-[60] flex flex-col
		w-[3.6rem] hover:w-60
		bg-gray-50/95 dark:bg-gray-950/95 backdrop-blur
		border-e border-gray-200/70 dark:border-gray-900
		transition-[width] duration-200 ease-out
		overflow-hidden"
>
	<!-- Logo -->
	<a
		href="/home"
		class="flex items-center h-14 shrink-0 px-3 text-gray-900 dark:text-white"
		aria-label={$WEBUI_NAME}
	>
		<span class="w-10 shrink-0 flex items-center justify-center">
			<img
				src="{WEBUI_BASE_URL}/static/favicon.png"
				alt={$WEBUI_NAME}
				class="size-6 rounded object-contain"
				draggable="false"
			/>
		</span>
		<span
			class="ms-1 text-[13px] font-semibold tracking-tight whitespace-nowrap
				opacity-0 group-hover/rail:opacity-100 transition-opacity duration-150 delay-100"
		>
			{$WEBUI_NAME}
		</span>
	</a>

	<!-- Nav items -->
	<div class="flex-1 overflow-y-auto overflow-x-hidden scrollbar-hidden">
		<ul class="flex flex-col gap-0.5 px-2 py-1">
			{#each visibleItems as item (item.id)}
				<li>
					<a
						href={item.href}
						aria-label={$i18n?.t(item.label) ?? item.label}
						aria-current={item.id === activeId ? 'page' : undefined}
						class="flex items-center h-9 rounded-lg transition-colors duration-100
							{item.id === activeId
								? 'bg-gray-200/60 dark:bg-gray-900 text-gray-900 dark:text-white'
								: 'text-gray-600 dark:text-gray-400 hover:bg-gray-200/40 dark:hover:bg-gray-900/60 hover:text-gray-900 dark:hover:text-white'}"
					>
						<span class="w-10 shrink-0 flex items-center justify-center">
							<svelte:component this={item.icon} className="size-[1.125rem]" strokeWidth="1.5" />
						</span>
						<span
							class="ms-1 text-[13px] font-medium whitespace-nowrap
								opacity-0 group-hover/rail:opacity-100 transition-opacity duration-150 delay-100"
						>
							{$i18n?.t(item.label) ?? item.label}
						</span>
					</a>
				</li>
			{/each}
		</ul>
	</div>

	<!-- User -->
	{#if $user !== undefined && $user !== null}
		<div class="shrink-0 px-2 py-2 border-t border-gray-200/70 dark:border-gray-900">
			<UserMenu
				bind:show={showUserMenu}
				role={$user?.role}
				profile={$config?.features?.enable_user_status ?? true}
				showActiveUsers={false}
				className="w-[240px]"
				align="start"
				on:show={(e) => {
					if (e.detail === 'archived-chat') {
						showArchivedChats.set(true);
					}
				}}
			>
				<button
					type="button"
					aria-label={$i18n?.t('Open User Profile Menu') ?? 'Open User Profile Menu'}
					class="w-full flex items-center h-10 rounded-lg hover:bg-gray-200/40 dark:hover:bg-gray-900/60 transition-colors duration-100"
				>
					<span class="w-10 shrink-0 flex items-center justify-center">
						<img
							src={`${WEBUI_API_BASE_URL}/users/${$user?.id}/profile/image`}
							class="size-7 object-cover rounded-full"
							alt={$user?.name ?? ''}
							draggable="false"
						/>
					</span>
					<span
						class="ms-1 flex flex-col items-start min-w-0 pe-2 text-start
							opacity-0 group-hover/rail:opacity-100 transition-opacity duration-150 delay-100"
					>
						<span
							class="text-[13px] font-medium text-gray-900 dark:text-white truncate max-w-[10rem] leading-tight"
						>
							{$user?.name ?? ''}
						</span>
						{#if $user?.email}
							<span
								class="text-[11px] text-gray-500 dark:text-gray-500 truncate max-w-[10rem] leading-tight"
							>
								{$user.email}
							</span>
						{/if}
					</span>
				</button>
			</UserMenu>
		</div>
	{/if}
</nav>
