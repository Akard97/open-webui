<script lang="ts">
	import { tick } from 'svelte';
	import Icon from '../ui/Icon.svelte';
	import FilterBar from '../chrome/FilterBar.svelte';
	import TimelineHeader from './timeline/TimelineHeader.svelte';
	import TimelineRail from './timeline/TimelineRail.svelte';
	import TimelineBar from './timeline/TimelineBar.svelte';
	import {
		boardFilter, filteredTasks, currentWorkstream, timelineZoom, addTask
	} from '../lib/store';
	import {
		timelineItems, computeWindow, todayDay, todayLineX, dayToX, isWeekend, dayToTs,
		ZOOM_ORDER, ZOOM_DAY_WIDTH
	} from '../lib/timeline';

	const RAIL_W = 260;
	const ROW_H = 46;
	$: railW = RAIL_W;

	// `now` refreshes when the workstream changes so the today line/slip tails
	// stay correct in long-lived sessions.
	let now = Date.now();
	$: today = todayDay(now);
	$: items = timelineItems($filteredTasks);
	$: win = computeWindow(items, today);
	$: dayWidth = ZOOM_DAY_WIDTH[$timelineZoom];
	$: chartW = win.days * dayWidth;
	$: tlx = todayLineX(today, win, dayWidth);
	$: weekendDays = Array.from({ length: win.days }, (_, i) => win.startDay + i).filter(isWeekend);
	// Vertical gridline period: per-day when readable, per-week at quarter zoom.
	$: gridPeriod = dayWidth >= 16 ? dayWidth : dayWidth * 7;
	// Weekly gridlines must land on Mondays: UTC day 0 (1970-01-01) is a Thursday,
	// so a day index d is a Monday when d % 7 === 4. Shift the gradient accordingly.
	$: gridOffset = dayWidth >= 16 ? 0 : ((4 - (win.startDay % 7) + 7) % 7) * dayWidth;

	let scroller: HTMLElement | null = null;
	function scrollToToday() {
		if (!scroller) return;
		scroller.scrollLeft = Math.max(0, railW + tlx - scroller.clientWidth * 0.3);
	}
	// Initial scroll per workstream + zoom (re-anchors today after either changes).
	let scrolledFor = '';
	$: {
		const key = `${$currentWorkstream?.id ?? ''}:${$timelineZoom}`;
		if (scroller && scrolledFor !== key) {
			scrolledFor = key;
			now = Date.now();
			tick().then(scrollToToday);
		}
	}

	// Toolbar quick-add: schedules for today so the task appears on the chart.
	let creatingNew = false;
	let newTitle = '';
	async function submitNew() {
		const ws = $currentWorkstream;
		const title = newTitle.trim();
		if (!title || !ws) return;
		newTitle = '';
		creatingNew = false;
		const ts = dayToTs(todayDay(Date.now()));
		await addTask(ws.id, { title, start_date: ts, due_date: ts });
	}
</script>

<div class="h-full flex flex-col min-h-0">
	<FilterBar filter={boardFilter}>
		<!-- Zoom presets -->
		<div class="inline-flex items-center gap-0.5 rounded-full bg-gray-100 dark:bg-gray-900 p-0.5 text-sm">
			{#each ZOOM_ORDER as z (z)}
				<button
					type="button"
					aria-pressed={$timelineZoom === z}
					class="px-3 py-1 rounded-full transition capitalize {$timelineZoom === z ? 'bg-primary text-primary-foreground shadow-sm' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}"
					onclick={() => timelineZoom.set(z)}
				>{z}</button>
			{/each}
		</div>
		<button
			type="button"
			class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 hover:bg-gray-100 dark:hover:bg-gray-900 transition"
			onclick={() => { now = Date.now(); scrollToToday(); }}
		>Today</button>
		{#if creatingNew}
			<!-- svelte-ignore a11y_autofocus -->
			<input
				class="text-sm px-2 py-1.5 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent w-48"
				placeholder="Task title…"
				bind:value={newTitle}
				onkeydown={(e) => { if (e.key === 'Enter') submitNew(); if (e.key === 'Escape') { creatingNew = false; newTitle = ''; } }}
				autofocus
			/>
		{:else}
			<button class="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground text-sm font-medium" onclick={() => { creatingNew = true; newTitle = ''; }}>
				<Icon name="plus" size={15} /> Add new
			</button>
		{/if}
	</FilterBar>

	<div class="flex-1 flex min-h-0 bg-white dark:bg-gray-950">
		<!-- Chart: one scroller for both axes; header sticky top, rail cells sticky left -->
		<div bind:this={scroller} class="flex-1 overflow-auto min-w-0">
			<TimelineHeader {win} {dayWidth} zoom={$timelineZoom} {today} {railW} />

			<div class="relative" style="width: {railW + chartW}px;">
				<!-- Background layer: weekends, gridlines, today line -->
				<div class="absolute top-0 bottom-0 pointer-events-none" style="left: {railW}px; width: {chartW}px;">
					{#each weekendDays as d (d)}
						<div class="absolute top-0 bottom-0 bg-gray-50 dark:bg-gray-900/40" style="left: {dayToX(d, win, dayWidth)}px; width: {dayWidth}px; background-image: repeating-linear-gradient(-45deg, rgb(0 0 0 / 0.025), rgb(0 0 0 / 0.025) 4px, transparent 4px, transparent 8px);"></div>
					{/each}
					<div class="absolute inset-0" style="background: repeating-linear-gradient(to right, transparent, transparent {gridPeriod - 1}px, rgb(0 0 0 / 0.05) {gridPeriod - 1}px, rgb(0 0 0 / 0.05) {gridPeriod}px); background-position: {gridOffset}px 0;"></div>
					<div class="absolute top-0 bottom-0 w-0.5 bg-primary z-10" style="left: {tlx}px;">
						<span class="absolute top-0 -left-[17px] px-1 py-px rounded bg-primary text-primary-foreground text-[8px] font-bold tracking-wide">TODAY</span>
					</div>
				</div>

				<!-- Rows -->
				{#if items.length}
					{#each items as item (item.task.id)}
						<div class="flex border-b border-gray-100 dark:border-gray-900" style="height: {ROW_H}px;">
							<div class="sticky left-0 z-20 flex-none bg-white dark:bg-gray-950 border-r border-gray-100 dark:border-gray-900" style="width: {railW}px;">
								<TimelineRail {item} {today} />
							</div>
							<div class="relative flex-none" style="width: {chartW}px;">
								<TimelineBar {item} {win} {dayWidth} {today} />
							</div>
						</div>
					{/each}
				{:else}
					<div class="flex flex-col items-center justify-center gap-2 py-16 text-center" style="width: {railW + chartW}px;">
						<span class="sticky left-0 flex flex-col items-center gap-2 text-gray-400 dark:text-gray-500" style="max-width: 100vw;">
							<Icon name="chart-gantt" size={28} />
							<span class="text-sm">Nothing scheduled yet — add dates to tasks or create one with “Add new”.</span>
						</span>
					</div>
				{/if}
			</div>
		</div>
	</div>
</div>
