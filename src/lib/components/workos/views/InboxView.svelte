<script lang="ts">
	import { onMount } from 'svelte';
	import {
		notifications, loadNotifications, markRead, markAllRead,
		view, selectWorkstream, openTask
	} from '../lib/store';
	import type { Notification } from '../lib/types';

	onMount(loadNotifications);

	function summary(n: Notification): string {
		const who = n.data?.actor_name ?? 'Someone';
		const key = n.data?.task_key ? `${n.data.task_key} ` : '';
		switch (n.type) {
			case 'assigned': return `${who} assigned you ${key}`.trim();
			case 'mentioned': return `${who} mentioned you in ${key}`.trim();
			case 'commented': return `${who} commented on ${key}`.trim();
			case 'status_changed': return `${who} changed status of ${key}`.trim();
			default: return `${who} updated ${key}`.trim();
		}
	}

	async function open(n: Notification) {
		if (!n.read) await markRead([n.id]);
		if (n.data?.workstream_id) await selectWorkstream(n.data.workstream_id);
		if (n.task_id) openTask(n.task_id);
		view.set('board');
	}
</script>

<div class="h-full overflow-y-auto">
	<div class="flex items-center gap-2 px-4 h-12 border-b border-gray-200 dark:border-gray-800">
		<span class="text-sm font-semibold">Inbox</span>
		<div class="flex-1"></div>
		<button class="text-sm text-teal-600 hover:underline" onclick={markAllRead}>Mark all read</button>
	</div>
	{#if !$notifications.length}
		<div class="p-8 text-center text-sm text-gray-400">You're all caught up.</div>
	{:else}
		<div class="divide-y divide-gray-100 dark:divide-gray-900">
			{#each $notifications as n (n.id)}
				<button
					class="flex items-start gap-3 w-full text-left px-4 py-3 hover:bg-gray-100 dark:hover:bg-gray-900"
					onclick={() => open(n)}
				>
					<span class="mt-1.5 w-2 h-2 rounded-full flex-none {n.read ? 'bg-transparent' : 'bg-teal-500'}"></span>
					<div class="min-w-0">
						<div class="text-sm truncate">{summary(n)}</div>
						{#if n.data?.snippet}<div class="text-xs text-gray-400 truncate">{n.data.snippet}</div>{/if}
					</div>
				</button>
			{/each}
		</div>
	{/if}
</div>
