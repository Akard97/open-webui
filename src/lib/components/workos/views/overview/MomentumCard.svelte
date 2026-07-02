<script lang="ts">
	import * as Chart from '$lib/components/ui/chart';
	import { BarChart } from 'layerchart';
	import { scaleBand } from 'd3-scale';
	import type { WeekBin, CompletionTime } from '../../lib/overview';

	export let bins: WeekBin[];
	export let completion: CompletionTime;

	const config = {
		created: { label: 'Created', color: '#c5e8ee' },
		completed: { label: 'Completed', color: '#00a5ba' }
	} satisfies Chart.ChartConfig;

	$: data = bins.map((b) => ({
		week: b.current ? `${b.label} (this week)` : b.label,
		created: b.created,
		completed: b.completed
	}));

	// Completion-time delta: lower is better → ▾ green when faster, ▴ red when slower.
	$: delta =
		completion.avgDays != null && completion.prevAvgDays != null && completion.avgDays !== completion.prevAvgDays
			? { faster: completion.avgDays < completion.prevAvgDays,
				text: Math.abs(Math.round((completion.avgDays - completion.prevAvgDays) * 10) / 10).toFixed(1) }
			: null;
</script>

<section class="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 min-w-0">
	<div class="flex items-start gap-2 mb-2">
		<div>
			<h3 class="text-[13.5px] font-medium">Weekly momentum</h3>
			<p class="text-[11px] text-gray-400 mt-0.5">Tasks created vs completed per week.</p>
		</div>
	</div>
	<Chart.Container {config} class="h-[190px] w-full" aria-label="Created versus completed tasks per week">
		<BarChart
			{data}
			x="week"
			xScale={scaleBand().padding(0.3)}
			axis="x"
			seriesLayout="group"
			series={[
				{ key: 'created', label: 'Created', color: config.created.color },
				{ key: 'completed', label: 'Completed', color: config.completed.color }
			]}
			props={{ bars: { radius: 4, 'stroke-width': 0 }, xAxis: { format: (v: string) => v.replace(' (this week)', ' ·') } }}
		>
			{#snippet tooltip()}
				<Chart.Tooltip />
			{/snippet}
		</BarChart>
	</Chart.Container>
	<div class="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2 text-[11px] text-gray-500 dark:text-gray-400">
		<span><span style="color:#c5e8ee">●</span> Created</span>
		<span><span style="color:#00a5ba">●</span> Completed</span>
		<span class="ml-auto">
			avg completion time
			<b class="font-medium text-gray-900 dark:text-gray-100">{completion.avgDays != null ? `${completion.avgDays}d` : '—'}</b>
			{#if delta}
				<span class={delta.faster ? 'text-green-700 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
					{delta.faster ? '▾' : '▴'}{delta.text}
				</span>
			{/if}
		</span>
	</div>
</section>
