<script lang="ts">
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

<div class="group flex flex-col gap-1 min-h-[88px] p-1.5 border-r border-b border-gray-100 dark:border-gray-900">
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

	{#if adding}
		<!-- svelte-ignore a11y_autofocus -->
		<input
			class="mt-1 text-[11px] px-1.5 py-1 rounded border border-gray-300 dark:border-gray-700 bg-transparent"
			placeholder="Task title…"
			bind:value={title}
			onkeydown={(e) => { if (e.key === 'Enter') submit(); if (e.key === 'Escape') { adding = false; title = ''; } }}
			onblur={() => { adding = false; title = ''; }}
			autofocus
		/>
	{:else}
		<button
			class="flex-1 min-h-[16px] rounded text-left opacity-0 group-hover:opacity-100 transition"
			title="Add task on this day"
			aria-label="Add task on {date.toDateString()}"
			onclick={() => (adding = true)}
		></button>
	{/if}
</div>
