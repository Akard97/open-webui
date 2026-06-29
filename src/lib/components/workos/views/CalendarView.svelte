<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import FilterBar from '../chrome/FilterBar.svelte';
	import DayCell from './calendar/DayCell.svelte';
	import { monthGrid, weekDays, isToday } from '../lib/calendar';
	import { boardFilter } from '../lib/store';

	const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

	let mode: 'month' | 'week' = 'month';
	// Anchor date for the visible period; ephemeral (resets on remount).
	let cursor = new Date();

	$: days = mode === 'month' ? monthGrid(cursor) : weekDays(cursor);
	$: cursorMonth = cursor.getMonth();
	$: label =
		mode === 'month'
			? cursor.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
			: rangeLabel(weekDays(cursor));

	function rangeLabel(w: Date[]): string {
		const f = w[0], l = w[6];
		const opts: Intl.DateTimeFormatOptions = { month: 'short', day: 'numeric' };
		return `${f.toLocaleDateString(undefined, opts)} – ${l.toLocaleDateString(undefined, opts)}, ${l.getFullYear()}`;
	}

	function step(dir: 1 | -1) {
		const c = new Date(cursor);
		if (mode === 'month') c.setMonth(c.getMonth() + dir);
		else c.setDate(c.getDate() + dir * 7);
		cursor = c;
	}
	function today() {
		cursor = new Date();
	}
</script>

<div class="h-full flex flex-col min-h-0">
	<FilterBar filter={boardFilter} />

	<!-- Toolbar -->
	<div class="flex-none flex items-center gap-3 px-4 py-2.5 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
		<div class="flex items-center gap-1">
			<button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-900" title="Previous" onclick={() => step(-1)}><Icon name="chevron-left" size={16} /></button>
			<button class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-900" title="Next" onclick={() => step(1)}><Icon name="chevron-right" size={16} /></button>
		</div>
		<div class="text-base font-semibold">{label}</div>
		<button class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 hover:bg-gray-100 dark:hover:bg-gray-900" onclick={today}>Today</button>
		<div class="flex-1"></div>
		<div class="inline-flex rounded-lg border border-gray-200 dark:border-gray-800 overflow-hidden text-sm">
			<button class="px-3 py-1.5 {mode === 'month' ? 'bg-primary text-primary-foreground' : 'hover:bg-gray-100 dark:hover:bg-gray-900'}" onclick={() => (mode = 'month')}>Month</button>
			<button class="px-3 py-1.5 {mode === 'week' ? 'bg-primary text-primary-foreground' : 'hover:bg-gray-100 dark:hover:bg-gray-900'}" onclick={() => (mode = 'week')}>Week</button>
		</div>
	</div>

	<!-- Grid -->
	<div class="flex-1 overflow-auto p-4 bg-white dark:bg-gray-900">
		<div class="rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
			<div class="grid grid-cols-7 bg-gray-50 dark:bg-gray-950">
				{#each WEEKDAYS as w (w)}
					<div class="px-2 py-1.5 text-xs text-gray-400 border-b border-gray-100 dark:border-gray-900">{w}</div>
				{/each}
			</div>
			<div class="grid grid-cols-7">
				{#each days as d (d.getTime())}
					<DayCell date={d} dimmed={mode === 'month' && d.getMonth() !== cursorMonth} today={isToday(d.getTime(), Date.now())} />
				{/each}
			</div>
		</div>
	</div>
</div>
