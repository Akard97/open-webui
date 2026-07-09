<script lang="ts">
	import { PALETTE, DEFAULT_COLOR_CYCLE, type KpiWidget } from '$lib/utils/widgets';

	export let widget: KpiWidget;

	$: gridCols =
		widget.items.length === 1
			? 'grid-cols-1'
			: widget.items.length === 2
				? 'grid-cols-2'
				: widget.items.length === 3
					? 'grid-cols-1 sm:grid-cols-3'
					: 'grid-cols-2 sm:grid-cols-4';
</script>

<div class="grid {gridCols} gap-2.5 w-full">
	{#each widget.items as item, idx}
		{@const palette = PALETTE[item.color ?? DEFAULT_COLOR_CYCLE[idx % DEFAULT_COLOR_CYCLE.length]]}
		<div class="relative overflow-hidden rounded-2xl p-4 text-white shadow-sm {palette.tile}">
			<!-- soft glow accent -->
			<div class="absolute -top-6 -end-6 size-20 rounded-full bg-white/10 pointer-events-none"></div>

			<div class="text-[0.7rem] font-medium uppercase tracking-wide text-white/80 truncate">
				{item.label}
			</div>
			<div class="mt-1 text-2xl font-semibold leading-tight break-words">
				{item.value}
			</div>

			{#if item.delta}
				<div
					class="mt-2 inline-flex items-center gap-1 rounded-full bg-white/20 px-2 py-0.5 text-xs font-medium"
				>
					{#if item.trend === 'up'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2.5"
							class="size-3"
						>
							<path stroke-linecap="round" stroke-linejoin="round" d="m4.5 15.75 7.5-7.5 7.5 7.5" />
						</svg>
					{:else if item.trend === 'down'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2.5"
							class="size-3"
						>
							<path stroke-linecap="round" stroke-linejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
						</svg>
					{:else if item.trend === 'flat'}
						<svg
							xmlns="http://www.w3.org/2000/svg"
							viewBox="0 0 24 24"
							fill="none"
							stroke="currentColor"
							stroke-width="2.5"
							class="size-3"
						>
							<path stroke-linecap="round" stroke-linejoin="round" d="M4.5 12h15" />
						</svg>
					{/if}
					<span>{item.delta}</span>
				</div>
			{/if}
		</div>
	{/each}
</div>
