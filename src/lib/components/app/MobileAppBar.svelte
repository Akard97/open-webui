<script lang="ts">
	import { getContext } from 'svelte';
	import { page } from '$app/stores';

	import {
		WEBUI_NAME,
		config,
		showArchivedChats,
		showRailDrawer,
		showSidebar,
		user
	} from '$lib/stores';
	import { WEBUI_API_BASE_URL } from '$lib/constants';

	import MenuLines from '$lib/components/icons/MenuLines.svelte';
	import Tooltip from '$lib/components/common/Tooltip.svelte';
	import UserMenu from '$lib/components/layout/Sidebar/UserMenu.svelte';

	import { activeRailItem } from './railItems';

	const i18n = getContext<any>('i18n');

	let showUserMenu = false;

	$: activeItem = activeRailItem($page.url.pathname);
	$: title = activeItem?.label ? ($i18n?.t(activeItem.label) ?? activeItem.label) : $WEBUI_NAME;

	const openRailDrawer = () => {
		// Mutual exclusion with the chat-sidebar mobile drawer.
		showSidebar.set(false);
		showRailDrawer.set(true);
	};
</script>

<header
	class="sticky top-0 z-30 flex items-center gap-2 h-11 px-2 bg-white/95 dark:bg-gray-900/95 backdrop-blur border-b border-gray-100 dark:border-gray-850 text-gray-700 dark:text-gray-100"
>
	<Tooltip content={$i18n?.t('Open menu') ?? 'Open menu'} placement="bottom">
		<button
			type="button"
			aria-label={$i18n?.t('Open menu') ?? 'Open menu'}
			class="flex items-center justify-center size-9 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-850 transition cursor-pointer"
			on:click={openRailDrawer}
		>
			<MenuLines className="size-5" strokeWidth="2" />
		</button>
	</Tooltip>

	<div class="flex-1 min-w-0 text-center font-medium text-sm truncate px-2">
		{title}
	</div>

	{#if $user !== undefined && $user !== null}
		<UserMenu
			bind:show={showUserMenu}
			role={$user?.role}
			profile={$config?.features?.enable_user_status ?? true}
			showActiveUsers={false}
			className="w-[240px]"
			align="end"
			on:show={(e) => {
				if (e.detail === 'archived-chat') {
					showArchivedChats.set(true);
				}
			}}
		>
			<button
				type="button"
				aria-label={$i18n?.t('Open User Profile Menu') ?? 'Open User Profile Menu'}
				class="flex items-center justify-center size-9 rounded-full hover:bg-gray-100 dark:hover:bg-gray-850 transition cursor-pointer"
			>
				<img
					src={`${WEBUI_API_BASE_URL}/users/${$user?.id}/profile/image`}
					class="size-7 object-cover rounded-full"
					alt={$i18n?.t('Open User Profile Menu') ?? 'Open User Profile Menu'}
				/>
			</button>
		</UserMenu>
	{/if}
</header>
