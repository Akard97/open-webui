<script lang="ts">
	import type { OverviewKpis } from '../../lib/overview';

	export let kpis: OverviewKpis;
	export let weeks: 4 | 6 | 12;
	export let onWeeks: (w: 4 | 6 | 12) => void;
	export let workspaceName = '';
	export let workstreamName = '';
	export let taskCount = 0;
	export let peopleCount = 0;

	const WEEK_OPTIONS: (4 | 6 | 12)[] = [4, 6, 12];

	type Tile = { dot: string; label: string; value: string; delta?: { up: boolean; text: string } | null; caption: string };
	$: tiles = [
		{ dot: '#00a5ba', label: 'Open tasks', value: String(kpis.open),
			caption: `${kpis.inProgress} in progress · ${kpis.inReview} in review` },
		{ dot: '#f0b47a', label: 'Due this week', value: String(kpis.dueThisWeek),
			caption: kpis.dueTomorrow ? `${kpis.dueTomorrow} due tomorrow` : 'none tomorrow' },
		{ dot: '#f27d72', label: 'Overdue', value: String(kpis.overdue),
			caption: kpis.oldestOverdueDays != null ? `oldest ${kpis.oldestOverdueDays}d late` : 'all clear' },
		{ dot: '#5DCAA5', label: 'Completed', value: String(kpis.completed7d),
			delta: kpis.completed7d === kpis.completedPrev7d ? null
				: { up: kpis.completed7d > kpis.completedPrev7d, text: `vs ${kpis.completedPrev7d}` },
			caption: 'last 7 days vs prior 7' },
		{ dot: '#8fa3ff', label: 'New tasks', value: String(kpis.new7d), caption: 'added in last 7 days' }
	] satisfies Tile[];
</script>

<section class="rounded-2xl p-4 sm:p-5" style="background:#101623" aria-label="Workstream key figures">
	<div class="flex items-center gap-3 mb-4">
		<div class="min-w-0">
			<div class="text-[11px]" style="color:#7e8aa0">{workspaceName ? `${workspaceName} / ` : ''}{workstreamName}</div>
			<h2 class="text-[17px] font-medium mt-0.5" style="color:#eef2f8">Overview</h2>
		</div>
		<div class="ml-auto text-[11px]" style="color:#7e8aa0">{taskCount} tasks · {peopleCount} people</div>
		<div class="flex rounded-full border p-0.5" style="border-color:#2a3651" role="group" aria-label="Momentum window">
			{#each WEEK_OPTIONS as w (w)}
				<button
					type="button"
					class="px-2.5 py-1 rounded-full text-[11px] font-medium transition-colors"
					style="color:{weeks === w ? '#101623' : '#aab5c8'}; background:{weeks === w ? '#aab5c8' : 'transparent'}"
					aria-pressed={weeks === w}
					onclick={() => onWeeks(w)}
				>{w}w</button>
			{/each}
		</div>
	</div>
	<div class="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-5 gap-2">
		{#each tiles as t (t.label)}
			<div class="rounded-xl px-3 py-2.5 border" style="background:#1b2434;border-color:#232f45"
				aria-label="{t.label}: {t.value}">
				<div class="text-[11px]" style="color:#9aa6ba"><span style="color:{t.dot}">●</span> {t.label}</div>
				<div class="mt-1 text-[22px] font-medium tabular-nums" style="color:#ffffff">
					{t.value}
					{#if t.delta}
						<span class="align-[3px] text-[10.5px] rounded-full px-1.5 py-0.5"
							style="background:{t.delta.up ? '#123c2c' : '#3c1a1a'};color:{t.delta.up ? '#5DCAA5' : '#f27d72'}">
							{t.delta.up ? '↑' : '↓'} {t.delta.text}
						</span>
					{/if}
				</div>
				<div class="mt-1 text-[10.5px]" style="color:#7e8aa0">{t.caption}</div>
			</div>
		{/each}
	</div>
</section>
