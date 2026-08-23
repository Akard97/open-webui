<script lang="ts">
	export let items: { label: string; value: number; sub?: string }[] = [];

	$: max = Math.max(1, ...items.map((i) => i.value));
</script>

<div class="flex flex-col gap-1">
	{#each items as item (item.label)}
		<div class="flex items-center gap-2 text-xs">
			<div class="w-36 shrink-0 truncate font-medium text-gray-900 dark:text-white">
				{item.label}
			</div>
			<div class="flex-1 h-3 bg-gray-50 dark:bg-gray-850 rounded overflow-hidden">
				<div
					class="h-full bg-blue-500/70 rounded"
					style="width: {(item.value / max) * 100}%"
				></div>
			</div>
			<div class="w-14 shrink-0 text-right text-gray-500 dark:text-gray-400">
				{item.value.toLocaleString()}
			</div>
			{#if item.sub !== undefined}
				<div class="w-20 shrink-0 text-right text-gray-400 truncate">{item.sub}</div>
			{/if}
		</div>
	{/each}
</div>
