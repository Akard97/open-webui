<script lang="ts">
	import { getContext } from 'svelte';

	const i18n = getContext('i18n');

	const data = [
		12, 18, 15, 22, 30, 26, 34, 41, 38, 52, 47, 63, 58, 71, 66, 80, 74, 92, 88, 105, 98, 120,
		112, 131, 124, 140, 133, 151, 146, 162
	];
	const W = 560;
	const H = 120;
	const mx = Math.max(...data);
	const pts = data.map(
		(v, i) =>
			[(i / (data.length - 1)) * W, H - 8 - (v / mx) * (H - 20)] as [number, number]
	);
	const line = pts.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(' ');
	const last = pts[pts.length - 1];

	const topPages: [string, string, number][] = [
		['index.html', '1,904', 100],
		['policies.html', '712', 37],
		['cover.png', '231', 12]
	];
</script>

<div class="st-pane flex flex-col gap-3.5">
	<div class="rounded-xl border border-[var(--st-hairline)] p-4">
		<h4 class="text-[13px] font-semibold">{$i18n.t('Views · last 30 days')}</h4>
		<div class="mb-2.5 text-xs text-[var(--st-faint)]">
			{$i18n.t('Sample data — this ships in a later phase.')}
		</div>
		<svg viewBox="0 0 {W} {H}" class="block h-auto w-full" role="img" aria-label={$i18n.t('Views · last 30 days')}>
			<path d="{line} L{W},{H} L0,{H} Z" fill="var(--st-chart-fill)" />
			<path d={line} fill="none" stroke="var(--st-chart)" stroke-width="2" />
			<circle cx={last[0]} cy={last[1]} r="3.5" fill="var(--st-chart)" />
		</svg>
	</div>

	<div class="grid grid-cols-1 gap-3 sm:grid-cols-3">
		{#each [[$i18n.t('Total views'), '2,847'], [$i18n.t('Unique visitors'), '391'], [$i18n.t('Avg. time on page'), '1:42']] as [k, v] (k)}
			<div class="rounded-xl border border-[var(--st-hairline)] px-3.5 py-3">
				<div class="text-xs font-medium text-gray-400 dark:text-gray-500">
					{k}
				</div>
				<div class="mt-0.5 text-[21px] font-bold tabular-nums tracking-tight">{v}</div>
				<div class="text-[11.5px] text-[var(--st-muted)]">{$i18n.t('Sample data')}</div>
			</div>
		{/each}
	</div>

	<div class="rounded-xl border border-[var(--st-hairline)] p-4">
		<h4 class="text-[13px] font-semibold">{$i18n.t('Top pages')}</h4>
		<div class="mb-2.5 text-xs text-[var(--st-faint)]">{$i18n.t('Sample data')}</div>
		<div class="overflow-x-auto">
			<table class="w-full border-collapse text-[13px]">
				<thead>
					<tr>
						<th
							class="border-b border-[var(--st-hairline)] py-1.5 text-left text-xs font-medium text-gray-400 dark:text-gray-500"
							>{$i18n.t('Page')}</th
						>
						<th
							class="w-28 border-b border-[var(--st-hairline)] py-1.5 text-left text-xs font-medium text-gray-400 dark:text-gray-500"
							>{$i18n.t('Views')}</th
						>
						<th class="w-44 border-b border-[var(--st-hairline)]"></th>
					</tr>
				</thead>
				<tbody>
					{#each topPages as [page, views, pct] (page)}
						<tr>
							<td
								class="border-b border-[var(--st-hairline)] py-2 text-[12.5px] last:border-b-0"
								>/{page}</td
							>
							<td class="border-b border-[var(--st-hairline)] py-2 tabular-nums">{views}</td>
							<td class="border-b border-[var(--st-hairline)] py-2">
								<div class="h-[5px] rounded-[3px] bg-[var(--st-chart)]" style="width: {pct}%"></div>
							</td>
						</tr>
					{/each}
				</tbody>
			</table>
		</div>
	</div>
</div>
