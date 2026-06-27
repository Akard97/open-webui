<script lang="ts">
	import Icon from '../../ui/Icon.svelte';
	import type { MyWorkStats } from '../../lib/stats';
	export let stats: MyWorkStats;
	export let active: string | null = null;
	export let onPick: (key: string) => void;

	// Neutral tiles; color lives only in the small icon chip (and a red number when overdue).
	$: tiles = [
		{ key: 'overdue', label: 'Overdue', value: stats.overdue, icon: 'alert-triangle',
			chip: 'bg-red-50 text-red-500 dark:bg-red-500/10 dark:text-red-400', alert: stats.overdue > 0 },
		{ key: 'dueToday', label: 'Due today', value: stats.dueToday, icon: 'calendar',
			chip: 'bg-amber-50 text-amber-500 dark:bg-amber-500/10 dark:text-amber-400', alert: false },
		{ key: 'inProgress', label: 'In progress', value: stats.inProgress, icon: 'loader',
			chip: 'bg-brand-100/70 text-brand-600 dark:bg-brand-900/30 dark:text-brand-300', alert: false },
		{ key: 'doneThisWeek', label: 'Done this week', value: stats.doneThisWeek, icon: 'circle-check',
			chip: 'bg-green-50 text-green-500 dark:bg-green-500/10 dark:text-green-400', alert: false }
	];
</script>

<div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
	{#each tiles as t (t.key)}
		<button
			type="button"
			class="flex items-center gap-3 text-left rounded-xl border bg-white dark:bg-gray-950 px-3.5 py-3 transition-colors
				{active === t.key ? 'border-primary ring-1 ring-primary' : 'border-gray-200 dark:border-gray-800 hover:border-gray-300 dark:hover:border-gray-700'}"
			onclick={() => onPick(t.key)}
		>
			<span class="w-9 h-9 rounded-lg flex items-center justify-center flex-none {t.chip}"><Icon name={t.icon} size={18} /></span>
			<span class="min-w-0">
				<span class="block text-xl font-semibold leading-none tabular-nums {t.alert ? 'text-red-600 dark:text-red-400' : ''}">{t.value}</span>
				<span class="block text-[11px] text-gray-500 dark:text-gray-400 mt-1 truncate">{t.label}</span>
			</span>
		</button>
	{/each}
</div>
