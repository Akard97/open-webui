<script lang="ts">
	import CalChip from './CalChip.svelte';
	import type { Task } from '../../lib/types';

	export let date: Date;
	export let dimmed = false;
	export let today = false;
	export let tasks: Task[] = [];
	export let cap = Infinity;

	$: visible = tasks.slice(0, cap);
	$: overflow = Math.max(0, tasks.length - visible.length);
</script>

<div class="flex flex-col gap-1 min-h-[88px] p-1.5 border-r border-b border-gray-100 dark:border-gray-900">
	<div class="flex-none">
		{#if today}
			<span class="inline-flex items-center justify-center w-5 h-5 rounded-full bg-primary text-primary-foreground text-xs font-medium">{date.getDate()}</span>
		{:else}
			<span class="text-xs {dimmed ? 'text-gray-300 dark:text-gray-700' : 'text-gray-500 dark:text-gray-400'}">{date.getDate()}</span>
		{/if}
	</div>

	<div class="flex flex-col gap-1">
		{#each visible as t (t.id)}
			<CalChip task={t} />
		{/each}
		{#if overflow > 0}
			<div class="text-[11px] text-gray-400 pl-1.5">+{overflow} more</div>
		{/if}
	</div>
</div>
