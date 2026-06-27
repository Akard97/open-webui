<script lang="ts">
	import { onMount } from 'svelte';
	import { notifications, loadNotifications, markAllRead, openNotification } from '../lib/store';
	import { summarizeNotification } from '../lib/notifications';

	onMount(loadNotifications);
</script>

<div class="h-full overflow-y-auto">
	<div class="flex items-center gap-2 px-4 h-12 border-b border-gray-200 dark:border-gray-800">
		<span class="text-sm font-semibold">Inbox</span>
		<div class="flex-1"></div>
		<button class="text-sm text-primary hover:underline" onclick={markAllRead}>Mark all read</button>
	</div>
	{#if !$notifications.length}
		<div class="p-8 text-center text-sm text-gray-400">You're all caught up.</div>
	{:else}
		<div class="divide-y divide-gray-100 dark:divide-gray-900">
			{#each $notifications as n (n.id)}
				<button
					class="flex items-start gap-3 w-full text-left px-4 py-3 hover:bg-gray-100 dark:hover:bg-gray-900"
					onclick={() => openNotification(n)}
				>
					<span class="mt-1.5 w-2 h-2 rounded-full flex-none {n.read ? 'bg-transparent' : 'bg-primary'}"></span>
					<div class="min-w-0">
						<div class="text-sm truncate">{summarizeNotification(n)}</div>
						{#if n.data?.snippet}<div class="text-xs text-gray-400 truncate">{n.data.snippet}</div>{/if}
					</div>
				</button>
			{/each}
		</div>
	{/if}
</div>
