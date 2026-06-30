<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import CalChip from './CalChip.svelte';
	import type { Task } from '../../lib/types';
	import { addTask, currentWorkstream } from '../../lib/store';
	import { dayKey } from '../../lib/calendar';

	export let date: Date;
	export let dimmed = false;
	export let today = false;
	export let tasks: Task[] = [];
	export let cap = Infinity;

	$: visible = tasks.slice(0, cap);
	$: overflow = Math.max(0, tasks.length - visible.length);

	let adding = false;
	let title = '';

	async function submit() {
		const ws = $currentWorkstream;
		const t = title.trim();
		if (!t || !ws) return;
		// Close before the await so a quick double-Enter can't fire addTask twice.
		adding = false;
		title = '';
		await addTask(ws.id, { title: t, due_date: dayKey(date.getTime()) });
	}
</script>

<div
	class="group relative flex flex-col min-h-[96px] border-r border-b border-gray-100 dark:border-gray-900 [&:nth-child(7n)]:border-r-0 transition-colors hover:bg-gray-50/70 dark:hover:bg-gray-900/40 {today ? 'bg-primary/5' : ''}"
>
	<!-- Date — outside the drop zone so the dragged-chip preview always lands below the number -->
	<div class="flex-none px-1.5 pt-1.5">
		{#if today}
			<span class="inline-flex items-center justify-center w-[22px] h-[22px] rounded-full bg-primary text-primary-foreground text-xs font-semibold">{date.getDate()}</span>
		{:else}
			<span class="text-xs {dimmed ? 'text-gray-300 dark:text-gray-700' : 'text-gray-500 dark:text-gray-400'}">{date.getDate()}</span>
		{/if}
	</div>

	<!-- Drop zone — fills the rest of the cell so the whole box (below the date) accepts drops.
	     Only [data-task-id] chips are draggable; the plus button lives inside so drops over it
	     still resolve to this day. -->
	<div
		data-cal-list
		data-day={dayKey(date.getTime())}
		class="relative flex-1 flex flex-col gap-1 px-1.5 pb-1.5 pt-1"
	>
		{#each visible as t (t.id)}
			<CalChip task={t} />
		{/each}
		{#if overflow > 0}
			<div class="text-[11px] text-gray-400 dark:text-gray-500 pl-1.5">+{overflow} more</div>
		{/if}

		{#if adding}
			<!-- svelte-ignore a11y_autofocus -->
			<input
				class="mt-0.5 text-[11px] px-1.5 py-1 rounded-md border border-gray-300 dark:border-gray-700 bg-white dark:bg-gray-950 focus:outline-none focus:ring-1 focus:ring-primary"
				placeholder="Task title…"
				bind:value={title}
				onkeydown={(e) => { if (e.key === 'Enter') submit(); if (e.key === 'Escape') { adding = false; title = ''; } }}
				onblur={() => { adding = false; title = ''; }}
				autofocus
			/>
		{:else}
			<button
				type="button"
				class="absolute bottom-1 right-1 w-[22px] h-[22px] rounded-md inline-flex items-center justify-center text-primary bg-primary/10 hover:bg-primary/20 opacity-0 group-hover:opacity-100 focus:opacity-100 transition"
				title="Add task on this day"
				aria-label="Add task on {date.toDateString()}"
				onclick={() => (adding = true)}
			><Icon name="plus" size={14} /></button>
		{/if}
	</div>
</div>
