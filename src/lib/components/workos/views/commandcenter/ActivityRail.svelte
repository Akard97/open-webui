<script lang="ts">
	import { onMount } from 'svelte';
	import { notifications, loadNotifications, openNotification, view } from '../../lib/store';
	import { summarizeNotification } from '../../lib/notifications';
	import type { Notification } from '../../lib/types';

	onMount(loadNotifications);
	$: recent = $notifications.slice(0, 8);

	const actorInitial = (n: Notification) => (n.data?.actor_name ?? '?').trim().charAt(0).toUpperCase() || '•';
</script>

<div class="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-4">
	<div class="flex items-center justify-between mb-2.5">
		<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold">Activity</div>
		<button type="button" class="text-[11px] text-primary hover:underline" onclick={() => view.set('inbox')}>See all</button>
	</div>
	{#if !recent.length}
		<div class="text-[11px] text-gray-400 py-2">You're all caught up.</div>
	{:else}
		<div class="flex flex-col gap-0.5">
			{#each recent as n (n.id)}
				<button
					type="button"
					class="flex items-start gap-2.5 text-left rounded-lg px-1.5 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors"
					aria-label={summarizeNotification(n) + (n.read ? '' : ' (unread)')}
					onclick={() => openNotification(n)}
				>
					<span aria-hidden="true" class="w-6 h-6 rounded-full text-[10px] font-semibold flex items-center justify-center flex-none bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300">{actorInitial(n)}</span>
					<span class="min-w-0 flex-1">
						<span class="flex items-center gap-1.5">
							<span class="block text-xs truncate flex-1">{summarizeNotification(n)}</span>
							{#if !n.read}<span aria-hidden="true" class="w-1.5 h-1.5 rounded-full bg-primary flex-none"></span>{/if}
						</span>
						{#if n.data?.snippet}<span class="block text-[11px] text-gray-400 truncate">{n.data.snippet}</span>{/if}
					</span>
				</button>
			{/each}
		</div>
	{/if}
</div>
