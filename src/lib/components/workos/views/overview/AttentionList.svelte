<script lang="ts">
	import { Button } from '$lib/components/ui/button';
	import { openTask } from '../../lib/store';
	import type { AttentionItem, AttentionClass } from '../../lib/overview';

	export let items: AttentionItem[];

	let expanded = false;
	$: shown = expanded ? items : items.slice(0, 6);

	const DOT: Record<AttentionClass, string> = {
		overdue: '#dc2626', behind: '#ea580c', at_risk: '#f59e0b', due_soon: '#f59e0b'
	};
	function label(i: AttentionItem): { text: string; cls: string; title?: string } {
		if (i.cls === 'overdue') return { text: `${i.daysLate}d late`, cls: 'text-red-600 dark:text-red-400' };
		if (i.cls === 'behind')
			return { text: 'behind plan', cls: 'text-orange-600 dark:text-orange-400', title: `${Math.round(i.gap ?? 0)} points behind planned progress` };
		if (i.cls === 'at_risk')
			return { text: 'at risk', cls: 'text-amber-600 dark:text-amber-500', title: `${Math.round(i.gap ?? 0)} points behind planned progress` };
		return { text: `due ${i.dueLabel}`, cls: 'text-amber-700 dark:text-amber-500' };
	}
</script>

<section class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 min-w-0">
	<h3 class="text-[13.5px] font-medium">Needs attention</h3>
	<p class="text-[11px] text-gray-400 mt-0.5">Overdue and slipping tasks, most urgent first.</p>
	{#if !items.length}
		<div class="py-6 text-center text-sm text-gray-400">Nothing needs attention.</div>
	{:else}
		<div class="mt-2.5 flex flex-col gap-0.5">
			{#each shown as i (i.task.id)}
				{@const l = label(i)}
				<button
					type="button"
					onclick={() => openTask(i.task.id)}
					class="flex items-center gap-2.5 w-full text-left px-2 py-1.5 rounded-lg text-[12.5px] hover:bg-gray-50 dark:hover:bg-gray-800/60
						{i.cls === 'overdue' ? 'bg-red-50/60 dark:bg-red-950/20' : ''}"
				>
					<span class="w-[7px] h-[7px] rounded-full flex-none" style="background:{DOT[i.cls]}"></span>
					<span class="min-w-0 flex-1 truncate">{i.task.title} <span class="text-gray-400">· {i.task.key}</span></span>
					<span class="flex-none text-[11.5px] tabular-nums {l.cls}" title={l.title}>{l.text}</span>
				</button>
			{/each}
		</div>
		{#if items.length > 6}
			<Button variant="ghost" size="xs" class="mt-2 text-primary" onclick={() => (expanded = !expanded)}>
				{expanded ? 'Show fewer' : `Show all ${items.length}`}
			</Button>
		{/if}
	{/if}
</section>
