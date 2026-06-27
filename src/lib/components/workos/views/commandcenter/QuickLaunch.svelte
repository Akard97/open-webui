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

<div class="rounded-lg border border-gray-200 dark:border-gray-800 p-3">
	<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-2">Quick launch</div>
	{#if streams.length}
		<div class="flex flex-col gap-0.5">
			{#each streams as s (s.id)}
				<button
					type="button"
					class="flex items-center gap-2 text-left rounded-md px-1.5 py-1 hover:bg-gray-100 dark:hover:bg-gray-900"
					onclick={() => go(s.id)}
				>
					<Icon name="layers" size={13} />
					<span class="flex-1 truncate text-xs">{s.label}</span>
					<span class="text-[11px] text-gray-400">{s.count}</span>
				</button>
			{/each}
		</div>
	{:else}
		<div class="text-[11px] text-gray-400">No workstreams yet</div>
	{/if}
</div>
