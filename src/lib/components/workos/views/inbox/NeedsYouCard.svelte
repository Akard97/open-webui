<script lang="ts">
	// "Needs you" card — flat rounded-lg card with a 2px primary inset (mockup V4).
	import Icon from '../../ui/Icon.svelte';
	import TypeGlyph from './TypeGlyph.svelte';
	import { Avatar, AvatarFallback } from '$lib/components/ui/avatar';
	import { avatarColors } from '../../lib/avatar';
	import { displayName } from '../../lib/store';
	import { agoShort } from '../../lib/inboxFormat';
	import type { Notification } from '../../lib/types';

	export let n: Notification;
	export let selected = false;
	export let onopen: () => void;
	export let onread: () => void;
	export let onarchive: () => void;

	$: who = n.data?.actor_name ?? displayName(n.actor_id);
	$: initialsOf = (who || '?').trim().split(/\s+/).map((w: string) => w[0]).slice(0, 2).join('').toUpperCase() || '?';
	$: verb =
		n.type === 'assigned' ? 'assigned you' :
		n.type === 'subtask_assigned' ? 'assigned you a subtask on' :
		'mentioned you in';
</script>

<div
	class="group relative mx-4 mb-2 flex gap-2.5 rounded-lg border bg-white p-2.5 pl-3
		shadow-[inset_2px_0_0_var(--primary)] transition-colors duration-150 dark:bg-gray-900
		{selected ? 'border-primary' : 'border-gray-200 hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-850'}"
>
	<!-- Stretched primary action: a real sibling button (valid a11y tree) — the
	     hover actions below are z-raised siblings, never nested interactives. -->
	<button
		class="absolute inset-0 z-0 cursor-pointer rounded-lg focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
		aria-label="Open: {who} {verb} {n.data?.task_title ?? ''}"
		onclick={onopen}
	></button>
	<Avatar class="size-7 flex-none">
		<AvatarFallback class="text-[10px] font-semibold text-white" style="background:{avatarColors(n.actor_id ?? who).background}">
			{initialsOf}
		</AvatarFallback>
	</Avatar>
	<div class="min-w-0 flex-1">
		<div class="wos-body">
			<TypeGlyph type={n.type} variant="inline" />
			<span class="font-semibold">{who}</span>
			<span class="text-gray-500 dark:text-gray-400">{verb}</span>
			{#if n.data?.task_key}
				<span class="wos-caption rounded-md border border-gray-200 bg-gray-100 px-1.5 py-px text-gray-600 dark:border-gray-800 dark:bg-gray-850 dark:text-gray-300">{n.data.task_key}</span>
			{/if}
			<span class="font-semibold">{n.data?.task_title ?? ''}</span>
		</div>
		{#if n.data?.snippet}
			<div class="wos-meta mt-1 truncate border-l-2 border-gray-200 pl-2.5 text-gray-500 dark:border-gray-800 dark:text-gray-400">{n.data.snippet}</div>
		{/if}
	</div>
	<div class="flex flex-none flex-col items-end gap-1">
		<span class="wos-caption tabular-nums text-gray-400 dark:text-gray-500">{agoShort(n.created_at)}</span>
		<div class="relative z-10 flex gap-1 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-within:opacity-100">
			<button
				class="flex size-6 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-500 transition-colors duration-150 hover:text-gray-900 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:border-gray-800 dark:bg-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
				title="Mark read" aria-label="Mark read"
				onclick={onread}
			><Icon name="check" size={13} /></button>
			<button
				class="flex size-6 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-500 transition-colors duration-150 hover:text-gray-900 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:border-gray-800 dark:bg-gray-900 dark:text-gray-400 dark:hover:text-gray-100"
				title="Archive" aria-label="Archive"
				onclick={onarchive}
			><Icon name="archive" size={13} /></button>
		</div>
	</div>
</div>
