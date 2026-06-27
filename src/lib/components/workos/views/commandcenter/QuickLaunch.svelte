<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import { workspaces, workstreams, selectWorkstream, view } from '../../lib/store';
	import type { Task } from '../../lib/types';
	export let tasks: Task[];

	$: streams = (() => {
		const counts = new Map<string, number>();
		for (const t of tasks) counts.set(t.workstream_id, (counts.get(t.workstream_id) ?? 0) + 1);
		return [...counts.entries()]
			.map(([id, count]) => {
				const ws = $workstreams.find((s) => s.id === id);
				const wsp = ws ? $workspaces.find((w) => w.id === ws.workspace_id) : null;
				return ws ? { id, count, label: `${wsp ? wsp.name + ' · ' : ''}${ws.name}` } : null;
			})
			.filter((x): x is { id: string; count: number; label: string } => x !== null)
			.sort((a, b) => b.count - a.count);
	})();

	async function go(id: string) {
		await selectWorkstream(id);
		view.set('board');
	}
</script>

<div class="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-4">
	<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-2.5">Jump to</div>
	{#if streams.length}
		<div class="flex flex-col gap-0.5">
			{#each streams as s (s.id)}
				<button
					type="button"
					class="flex items-center gap-2.5 text-left rounded-lg px-1.5 py-1.5 hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors"
					onclick={() => go(s.id)}
				>
					<span class="w-6 h-6 rounded-md bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400 flex items-center justify-center flex-none">
						<Icon name="layers" size={13} />
					</span>
					<span class="flex-1 truncate text-xs">{s.label}</span>
					<span class="text-[10.5px] font-medium text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 rounded-full px-2 py-0.5 tabular-nums" aria-label="{s.count} tasks">{s.count}</span>
				</button>
			{/each}
		</div>
	{:else}
		<div class="text-[11px] text-gray-400">No workstreams yet</div>
	{/if}
</div>
