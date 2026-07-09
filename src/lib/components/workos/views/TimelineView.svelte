<script lang="ts">
	import { tick } from 'svelte';
	import Icon from '../ui/Icon.svelte';
	import FilterBar from '../chrome/FilterBar.svelte';
	import TimelineHeader from './timeline/TimelineHeader.svelte';
	import TimelineRail from './timeline/TimelineRail.svelte';
	import TimelineBar from './timeline/TimelineBar.svelte';
	import UnscheduledPanel from './timeline/UnscheduledPanel.svelte';
	import { toast } from 'svelte-sonner';
	import { mobile } from '$lib/stores';
	import {
		boardFilter, filteredTasks, currentWorkstream, timelineZoom, addTask, editTask, openTask
	} from '../lib/store';
	import {
		timelineItems, computeWindow, todayDay, todayLineX, dayToX, isWeekend, dayToTs,
		ZOOM_ORDER, ZOOM_DAY_WIDTH, MIN_WINDOW_DAYS, unscheduledTasks, xToDay, monthSpans
	} from '../lib/timeline';
	import { STATUS_COLOR } from '../lib/colors';

	const RAIL_W = 260;
	$: railW = $mobile ? 150 : RAIL_W;
	$: rowH = $mobile ? 40 : 46;

	// `now` refreshes when the workstream changes so the today line/slip tails
	// stay correct in long-lived sessions.
	let now = Date.now();
	$: today = todayDay(now);
	$: items = timelineItems($filteredTasks);
	$: dayWidth = ZOOM_DAY_WIDTH[$timelineZoom];
	// The window always covers at least the viewport (plus headroom), so coarse
	// zooms never leave blank space after the last data-driven month.
	let scrollerW = 0;
	$: viewportDays = scrollerW ? Math.ceil((scrollerW - railW) / dayWidth) + 21 : 0;
	$: win = computeWindow(items, today, Math.max(MIN_WINDOW_DAYS, viewportDays));
	$: chartW = win.days * dayWidth;
	$: tlx = todayLineX(today, win, dayWidth);
	$: weekendDays = Array.from({ length: win.days }, (_, i) => win.startDay + i).filter(isWeekend);
	// Vertical gridlines follow the column unit: per-day at Day zoom, per-week at
	// Week zoom (Monday-aligned: UTC day 0 (1970-01-01) is a Thursday, so a day
	// index d is a Monday when d % 7 === 4). Month zoom draws per-month boundary
	// lines instead (variable lengths — a repeating gradient can't express them).
	$: gridPeriod = $timelineZoom === 'day' ? dayWidth : dayWidth * 7;
	$: gridOffset = $timelineZoom === 'day' ? 0 : ((4 - (win.startDay % 7) + 7) % 7) * dayWidth;
	$: monthStarts = $timelineZoom === 'month' ? monthSpans(win).slice(1).map((s) => s.startDay) : [];

	let scroller: HTMLElement | null = null;
	function scrollToToday() {
		if (!scroller) return;
		scroller.scrollLeft = Math.max(0, tlx - (scroller.clientWidth - railW) * 0.3);
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
		try {
			await addTask(ws.id, { title, start_date: ts, due_date: ts });
		} catch {
			toast.error('Failed to create task');
			// Give the title back — unless the user already started another entry.
			if (!creatingNew && !newTitle) {
				creatingNew = true;
				newTitle = title;
			}
		}
	}

	$: unscheduled = unscheduledTasks($filteredTasks);
	let railCollapsed = false;
	let showUnscheduled = false;
	// Auto-collapse the side panel when it has nothing to offer; reopen when the
	// first unscheduled task (re)appears. Manual toggling wins in between.
	let hadUnscheduled = false;
	$: if (!unscheduled.length) {
		railCollapsed = true;
		hadUnscheduled = false;
	} else if (!hadUnscheduled) {
		railCollapsed = false;
		hadUnscheduled = true;
	}

	// Hand-cursor panning: drag empty canvas to scroll both axes (mouse only —
	// touch uses native scrolling, and interactive elements keep their own drags).
	let panning = false;
	let px0 = 0, py0 = 0, psl = 0, pst = 0;
	function panDown(e: PointerEvent) {
		if ($mobile || e.pointerType !== 'mouse' || e.button !== 0 || !scroller) return;
		if ((e.target as HTMLElement).closest('button, [role="button"], input, [draggable="true"]')) return;
		panning = true;
		px0 = e.clientX; py0 = e.clientY;
		psl = scroller.scrollLeft; pst = scroller.scrollTop;
		scroller.setPointerCapture(e.pointerId);
	}
	function panMove(e: PointerEvent) {
		if (!panning || !scroller) return;
		scroller.scrollLeft = psl - (e.clientX - px0);
		scroller.scrollTop = pst - (e.clientY - py0);
	}
	function panUp() {
		panning = false;
	}

	// HTML5 drop target state: the hovered chart day while a rail card is dragged.
	let rowsEl: HTMLElement | null = null;
	let hoverDay: number | null = null;
	function laneDay(e: DragEvent): number | null {
		if (!rowsEl || !scroller) return null;
		if (e.clientX - scroller.getBoundingClientRect().left < railW) return null;
		const x = e.clientX - rowsEl.getBoundingClientRect().left - railW;
		return x < 0 ? null : xToDay(x, win, dayWidth);
	}
	function dragOver(e: DragEvent) {
		if (!e.dataTransfer?.types.includes('text/workos-task')) return;
		const day = laneDay(e);
		hoverDay = day;
		if (day != null) e.preventDefault();
	}
	async function drop(e: DragEvent) {
		const id = e.dataTransfer?.getData('text/workos-task');
		const day = laneDay(e);
		hoverDay = null;
		if (!id || day == null) return;
		e.preventDefault();
		try {
			await editTask(id, { start_date: dayToTs(day), due_date: dayToTs(day) });
		} catch {
			toast.error('Could not schedule the task');
		}
	}

	// Per-chart quick add (bottom row).
	let addingRow = false;
	let rowTitle = '';
	async function submitRow() {
		const ws = $currentWorkstream;
		const title = rowTitle.trim();
		if (!title || !ws) return;
		rowTitle = '';
		addingRow = false;
		const ts = dayToTs(todayDay(Date.now()));
		try {
			await addTask(ws.id, { title, start_date: ts, due_date: ts });
		} catch {
			toast.error('Failed to create task');
			if (!addingRow && !rowTitle) {
				addingRow = true;
				rowTitle = title;
			}
		}
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
					class="px-3 py-1 rounded-full transition capitalize {$timelineZoom === z ? 'bg-primary text-primary-foreground shadow-sm' : 'text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200'}"
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
				aria-label="Task title"
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

	{#if $mobile && unscheduled.length}
		<div class="flex-none px-3 pt-3 bg-white dark:bg-gray-950">
			<button
				class="w-full flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-800 text-sm font-medium"
				aria-expanded={showUnscheduled}
				aria-controls="timeline-unscheduled-list"
				onclick={() => (showUnscheduled = !showUnscheduled)}
			>
				Unscheduled <span class="text-xs text-gray-400">{unscheduled.length}</span>
				<span class="flex-1"></span>
				<Icon name={showUnscheduled ? 'chevron-up' : 'chevron-down'} size={14} />
			</button>
			{#if showUnscheduled}
				<div id="timeline-unscheduled-list" class="mt-2 rounded-lg border border-gray-200 dark:border-gray-800 divide-y divide-gray-100 dark:divide-gray-900">
					{#each unscheduled as t (t.id)}
						<button class="w-full flex items-center gap-2.5 px-3 py-2.5 text-left" onclick={() => openTask(t.id)}>
							<span class="flex-none w-2 h-2 rounded-full" style="background:{STATUS_COLOR[t.status]}"></span>
							<span class="flex-1 min-w-0 text-sm truncate">{t.title}</span>
						</button>
					{/each}
				</div>
			{/if}
		</div>
	{/if}

	<div class="flex-1 flex min-h-0 bg-white dark:bg-gray-950">
		<!-- Chart: one scroller for both axes; header sticky top, rail cells sticky left.
		     Flex column so the rows canvas stretches to the full viewport height; drag
		     empty canvas (hand cursor) to pan both axes. -->
		<div
			bind:this={scroller}
			bind:clientWidth={scrollerW}
			class="flex-1 overflow-auto min-w-0 flex flex-col {panning ? 'cursor-grabbing select-none' : 'cursor-grab'}"
			onpointerdown={panDown}
			onpointermove={panMove}
			onpointerup={panUp}
			onpointercancel={panUp}
		>
			<TimelineHeader {win} {dayWidth} zoom={$timelineZoom} {today} {railW} />

			<div
				bind:this={rowsEl}
				role="list"
				class="relative grow flex flex-col"
				style="width: {railW + chartW}px;"
				ondragover={dragOver}
				ondragleave={() => (hoverDay = null)}
				ondragend={() => (hoverDay = null)}
				ondrop={drop}
			>
				<!-- Background layer: weekends, gridlines, today line -->
				<div class="absolute top-0 bottom-0 pointer-events-none" style="left: {railW}px; width: {chartW}px;">
					{#if $timelineZoom !== 'month'}
						{#each weekendDays as d (d)}
							<div class="absolute top-0 bottom-0 bg-gray-50 dark:bg-gray-900/40" style="left: {dayToX(d, win, dayWidth)}px; width: {dayWidth}px; background-image: repeating-linear-gradient(-45deg, rgb(107 114 128 / 0.08), rgb(107 114 128 / 0.08) 4px, transparent 4px, transparent 8px);"></div>
						{/each}
						<div class="absolute inset-0" style="background: repeating-linear-gradient(to right, transparent, transparent {gridPeriod - 1}px, rgb(107 114 128 / 0.12) {gridPeriod - 1}px, rgb(107 114 128 / 0.12) {gridPeriod}px); background-position: {gridOffset}px 0;"></div>
					{:else}
						{#each monthStarts as d (d)}
							<div class="absolute top-0 bottom-0 w-px bg-gray-200 dark:bg-gray-800" style="left: {dayToX(d, win, dayWidth)}px;"></div>
						{/each}
					{/if}
					<div class="absolute top-0 bottom-0 w-0.5 bg-primary z-10" style="left: {tlx}px;">
						<span class="absolute top-0 left-1/2 -translate-x-1/2 whitespace-nowrap px-1 py-px rounded bg-primary text-primary-foreground text-[8px] font-bold tracking-wide">TODAY</span>
					</div>
				</div>

				{#if hoverDay != null}
					<div class="absolute top-0 bottom-0 z-30 border-l-2 border-dashed border-primary pointer-events-none" style="left: {railW + dayToX(hoverDay, win, dayWidth)}px;">
						<span class="absolute top-1 left-1 px-1.5 py-0.5 rounded bg-primary text-primary-foreground text-[9px] font-bold whitespace-nowrap">Schedule here</span>
					</div>
				{/if}

				<!-- Rows -->
				{#if items.length}
					{#each items as item (item.task.id)}
						<div role="listitem" class="flex-none flex border-b border-gray-100 dark:border-gray-900 hover:bg-gray-50/60 dark:hover:bg-gray-900/30" style="height: {rowH}px;">
							<div class="sticky left-0 z-20 flex-none bg-white dark:bg-gray-950 border-r border-gray-100 dark:border-gray-900" style="width: {railW}px;">
								<TimelineRail {item} compact={$mobile} />
							</div>
							<div class="relative flex-none" style="width: {chartW}px;">
								<TimelineBar {item} {win} {dayWidth} {today} {scroller} disabled={$mobile} />
							</div>
						</div>
					{/each}
				{:else}
					<!-- Empty state: centered in the visible viewport (sticky), above the grid -->
					<div class="flex-1 sticky left-0 z-10 flex items-center justify-center py-16" style="width: {scrollerW || 600}px;">
						<div class="flex flex-col items-center gap-2.5 text-center px-6">
							<span class="w-12 h-12 rounded-2xl bg-gray-100 dark:bg-gray-900 text-gray-400 dark:text-gray-500 flex items-center justify-center">
								<Icon name="chart-gantt" size={24} />
							</span>
							{#if unscheduled.length}
								<span class="text-sm text-gray-500 dark:text-gray-400">Nothing scheduled yet</span>
								<span class="text-xs text-gray-400 dark:text-gray-500">Drag a task in from the Unscheduled panel, or give a task dates.</span>
							{:else}
								<span class="text-sm text-gray-500 dark:text-gray-400">No tasks on the timeline</span>
								<span class="text-xs text-gray-400 dark:text-gray-500">Plan your work by creating a task — it lands on today.</span>
								<button class="mt-1 inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-lg bg-primary hover:bg-primary/90 text-primary-foreground text-sm font-medium" onclick={() => { addingRow = true; rowTitle = ''; }}>
									<Icon name="plus" size={15} /> Add task
								</button>
							{/if}
						</div>
					</div>
				{/if}

				<!-- Add-task row -->
				<div class="flex-none flex" style="height: {rowH}px;">
					<div class="sticky left-0 z-20 flex-none bg-white dark:bg-gray-950 flex items-center px-3" style="width: {railW}px;">
						{#if addingRow}
							<!-- svelte-ignore a11y_autofocus -->
							<input
								class="text-sm px-2 py-1 rounded-lg border border-gray-300 dark:border-gray-700 bg-transparent w-full"
								placeholder="Task title…"
								bind:value={rowTitle}
								onkeydown={(e) => { if (e.key === 'Enter') submitRow(); if (e.key === 'Escape') { addingRow = false; rowTitle = ''; } }}
								autofocus
							/>
						{:else}
							<button class="inline-flex items-center gap-1.5 text-sm text-primary font-medium hover:opacity-80" onclick={() => { addingRow = true; rowTitle = ''; }}>
								<Icon name="plus" size={15} /> Add task
							</button>
						{/if}
					</div>
				</div>

				{#if items.length}
					<!-- Rail filler: the title column runs to the bottom of the canvas -->
					<div class="flex-1 flex min-h-0">
						<div class="sticky left-0 z-20 flex-none bg-white dark:bg-gray-950 border-r border-gray-100 dark:border-gray-900" style="width: {railW}px;"></div>
					</div>
				{/if}
			</div>
		</div>

		{#if !$mobile}
			<UnscheduledPanel tasks={unscheduled} bind:collapsed={railCollapsed} />
		{/if}
	</div>
</div>
