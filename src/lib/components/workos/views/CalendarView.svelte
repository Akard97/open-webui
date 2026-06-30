<script lang="ts">
	import Icon from '../ui/Icon.svelte';
	import FilterBar from '../chrome/FilterBar.svelte';
	import DayCell from './calendar/DayCell.svelte';
	import UnscheduledRail from './calendar/UnscheduledRail.svelte';
	import { monthGrid, weekDays, isToday, dayKey } from '../lib/calendar';
	import { boardFilter, filteredTasks, editTask, tasks as tasksStore } from '../lib/store';
	import type { Task } from '../lib/types';
	import Sortable from 'sortablejs';
	import { onDestroy, tick } from 'svelte';
	import { get } from 'svelte/store';

	const WEEKDAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

	let mode: 'month' | 'week' = 'month';
	// Anchor date for the visible period; ephemeral (resets on remount).
	let cursor = new Date();

	$: days = mode === 'month' ? monthGrid(cursor) : weekDays(cursor);
	$: cursorMonth = cursor.getMonth();
	$: scheduled = $filteredTasks.filter((t) => t.due_date != null);
	$: unscheduled = $filteredTasks.filter((t) => t.due_date == null);
	$: byDay = scheduled.reduce<Map<number, Task[]>>((m, t) => {
		const k = dayKey(t.due_date as number);
		(m.get(k) ?? m.set(k, []).get(k)!).push(t);
		return m;
	}, new Map());
	$: cap = mode === 'month' ? 3 : Infinity;
	// In week mode `days` is already weekDays(cursor); derive the label from it
	// rather than recomputing the week array.
	$: label =
		mode === 'month'
			? cursor.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
			: rangeLabel(days);

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

	let gridEl: HTMLElement;
	// Bumped after each drop to re-key the grid + rail, discarding SortableJS's
	// DOM mutation and rebuilding every cell from the store (the source of truth).
	let epoch = 0;
	let sortables: Sortable[] = [];

	function destroySortables() {
		sortables.forEach((s) => s.destroy());
		sortables = [];
	}

	// Live drop-target highlight while dragging (SortableJS onMove → the hovered list).
	function highlightDrop(to: HTMLElement | null) {
		if (!gridEl) return;
		gridEl.querySelectorAll('.cal-drop-active').forEach((n) => n.classList.remove('cal-drop-active'));
		to?.classList.add('cal-drop-active');
	}
	function clearDrop() {
		gridEl?.querySelectorAll('.cal-drop-active').forEach((n) => n.classList.remove('cal-drop-active'));
	}

	async function initSortables() {
		destroySortables();
		await tick();
		if (!gridEl) return;
		const lists = gridEl.querySelectorAll<HTMLElement>('[data-cal-list], [data-cal-rail]');
		lists.forEach((el) =>
			sortables.push(
				new Sortable(el, {
					group: 'workos-calendar',
					animation: 150,
					ghostClass: 'opacity-40',
					draggable: '[data-task-id]',
					onMove: (e: Sortable.MoveEvent) => { highlightDrop(e.to); return true; },
					onEnd: handleEnd
				})
			)
		);
	}

	async function handleEnd(evt: Sortable.SortableEvent) {
		clearDrop();
		const taskId = evt.item.getAttribute('data-task-id');
		const to = evt.to as HTMLElement;
		if (!taskId) return;
		const isRail = to.hasAttribute('data-cal-rail');
		const nextDue = isRail ? null : Number(to.getAttribute('data-day'));

		// Drop SortableJS's moved node; the store-driven rebuild below recreates it.
		evt.item.remove();

		const current = get(tasksStore).find((t) => t.id === taskId);
		const curKey = current?.due_date == null ? null : dayKey(current.due_date);
		const nextKey = nextDue == null ? null : dayKey(nextDue);
		// editTask writes optimistically (synchronously) before its network await,
		// so rebuild from that synchronous state and re-init BEFORE awaiting the
		// network — otherwise the chip flickers out for the whole round-trip.
		// (Mirrors BoardView's epoch-before-await ordering.)
		const saved = curKey !== nextKey ? editTask(taskId, { due_date: nextDue }) : null;
		epoch += 1; // rebuild grid + rail from the (already-updated) store
		await initSortables();
		if (saved) await saved;
	}

	// Re-init whenever the rendered cell set changes (period, mode, filtered
	// tasks, or a post-drop rebuild). Guarded by tick() inside initSortables.
	$: void [days, mode, $filteredTasks, epoch], queueInit();
	let queued = false;
	function queueInit() {
		if (queued) return;
		queued = true;
		tick().then(() => { queued = false; initSortables(); });
	}

	onDestroy(destroySortables);
