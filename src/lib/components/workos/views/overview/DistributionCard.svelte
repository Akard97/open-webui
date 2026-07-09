<script lang="ts">
	import { STATUS_COLOR, PRIORITY_COLOR } from '../../lib/colors';
	import { STATUS_LABEL } from '../../lib/types';
	import type { PriorityPair, StatusSlice } from '../../lib/overview';

	export let pairs: PriorityPair[];
	export let mix: { total: number; slices: StatusSlice[] };
	export let daily: { day: string; n: number }[];
	export let loaded = false;
	export let error = false;

	$: maxDaily = Math.max(1, ...daily.map((d) => d.n));
	// Intensity: quiet base for zero, then three teal steps by share of the busiest day.
	function stripColor(n: number): string {
		if (n === 0) return 'rgb(0 165 186 / 0.12)';
		const r = n / maxDaily;
		return r > 0.66 ? '#00a5ba' : r > 0.33 ? '#49b9c8' : '#8fd2dd';
	}
	function stripHeight(n: number): number {
		return n === 0 ? 4 : Math.max(8, Math.round((n / maxDaily) * 34));
	}
	const pairColor = (p: PriorityPair): string =>
		p.key === 'none' ? '' : `color:${PRIORITY_COLOR[p.key]}`;
	$: hasActivity = daily.some((d) => d.n > 0);
</script>

<section class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 min-w-0">
	<h3 class="text-[13.5px] font-medium">Distribution</h3>
	<p class="text-[11px] text-gray-400 mt-0.5">Open tasks by priority and status.</p>

	<div class="grid grid-cols-2 gap-x-3 gap-y-2 mt-3 text-[11px] text-gray-500 dark:text-gray-400">
		{#each pairs as p (p.key)}
			<div>
				{p.label}
				<div class="text-[16px] font-medium tabular-nums text-gray-900 dark:text-gray-100" style={pairColor(p)}>{p.n}</div>
			</div>
		{/each}
	</div>

	<div class="flex h-[9px] rounded-full overflow-hidden mt-4 bg-gray-100 dark:bg-gray-800" role="img"
		aria-label="Status mix: {mix.slices.map((s) => `${STATUS_LABEL[s.status]} ${s.n}`).join(', ')}">
		{#each mix.slices as s (s.status)}
			{#if s.n > 0}<div class:hatch-canceled={s.status === 'canceled'} style="width:{s.pct}%;background-color:{STATUS_COLOR[s.status]}"></div>{/if}
		{/each}
	</div>
	<div class="flex gap-x-2.5 gap-y-1 flex-wrap mt-2 text-[10.5px] text-gray-500 dark:text-gray-400">
		{#each mix.slices as s (s.status)}
			{#if s.n > 0}<span>{#if s.status === 'canceled'}<span class="hatch-canceled inline-block w-[7px] h-[7px] rounded-full align-middle" style="background-color:{STATUS_COLOR[s.status]}"></span>{:else}<span style="color:{STATUS_COLOR[s.status]}">●</span>{/if} {STATUS_LABEL[s.status]} {s.n}</span>{/if}
		{/each}
	</div>

	<div class="text-[11px] text-gray-400 mt-4">Activity · last 14 days</div>
	{#if error}
		<div class="text-[11px] text-gray-400 mt-2">Couldn't load activity.</div>
	{:else if !loaded}
		<div class="h-[34px] mt-1.5 rounded bg-gray-100 dark:bg-gray-800 animate-pulse"></div>
	{:else}
		<div class="flex items-end gap-[5px] mt-1.5 h-[34px]" role="img"
			aria-label={hasActivity ? `Daily activity, busiest day ${maxDaily} events` : 'No activity in the last 14 days'}>
			{#each daily as d (d.day)}
				<div class="w-2 rounded" title="{d.day} · {d.n}" style="height:{stripHeight(d.n)}px;background:{stripColor(d.n)}"></div>
			{/each}
		</div>
	{/if}
</section>

<style>
	/* Disambiguates canceled from backlog where both share STATUS_COLOR's gray — reads as "void". */
	.hatch-canceled {
		background-image: repeating-linear-gradient(-45deg, transparent 0 3px, rgba(255, 255, 255, 0.55) 3px 5px);
	}
</style>
