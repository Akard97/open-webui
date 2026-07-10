<script lang="ts">
	import type { OverviewKpis } from '../../lib/overview';
	import KpiNumeral from '../../ui/KpiNumeral.svelte';

	export let kpis: OverviewKpis;
	export let weeks: 4 | 6 | 12;
	export let onWeeks: (w: 4 | 6 | 12) => void;
	export let workspaceName = '';
	export let workstreamName = '';
	export let taskCount = 0;
	export let peopleCount = 0;

	const WEEK_OPTIONS: (4 | 6 | 12)[] = [4, 6, 12];

	// Dot hues are data colors from the token layer (D2/D3); "new tasks" is
	// deliberately neutral gray-500 (user decision 2026-07-10, no creation hue).
	type Tile = { dot: string; label: string; value: string; delta?: { up: boolean; text: string } | null; caption: string };
	$: tiles = [
		{ dot: 'var(--wos-status-in-progress)', label: 'Open tasks', value: String(kpis.open),
			caption: `${kpis.inProgress} in progress · ${kpis.inReview} in review` },
		{ dot: 'var(--wos-due)', label: 'Due this week', value: String(kpis.dueThisWeek),
			caption: kpis.dueTomorrow ? `${kpis.dueTomorrow} due tomorrow` : 'none tomorrow' },
		{ dot: 'var(--wos-danger)', label: 'Overdue', value: String(kpis.overdue),
			caption: kpis.oldestOverdueDays != null ? `oldest ${kpis.oldestOverdueDays}d late` : 'all clear' },
		{ dot: 'var(--wos-done)', label: 'Completed', value: String(kpis.completed7d),
			delta: kpis.completed7d === kpis.completedPrev7d ? null
				: { up: kpis.completed7d > kpis.completedPrev7d, text: `vs ${kpis.completedPrev7d}` },
			caption: 'last 7 days vs prior 7' },
		{ dot: 'var(--color-gray-500)', label: 'New tasks', value: String(kpis.new7d), caption: 'added in last 7 days' }
	] satisfies Tile[];
</script>

<section
	class="rounded-xl border border-gray-200 bg-white p-4 sm:p-5 dark:border-gray-800 dark:bg-gray-900"
	aria-label="Workstream key figures"
>
	<div class="mb-4 flex flex-wrap items-center gap-3">
		<div class="min-w-0">
			<div class="text-[11px] font-medium text-gray-400 dark:text-gray-500">{workspaceName ? `${workspaceName} / ` : ''}{workstreamName}</div>
			<h2 class="wos-heading mt-0.5 text-gray-900 dark:text-gray-100">Overview</h2>
		</div>
		<div class="ml-auto text-[11px] text-gray-400 dark:text-gray-500">{taskCount} tasks · {peopleCount} people</div>
		<div class="flex rounded-full bg-gray-100 p-0.5 dark:bg-gray-800" role="group" aria-label="Momentum window">
			{#each WEEK_OPTIONS as w (w)}
				<button
					type="button"
					class="rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors
						{weeks === w ? 'bg-primary text-primary-foreground shadow-sm' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}"
					aria-pressed={weeks === w}
					onclick={() => onWeeks(w)}
				>{w}w</button>
			{/each}
		</div>
	</div>
	<div class="grid grid-cols-2 gap-4 sm:grid-cols-3 xl:grid-cols-5 xl:gap-0 xl:divide-x xl:divide-gray-100 xl:dark:divide-gray-800">
		{#each tiles as t (t.label)}
			<div class="min-w-0 xl:px-4 xl:first:pl-0 xl:last:pr-0" aria-label="{t.label}: {t.value}">
				<div class="flex items-center gap-1.5 text-[11px] font-medium text-gray-500 dark:text-gray-400">
					<span class="h-2 w-2 flex-none rounded-full" style="background:{t.dot}"></span>{t.label}
				</div>
				<div class="mt-1.5"><KpiNumeral value={t.value} delta={t.delta ?? null} /></div>
				<div class="mt-1 text-[11px] text-gray-400 dark:text-gray-500">{t.caption}</div>
			</div>
		{/each}
	</div>
</section>
