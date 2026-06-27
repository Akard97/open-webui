<script lang="ts">
	import type { MyWorkStats, PriorityKey } from '../../lib/stats';
	import { STATUS_COLOR, PRIORITY_COLOR } from '../../lib/colors';
	import { STATUS_ORDER, STATUS_LABEL, type TaskStatus } from '../../lib/types';
	export let stats: MyWorkStats;

	const R = 52;
	const CIRC = 2 * Math.PI * R;
	$: pct = Math.round(stats.completionRate * 100);
	$: offset = CIRC * (1 - stats.completionRate);

	$: statusSegs = ([...STATUS_ORDER, 'canceled'] as TaskStatus[])
		.map((s) => ({ key: s, label: STATUS_LABEL[s], count: stats.byStatus[s], color: STATUS_COLOR[s] }))
		.filter((seg) => seg.count > 0);
	$: statusTotal = statusSegs.reduce((n, s) => n + s.count, 0);

	const PRI_ORDER: PriorityKey[] = ['urgent', 'high', 'medium', 'low', 'none'];
	const PRI_LABEL: Record<PriorityKey, string> = {
		urgent: 'Urgent', high: 'High', medium: 'Medium', low: 'Low', none: 'No priority'
	};
	const PRI_COLOR: Record<PriorityKey, string> = { ...PRIORITY_COLOR, none: '#d1d5db' };
	$: priSegs = PRI_ORDER
		.map((p) => ({ key: p, label: PRI_LABEL[p], count: stats.byPriority[p], color: PRI_COLOR[p] }))
		.filter((seg) => seg.count > 0);
	$: priTotal = priSegs.reduce((n, s) => n + s.count, 0);
</script>

<div class="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950 p-4 flex flex-col gap-5">
	<div class="flex justify-center pt-1">
		<svg width="128" height="128" viewBox="0 0 128 128" class="flex-none" aria-hidden="true">
			<circle cx="64" cy="64" r={R} fill="none" stroke="currentColor" class="text-gray-200 dark:text-gray-800" stroke-width="12" />
			<circle cx="64" cy="64" r={R} fill="none" stroke="currentColor" class="text-primary" stroke-width="12"
				stroke-dasharray={CIRC} stroke-dashoffset={offset} stroke-linecap="round" transform="rotate(-90 64 64)" />
			<text x="64" y="62" text-anchor="middle" fill="currentColor" class="text-gray-900 dark:text-gray-100" style="font-size:26px;font-weight:600">{pct}%</text>
			<text x="64" y="82" text-anchor="middle" fill="currentColor" class="text-gray-400" style="font-size:9px;letter-spacing:0.12em">COMPLETE</text>
		</svg>
	</div>

	<div>
		<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-2">By status</div>
		{#if statusTotal}
			<div class="flex h-2.5 rounded-full overflow-hidden">
				{#each statusSegs as s (s.key)}
					<div style="width:{(s.count / statusTotal) * 100}%; background:{s.color}" title="{s.label}: {s.count}"></div>
				{/each}
			</div>
			<div class="flex flex-wrap gap-x-3 gap-y-1 mt-2.5">
				{#each statusSegs as s (s.key)}
					<span class="inline-flex items-center gap-1.5 text-[11px] text-gray-500 dark:text-gray-400">
						<span class="w-2 h-2 rounded-full" style="background:{s.color}"></span>{s.label} {s.count}
					</span>
				{/each}
			</div>
		{:else}
			<div class="text-[11px] text-gray-400">No tasks</div>
		{/if}
	</div>

	<div>
		<div class="text-[11px] uppercase tracking-wide text-gray-400 font-semibold mb-2">By priority</div>
		{#if priTotal}
			<div class="flex h-2.5 rounded-full overflow-hidden">
				{#each priSegs as s (s.key)}
					<div style="width:{(s.count / priTotal) * 100}%; background:{s.color}" title="{s.label}: {s.count}"></div>
				{/each}
			</div>
			<div class="flex flex-wrap gap-x-3 gap-y-1 mt-2.5">
				{#each priSegs as s (s.key)}
					<span class="inline-flex items-center gap-1.5 text-[11px] text-gray-500 dark:text-gray-400">
						<span class="w-2 h-2 rounded-full" style="background:{s.color}"></span>{s.label} {s.count}
					</span>
				{/each}
			</div>
		{:else}
			<div class="text-[11px] text-gray-400">No tasks</div>
		{/if}
	</div>
</div>
