<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import type { MyWorkStats } from '../../lib/stats';
	export let stats: MyWorkStats;
	export let active: string | null = null;
	export let onPick: (key: string) => void;

	// Each KPI owns an accent + icon so the row reads as mission-control, not a flat table.
	$: tiles = [
		{ key: 'overdue', label: 'Overdue', value: stats.overdue, icon: 'alert-triangle',
			fill: 'bg-red-50 dark:bg-red-500/10', fg: 'text-red-600 dark:text-red-400' },
		{ key: 'dueToday', label: 'Due today', value: stats.dueToday, icon: 'calendar',
			fill: 'bg-amber-50 dark:bg-amber-500/10', fg: 'text-amber-600 dark:text-amber-400' },
		{ key: 'inProgress', label: 'In progress', value: stats.inProgress, icon: 'loader',
			fill: 'bg-brand-100/60 dark:bg-brand-900/30', fg: 'text-brand-700 dark:text-brand-200' },
		{ key: 'doneThisWeek', label: 'Done this week', value: stats.doneThisWeek, icon: 'circle-check',
			fill: 'bg-green-50 dark:bg-green-500/10', fg: 'text-green-600 dark:text-green-400' }
	];
</script>

<div class="grid grid-cols-2 sm:grid-cols-4 gap-3 px-4 pt-3">
	{#each tiles as t (t.key)}
		<button
			type="button"
			class="text-left rounded-xl px-4 py-3 transition {t.fill} {t.fg}
				{active === t.key ? 'ring-2 ring-inset ring-current' : 'hover:ring-1 hover:ring-inset hover:ring-current'}"
			onclick={() => onPick(t.key)}
		>
			<div class="flex items-center justify-between">
				<span class="text-2xl font-semibold leading-none tabular-nums">{t.value}</span>
				<Icon name={t.icon} size={18} />
			</div>
			<div class="text-xs mt-2 opacity-80">{t.label}</div>
		</button>
	{/each}
</div>
