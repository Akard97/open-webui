<script lang="ts">
	import { getContext } from 'svelte';
	import dayjs from 'dayjs';
	import { chartGeometry, nearestIndex, formatCount, type SeriesPoint } from './lib/analytics';

	const i18n = getContext('i18n');

	// Presentational: OverviewTab owns the fetch (and every guard around it)
	// and passes the resolved state down, so the tab can place this card and
	// the Top pages card wherever its layout needs them.
	let {
		days,
		loading,
		failed,
		dataUnknown,
		totals,
		series,
		ownerVisible,
		onRangeChange
	}: {
		days: number;
		loading: boolean;
		failed: boolean;
		// `loading || failed` — computed once by the owner and reused here so
		// no KPI numeral can render a fabricated zero or a stale previous
		// range while the current one is unknown.
		dataUnknown: boolean;
		totals: { views: number; unique_visitors: number; owner_views: number };
		series: SeriesPoint[];
		ownerVisible: boolean;
		onRangeChange: (days: number) => void;
	} = $props();

	const W = 640;
	const H = 112;
	const RANGES = [7, 30, 90];

	let hover = $state<number | null>(null);

	// Counts follow the active UI language; analytics.ts stays pure, so the
	// locale is passed in rather than imported there.
	const locale = $derived($i18n.language);

	const geo = $derived(chartGeometry(series, W, H));
	const isEmpty = $derived(!dataUnknown && totals.views === 0 && totals.owner_views === 0);

	$effect(() => {
		// Read `series` so this re-runs whenever the owner swaps in a new one:
		// a hover index is only meaningful against the series it was measured
		// against, so a range or site change must drop it.
		void series;
		hover = null;
	});

	const onMove = (e: PointerEvent) => {
		const rect = (e.currentTarget as SVGElement).getBoundingClientRect();
		hover = nearestIndex(series, ((e.clientX - rect.left) / rect.width) * W, W);
	};

	// A data label near either edge would clip a centered anchor, so it leans
	// inward instead; the tooltip does the same with its own translate.
	const labelAnchor = (x: number) => (x < 24 ? 'start' : x > W - 24 ? 'end' : 'middle');
	const tipShift = (x: number) => (x < W * 0.12 ? '0%' : x > W * 0.88 ? '-100%' : '-50%');
</script>

