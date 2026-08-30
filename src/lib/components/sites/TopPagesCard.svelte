<script lang="ts">
	import { getContext } from 'svelte';
	import { formatCount } from './lib/analytics';

	const i18n = getContext('i18n');

	// Presentational: OverviewTab owns the fetch and hands the rows down, so
	// both this card and Details can sit side by side under one load.
	let {
		loading = false,
		topPages = []
	}: { loading?: boolean; topPages?: { path: string; views: number }[] } = $props();

	// Counts follow the active UI language; analytics.ts stays pure, so the
	// locale is passed in rather than imported there.
	const locale = $derived($i18n.language);
</script>

<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
	<h4 class="mb-2 text-xs font-medium text-gray-400 dark:text-gray-500">
		{$i18n.t('Top pages')}
	</h4>
	{#if loading}
		<!-- A skeleton, never the rows still in state: those belong to the
		     previous site (or range) and must not appear under a new header. -->
		<div class="space-y-2 py-1.5" aria-hidden="true">
			<div class="h-3 animate-pulse rounded bg-[var(--st-hover)]"></div>
			<div class="h-3 w-4/5 animate-pulse rounded bg-[var(--st-hover)]"></div>
			<div class="h-3 w-3/5 animate-pulse rounded bg-[var(--st-hover)]"></div>
		</div>
	{:else}
		{#each topPages as p, i (p.path)}
			<div
				class="flex items-center gap-3 py-1.5 text-[13px] {i < topPages.length - 1
					? 'border-b border-[var(--st-hairline)]'
					: ''}"
			>
				<span class="min-w-0 flex-1 truncate" title="/{p.path}">/{p.path}</span>
				<div class="h-[5px] w-24 flex-none overflow-hidden rounded-[3px] bg-[var(--st-hairline)]">
					<div
						class="h-full rounded-[3px] bg-[var(--st-chart)]"
						style="width: {Math.max(6, (p.views / topPages[0].views) * 100)}%"
					></div>
				</div>
				<span class="w-12 text-right tabular-nums text-[var(--st-muted)]"
					>{formatCount(p.views, locale)}</span
				>
			</div>
		{/each}
	{/if}
</div>
