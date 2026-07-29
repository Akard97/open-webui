<script lang="ts">
	// Feed row — V1 anatomy (user pick): unread dot column, type bubble, two-line body
	// (sentence + snippet/transition), stack pill that expands in place.
	import Icon from '../../ui/Icon.svelte';
	import TypeGlyph from './TypeGlyph.svelte';
	import StatusBadge from '../../ui/StatusBadge.svelte';
	import { displayName } from '../../lib/store';
	import { agoShort } from '../../lib/inboxFormat';
	import type { FeedEntry } from '../../lib/inbox';
	import type { Notification, TaskStatus } from '../../lib/types';

	export let entry: FeedEntry;
	export let selectedId: string | null = null;
	export let archivedView = false;
	export let onopen: (n: Notification) => void;
	export let onread: (n: Notification) => void;
	export let onarchive: (n: Notification) => void;

	let expanded = false;
	$: rows = expanded ? entry.stack : [entry.latest];

	const VERB: Record<string, string> = {
		assigned: 'assigned you', subtask_assigned: 'assigned you a subtask on',
		mentioned: 'mentioned you in', replied: 'replied to your comment on',
		commented: 'commented on', status_changed: 'moved'
	};
	const who = (x: Notification) => x.data?.actor_name ?? displayName(x.actor_id);
</script>

{#each rows as item, i (item.id)}
	<div
		class="group relative flex items-start gap-2.5 px-4 py-2.5 transition-colors duration-150 hover:bg-gray-50 dark:hover:bg-gray-850
			{selectedId === item.id ? 'bg-primary/5 shadow-[inset_2px_0_0_var(--primary)]' : ''}
			{i > 0 ? 'pl-10' : ''}"
	>
		<!-- Stretched primary action (valid a11y tree: actions are siblings, not nested). -->
		<button
			class="absolute inset-0 z-0 cursor-pointer focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-inset focus-visible:outline-none"
			aria-label="Open: {who(item)} {VERB[item.type] ?? 'updated'} {item.data?.task_title ?? ''}"
			onclick={() => onopen(item)}
		></button>
		{#if !item.read}
			<span class="mt-[11px] size-2 flex-none rounded-full bg-primary"></span>
		{:else}
			<span class="w-2 flex-none"></span>
		{/if}
		<TypeGlyph type={item.type} />
		<div class="min-w-0 flex-1">
			<div class="wos-body {item.read ? 'text-gray-500 dark:text-gray-400' : ''}">
				<span class={item.read ? 'font-medium' : 'font-semibold'}>{who(item)}</span>
				<span class="text-gray-500 dark:text-gray-400">{VERB[item.type] ?? 'updated'}</span>
				{#if item.data?.task_key}
					<span class="wos-caption rounded-md border border-gray-200 bg-gray-100 px-1.5 py-px text-gray-600 dark:border-gray-800 dark:bg-gray-850 dark:text-gray-300">{item.data.task_key}</span>
				{/if}
				<span class={item.read ? '' : 'font-semibold'}>{item.data?.task_title ?? ''}</span>
				{#if i === 0 && entry.stack.length > 1}
					<button
						class="relative z-10 ml-1 rounded-full bg-gray-100 px-2 py-px text-[11px] font-semibold text-gray-600 transition-colors duration-150 hover:bg-gray-200 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:bg-gray-850 dark:text-gray-300 dark:hover:bg-gray-800"
						onclick={() => (expanded = !expanded)}
					>{expanded ? 'Collapse' : `${entry.stack.length} updates`}</button>
				{/if}
			</div>
			{#if item.type === 'status_changed' && item.data?.from && item.data?.to}
				<div class="mt-1 flex items-center gap-1.5">
					<StatusBadge status={item.data.from as TaskStatus} size="sm" />
					<span class="wos-caption text-gray-400">→</span>
					<StatusBadge status={item.data.to as TaskStatus} size="sm" />
				</div>
			{:else if item.data?.snippet}
				<div class="wos-meta mt-1 line-clamp-2 border-l-2 border-gray-200 pl-2.5 text-gray-500 dark:border-gray-800 dark:text-gray-400">{item.data.snippet}</div>
			{:else if item.type === 'subtask_assigned' && item.data?.subtask_title}
				<div class="wos-meta mt-1 line-clamp-1 border-l-2 border-gray-200 pl-2.5 text-gray-500 dark:border-gray-800 dark:text-gray-400">{item.data.subtask_title}</div>
			{/if}
		</div>
		<span class="wos-caption mt-1 flex-none tabular-nums text-gray-400 dark:text-gray-500">{agoShort(item.created_at)}</span>
		<div class="relative z-10 mt-0.5 flex flex-none gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100">
			{#if !archivedView && !item.read}
				<button
					class="flex size-6 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-500 transition-colors duration-150 hover:text-gray-900 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:border-gray-800 dark:bg-gray-950 dark:text-gray-400 dark:hover:text-gray-100"
					title="Mark read" aria-label="Mark read"
					onclick={() => onread(item)}
				><Icon name="check" size={13} /></button>
			{/if}
			<button
				class="flex size-6 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-500 transition-colors duration-150 hover:text-gray-900 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:border-gray-800 dark:bg-gray-950 dark:text-gray-400 dark:hover:text-gray-100"
				title={archivedView ? 'Unarchive' : 'Archive'} aria-label={archivedView ? 'Unarchive' : 'Archive'}
				onclick={() => onarchive(item)}
			><Icon name="archive" size={13} /></button>
		</div>
	</div>
{/each}
