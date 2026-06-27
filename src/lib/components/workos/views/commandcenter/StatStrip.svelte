<script lang="ts">
	import type { MyWorkStats } from '../../lib/stats';
	export let stats: MyWorkStats;
	export let active: string | null = null;
	export let onPick: (key: string) => void;

	$: tiles = [
		{ key: 'overdue', label: 'Overdue', value: stats.overdue, danger: stats.overdue > 0 },
		{ key: 'dueToday', label: 'Due today', value: stats.dueToday, danger: false },
		{ key: 'inProgress', label: 'In progress', value: stats.inProgress, danger: false },
		{ key: 'doneThisWeek', label: 'Done this week', value: stats.doneThisWeek, danger: false }
	];
</script>

<div class="grid grid-cols-2 sm:grid-cols-4 gap-2 px-4 pt-3">
	{#each tiles as t (t.key)}
		<button
			type="button"
			class="text-left rounded-lg border px-3 py-2 transition
				{active === t.key ? 'border-primary ring-1 ring-primary' : 'border-gray-200 dark:border-gray-800'}
				{t.danger ? 'bg-red-50 dark:bg-red-950/30' : 'bg-white dark:bg-gray-950'}
				hover:bg-gray-50 dark:hover:bg-gray-900"
			onclick={() => onPick(t.key)}
		>
			<div class="text-xl font-semibold {t.danger ? 'text-red-600 dark:text-red-400' : ''}">{t.value}</div>
			<div class="text-[11px] {t.danger ? 'text-red-600/80 dark:text-red-400/80' : 'text-gray-500'}">{t.label}</div>
		</button>
	{/each}
</div>
