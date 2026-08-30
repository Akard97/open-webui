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
	const H = 96;
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
</script>

<div class="rounded-xl border border-[var(--st-hairline)] px-4 py-3.5">
	<div class="flex flex-wrap items-start justify-between gap-3">
		<div class="flex gap-6">
			<div>
				<div class="text-xs font-medium text-gray-400 dark:text-gray-500">
					{$i18n.t('Views')}
				</div>
				<div class="mt-0.5 text-[21px] font-bold tabular-nums tracking-tight">
					{dataUnknown ? '—' : formatCount(totals.views, locale)}
				</div>
			</div>
			<div>
				<div
					class="text-xs font-medium text-gray-400 dark:text-gray-500"
					title={$i18n.t(
						'Signed-in viewers are counted once. Anonymous visitors are counted once per day.'
					)}
				>
					{$i18n.t('Unique visitors')}
				</div>
				<div class="mt-0.5 text-[21px] font-bold tabular-nums tracking-tight">
					{dataUnknown ? '—' : formatCount(totals.unique_visitors, locale)}
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
			<!-- The hover readout is pointer-only; announce it politely so the
			     value isn't silent to assistive tech. -->
			<div class="mt-1 flex justify-between text-[11px] text-[var(--st-faint)]" aria-live="polite">
				{#if hover !== null && series[hover]}
					<span>{dayjs(series[hover].day).format('MMM D')}</span>
					<span class="tabular-nums"
						>{formatCount(series[hover].views, locale)}
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
