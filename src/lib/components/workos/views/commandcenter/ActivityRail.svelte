<script lang="ts">
	import { onMount } from 'svelte';
	import { notifications, loadNotifications, openNotification, view } from '../../lib/store';
	import { summarizeNotification } from '../../lib/notifications';

	onMount(loadNotifications);
	$: recent = $notifications.slice(0, 8);
</script>

<div class="rounded-lg border border-gray-200 dark:border-gray-800 p-3">
	<div class="flex items-center justify-between mb-2">
		<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold">Activity</div>
		<button type="button" class="text-[11px] text-primary hover:underline" onclick={() => view.set('inbox')}>See all</button>
	</div>
	{#if !recent.length}
		<div class="text-[11px] text-gray-400 py-2">You're all caught up.</div>
	{:else}
		<div class="flex flex-col gap-1">
			{#each recent as n (n.id)}
				<button
					type="button"
					class="flex items-start gap-2 text-left rounded-md px-1.5 py-1 hover:bg-gray-100 dark:hover:bg-gray-900"
					aria-label={summarizeNotification(n) + (n.read ? '' : ' (unread)')}
					onclick={() => openNotification(n)}
				>
					<span aria-hidden="true" class="mt-1.5 w-1.5 h-1.5 rounded-full flex-none {n.read ? 'bg-transparent' : 'bg-primary'}"></span>
					<span class="min-w-0">
						<span class="block text-xs truncate">{summarizeNotification(n)}</span>
						{#if n.data?.snippet}<span class="block text-[11px] text-gray-400 truncate">{n.data.snippet}</span>{/if}
					</span>
				</button>
			{/each}
		</div>
	{/if}
</div>
