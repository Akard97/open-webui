<script lang="ts">
	import { getContext } from 'svelte';
	import dayjs from 'dayjs';
	import { getSiteAnalytics } from '$lib/apis/sites';
	import { chartGeometry, nearestIndex, formatCount, type SeriesPoint } from './lib/analytics';

	const i18n = getContext('i18n');

	let { site }: { site: any } = $props();

	const W = 640;
	const H = 96;
	const RANGES = [7, 30, 90];

	let days = $state(30);
	let loading = $state(true);
	let failed = $state(false);
	let totals = $state({ views: 0, unique_visitors: 0, owner_views: 0 });
	let series = $state<SeriesPoint[]>([]);
	let topPages = $state<{ path: string; views: number }[]>([]);
	let hover = $state<number | null>(null);
	// Sticky across reloads: only a resolved response updates it, so a
	// loading/failed window in between never yanks the "Yours" stat in or out.
	let ownerVisible = $state(false);

	// Request-generation counter shared by every trigger that re-runs the
	// $effect below (range AND site — see the effect for why a site change
	// re-runs it too). A response is only applied if no newer request — for
	// either a different range or a different site — has started since, so a
	// slow stale response can never paint another range's, or another site's,
	// numbers under the current header.
	let loadSeq = 0;

	const geo = $derived(chartGeometry(series, W, H));
	const isEmpty = $derived(!loading && !failed && totals.views === 0 && totals.owner_views === 0);
	const dataUnknown = $derived(loading || failed);

	const load = async (window: number) => {
		const seq = ++loadSeq;
		loading = true;
		failed = false;
		hover = null;
		try {
			const res = await getSiteAnalytics(localStorage.token, site.id, window);
			if (seq !== loadSeq) return;
			totals = res.totals;
			series = res.series;
			topPages = res.top_pages;
			ownerVisible = res.totals.owner_views > 0;
		} catch (err) {
			if (seq !== loadSeq) return;
			// Analytics is one card, not the whole tab — surface it inline and
			// let the rest of Overview render normally.
			console.error(err);
			failed = true;
		}
		loading = false;
	};

	$effect(() => {
		// site.id is read inside load(), synchronously before its first await,
		// so this effect depends on `site` too — not just `days`. That means a
		// rail selection change re-runs it exactly like a range change does,
		// and the shared loadSeq counter above covers both.
		load(days);
	});

	const onMove = (e: PointerEvent) => {
		const rect = (e.currentTarget as SVGElement).getBoundingClientRect();
		hover = nearestIndex(series, ((e.clientX - rect.left) / rect.width) * W, W);
	};
</script>

<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
	<div class="flex flex-wrap items-start justify-between gap-3">
		<div class="flex gap-6">
			<div>
				<div class="text-xs font-medium text-gray-400 dark:text-gray-500">
					{$i18n.t('Views')}
				</div>
				<div class="mt-0.5 text-[21px] font-bold tabular-nums tracking-tight">
					{dataUnknown ? '—' : formatCount(totals.views)}
				</div>
			</div>
			<div>
				<div class="text-xs font-medium text-gray-400 dark:text-gray-500">
					{$i18n.t('Unique visitors')}
				</div>
				<div class="mt-0.5 text-[21px] font-bold tabular-nums tracking-tight">
					{dataUnknown ? '—' : formatCount(totals.unique_visitors)}
				</div>
			</div>
			{#if ownerVisible}
				<div>
					<div class="text-xs font-medium text-gray-400 dark:text-gray-500">
						{$i18n.t('Yours')}
					</div>
					<div
						class="mt-0.5 text-[21px] font-bold tabular-nums tracking-tight text-[var(--st-muted)]"
					>
						{dataUnknown ? '—' : formatCount(totals.owner_views)}
					</div>
				</div>
			{/if}
		</div>

		<div class="flex gap-0.5" role="group" aria-label={$i18n.t('Time range')}>
			{#each RANGES as r (r)}
				<button
					type="button"
					aria-pressed={days === r}
					class="st-press rounded-[7px] px-2 py-1 text-xs transition-colors duration-150
						{days === r
						? 'bg-[var(--st-accent-soft)] font-semibold text-[var(--st-accent-soft-ink)]'
						: 'font-medium text-[var(--st-muted)] hover:bg-[var(--st-hover)] hover:text-[var(--st-ink)]'}"
					onclick={() => (days = r)}>{r}{$i18n.t('d')}</button
				>
			{/each}
		</div>
	</div>

	{#if loading}
		<div class="mt-3 h-[96px] animate-pulse rounded-lg bg-[var(--st-hover)]"></div>
	{:else if failed}
		<div class="mt-3 flex h-[96px] items-center justify-center text-[13px] text-[var(--st-muted)]">
			{$i18n.t("Couldn't load view data.")}
		</div>
	{:else if isEmpty}
		<div class="mt-3 flex h-[96px] flex-col items-center justify-center gap-1 text-center">
			<div class="text-[13px] font-medium">{$i18n.t('No views yet')}</div>
			<div class="text-xs text-[var(--st-muted)]">
				{$i18n.t('Share the link to start seeing traffic.')}
			</div>
		</div>
	{:else}
		<div class="relative mt-3">
			<svg
				viewBox="0 0 {W} {H}"
				class="block h-auto w-full touch-pan-y"
				role="img"
				aria-label={$i18n.t('Views over time')}
				onpointermove={onMove}
				onpointerleave={() => (hover = null)}
			>
				<path d={geo.area} fill="var(--st-chart-fill)" />
				<path d={geo.line} fill="none" stroke="var(--st-chart)" stroke-width="2" />
				{#if hover !== null && geo.points[hover]}
					<line
						x1={geo.points[hover][0]}
						y1="0"
						x2={geo.points[hover][0]}
						y2={H}
						stroke="var(--st-chart)"
						stroke-width="1"
						opacity="0.35"
					/>
					<circle
						cx={geo.points[hover][0]}
						cy={geo.points[hover][1]}
						r="3.5"
						fill="var(--st-chart)"
					/>
				{/if}
			</svg>
			<div class="mt-1 flex justify-between text-[11px] text-[var(--st-faint)]">
				{#if hover !== null && series[hover]}
					<span>{dayjs(series[hover].day).format('MMM D')}</span>
					<span class="tabular-nums"
						>{formatCount(series[hover].views)}
						{series[hover].views === 1 ? $i18n.t('view') : $i18n.t('views')}</span
					>
				{:else if series.length > 0}
					<span>{dayjs(series[0].day).format('MMM D')}</span>
					<span>{dayjs(series[series.length - 1].day).format('MMM D')}</span>
				{:else}
					<span>—</span>
					<span>—</span>
				{/if}
			</div>
		</div>
	{/if}
</div>

{#if !loading && !failed && topPages.length > 0}
	<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
		<h4 class="mb-2 text-xs font-medium text-gray-400 dark:text-gray-500">
			{$i18n.t('Top pages')}
		</h4>
		{#each topPages as p, i (p.path)}
			<div
				class="flex items-center gap-3 py-1.5 text-[13px] {i < topPages.length - 1
					? 'border-b border-[var(--st-hairline)]'
					: ''}"
			>
				<span class="min-w-0 flex-1 truncate">/{p.path}</span>
				<div
					class="h-[5px] rounded-[3px] bg-[var(--st-chart)]"
					style="width: {Math.max(6, (p.views / topPages[0].views) * 96)}px"
				></div>
				<span class="w-12 text-right tabular-nums text-[var(--st-muted)]"
					>{formatCount(p.views)}</span
				>
			</div>
		{/each}
	</div>
{/if}