</script>

<div class="h-full flex flex-col min-h-0">
	<FilterBar filter={boardFilter} />

	<!-- Toolbar -->
	<div class="flex-none flex items-center gap-3 px-4 py-2.5 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-950">
		<div class="flex items-center gap-1">
			<button type="button" class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-900 transition" title="Previous" aria-label="Previous period" onclick={() => step(-1)}><Icon name="chevron-left" size={16} /></button>
			<button type="button" class="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-900 transition" title="Next" aria-label="Next period" onclick={() => step(1)}><Icon name="chevron-right" size={16} /></button>
		</div>
		<div class="text-base font-semibold tracking-tight">{label}</div>
		<button type="button" class="text-sm px-3 py-1.5 rounded-lg border border-gray-200 dark:border-gray-800 hover:bg-gray-100 dark:hover:bg-gray-900 transition" onclick={today}>Today</button>
		<div class="flex-1"></div>
		<div class="inline-flex items-center gap-0.5 rounded-full bg-gray-100 dark:bg-gray-900 p-0.5 text-sm">
			<button type="button" aria-pressed={mode === 'month'} class="px-3.5 py-1 rounded-full transition {mode === 'month' ? 'bg-primary text-primary-foreground shadow-sm' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}" onclick={() => (mode = 'month')}>Month</button>
			<button type="button" aria-pressed={mode === 'week'} class="px-3.5 py-1 rounded-full transition {mode === 'week' ? 'bg-primary text-primary-foreground shadow-sm' : 'text-gray-500 hover:text-gray-800 dark:hover:text-gray-200'}" onclick={() => (mode = 'week')}>Week</button>
		</div>
	</div>

	<!-- Grid -->
	<div class="flex-1 overflow-auto p-4 bg-white dark:bg-gray-900 flex gap-4 items-start" bind:this={gridEl}>
		{#key epoch}
			<div class="flex-1 min-w-0 rounded-xl border border-gray-200 dark:border-gray-800 overflow-hidden">
				<div class="grid grid-cols-7 bg-gray-50 dark:bg-gray-950">
					{#each WEEKDAYS as w (w)}
						<div class="px-2.5 py-2 text-[11px] font-medium uppercase tracking-wider text-gray-400 dark:text-gray-400 border-b border-gray-100 dark:border-gray-900">{w}</div>
					{/each}
				</div>
				<div class="grid grid-cols-7">
					{#each days as d (d.getTime())}
						<DayCell
							date={d}
							dimmed={mode === 'month' && d.getMonth() !== cursorMonth}
							today={isToday(d.getTime(), Date.now())}
							tasks={byDay.get(dayKey(d.getTime())) ?? []}
							{cap}
						/>
					{/each}
				</div>
			</div>
			<UnscheduledRail tasks={unscheduled} />
		{/key}
	</div>
</div>

<style>
	/* Drop-target highlight toggled by SortableJS onMove while dragging a chip. */
	:global([data-cal-list].cal-drop-active),
	:global([data-cal-rail].cal-drop-active) {
		box-shadow: inset 0 0 0 2px #00a5ba;
		background: rgba(0, 165, 186, 0.07);
		border-radius: 6px;
	}
	:global(.dark [data-cal-list].cal-drop-active),
	:global(.dark [data-cal-rail].cal-drop-active) {
		background: rgba(0, 165, 186, 0.16);
	}
</style>