<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
	<div class="flex flex-wrap items-start justify-between gap-3">
		<div class="flex gap-8">
			<div>
				<div
					class="text-[10.5px] font-semibold uppercase tracking-[0.07em] text-gray-400 dark:text-gray-500"
				>
					{$i18n.t('Views')}
				</div>
				<div class="mt-1 text-[27px] font-bold leading-none tabular-nums tracking-tight">
					{dataUnknown ? '—' : formatCount(totals.views, locale)}
				</div>
			</div>
			<div>
				<div
					class="text-[10.5px] font-semibold uppercase tracking-[0.07em] text-gray-400 dark:text-gray-500"
					title={$i18n.t(
						'Signed-in viewers are counted once. Anonymous visitors are counted once per day.'
					)}
				>
					{$i18n.t('Unique visitors')}
				</div>
				<div class="mt-1 text-[27px] font-bold leading-none tabular-nums tracking-tight">
					{dataUnknown ? '—' : formatCount(totals.unique_visitors, locale)}
				</div>
			</div>
			{#if ownerVisible}
				<div>
					<div
						class="text-[10.5px] font-semibold uppercase tracking-[0.07em] text-gray-400 dark:text-gray-500"
					>
						{$i18n.t('Yours')}
					</div>
					<div
						class="mt-1 text-[27px] font-bold leading-none tabular-nums tracking-tight text-[var(--st-muted)]"
					>
						{dataUnknown ? '—' : formatCount(totals.owner_views, locale)}
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
					onclick={() => onRangeChange(r)}>{r}{$i18n.t('d')}</button
				>
			{/each}
		</div>
	</div>

	{#if loading}
		<div class="mt-3 h-[112px] animate-pulse rounded-lg bg-[var(--st-hover)]"></div>
	{:else if failed}
		<div
			class="mt-3 flex h-[112px] items-center justify-center text-[13px] text-[var(--st-muted)]"
		>
			{$i18n.t("Couldn't load view data.")}
		</div>
	{:else if isEmpty}
		<div class="mt-3 flex h-[112px] flex-col items-center justify-center gap-1 text-center">
			<div class="text-[13px] font-medium">{$i18n.t('No views yet')}</div>
			<div class="text-xs text-[var(--st-muted)]">
				{$i18n.t('Share the link to start seeing traffic.')}
			</div>
		</div>
	{:else}
		<div class="mt-3">
			<div class="relative">
				<svg
					viewBox="0 0 {W} {H}"
					class="block h-auto w-full touch-pan-y overflow-visible"
					role="img"
					aria-label={$i18n.t('Views over time')}
					onpointermove={onMove}
					onpointerleave={() => (hover = null)}
				>
					<defs>
						<linearGradient id="st-chart-grad" x1="0" y1="0" x2="0" y2="1">
							<stop offset="0" stop-color="var(--st-chart)" stop-opacity="0.22" />
							<stop offset="1" stop-color="var(--st-chart)" stop-opacity="0.02" />
						</linearGradient>
					</defs>
					{#each geo.gridlines as g (g.value)}
						<line
							x1="0"
							y1={g.y}
							x2={W}
							y2={g.y}
							stroke="var(--st-faint)"
							stroke-opacity="0.25"
							stroke-dasharray="3 5"
						/>
						<text
							x="0"
							y={g.y - 4}
							font-size="10"
							fill="var(--st-faint)"
							class="tabular-nums select-none">{formatCount(g.value, locale)}</text
						>
					{/each}
					<path d={geo.area} fill="url(#st-chart-grad)" />
					<path d={geo.line} fill="none" stroke="var(--st-chart)" stroke-width="2" />
					{#each geo.labeled as i (i)}
						<text
							x={geo.points[i][0]}
							y={geo.points[i][1] - 8}
							font-size="10.5"
							font-weight="600"
							fill="var(--st-muted)"
							text-anchor={labelAnchor(geo.points[i][0])}
							class="tabular-nums select-none">{formatCount(series[i].views, locale)}</text
						>
					{/each}
					{#if geo.points.length > 0}
						<circle
							cx={geo.points[geo.points.length - 1][0]}
							cy={geo.points[geo.points.length - 1][1]}
							r="3"
							fill="var(--st-chart)"
						/>
					{/if}
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
				{#if hover !== null && geo.points[hover] && series[hover]}
					<div
						class="pointer-events-none absolute z-10 whitespace-nowrap rounded-md bg-[var(--st-deep)] px-2 py-1 text-[11px] font-medium text-[var(--st-ground)] shadow-sm"
						style="left: {(geo.points[hover][0] / W) * 100}%; top: {(geo.points[hover][1] / H) *
							100}%; transform: translate({tipShift(geo.points[hover][0])}, calc(-100% - 10px));"
					>
						{dayjs(series[hover].day).format('MMM D')} · <span class="tabular-nums"
							>{formatCount(series[hover].views, locale)}</span
						>
						{series[hover].views === 1 ? $i18n.t('view') : $i18n.t('views')}
					</div>
				{/if}
			</div>
			<div class="mt-1.5 flex justify-between text-[11px] text-[var(--st-faint)]">
				{#if series.length > 0}
					<span>{dayjs(series[0].day).format('MMM D')}</span>
					<span>{dayjs(series[series.length - 1].day).format('MMM D')}</span>
				{:else}
					<span>—</span>
					<span>—</span>
				{/if}
			</div>
			<!-- The tooltip is pointer-only; announce the hovered value politely
			     so it isn't silent to assistive tech. -->
			<span class="sr-only" aria-live="polite">
				{#if hover !== null && series[hover]}
					{dayjs(series[hover].day).format('MMM D')}: {formatCount(series[hover].views, locale)}
					{series[hover].views === 1 ? $i18n.t('view') : $i18n.t('views')}
				{/if}
			</span>
		</div>
	{/if}
</div>
