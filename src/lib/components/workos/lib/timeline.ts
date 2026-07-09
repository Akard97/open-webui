import type { Task } from './types';

// ── Day encoding ────────────────────────────────────────────────────────────
// start_date/due_date are stored as UTC midnight of the picked calendar date
// (see progress.ts). A "day" here is the integer UTC day index ts / DAY_MS.
export const DAY_MS = 86_400_000;

export function tsToDay(ts: number): number {
	return Math.floor(ts / DAY_MS);
}
export function dayToTs(day: number): number {
	return day * DAY_MS;
}
/** The viewer's local calendar date, encoded as a UTC day index — the same
 * value the date picker would store for "today". */
export function todayDay(now: number): number {
	const d = new Date(now);
	return Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()) / DAY_MS;
}

// ── Classification ──────────────────────────────────────────────────────────
export type TimelineKind = 'bar' | 'milestone' | 'unscheduled';

export interface TimelineItem {
	task: Task;
	kind: 'bar' | 'milestone';
	startDay: number; // inclusive
	endDay: number; // inclusive; === startDay for milestones and 1-day bars
}

export function classifyTask(t: Task): TimelineKind {
	if (t.start_date != null) return 'bar';
	if (t.due_date != null) return 'milestone';
	return 'unscheduled';
}

/** Chart rows: scheduled, non-canceled tasks as inclusive day ranges, sorted
 * by creation date (oldest first), then title. */
export function timelineItems(tasks: Task[]): TimelineItem[] {
	const items: TimelineItem[] = [];
	for (const t of tasks) {
		if (t.status === 'canceled') continue;
		const kind = classifyTask(t);
		if (kind === 'unscheduled') continue;
		if (kind === 'milestone') {
			const d = tsToDay(t.due_date as number);
			items.push({ task: t, kind, startDay: d, endDay: d });
		} else {
			const s = tsToDay(t.start_date as number);
			const e = t.due_date != null ? Math.max(s, tsToDay(t.due_date)) : s;
			items.push({ task: t, kind: 'bar', startDay: s, endDay: e });
		}
	}
	return items.sort(
		(a, b) => a.task.created_at - b.task.created_at || a.task.title.localeCompare(b.task.title)
	);
}

export function unscheduledTasks(tasks: Task[]): Task[] {
	return tasks.filter((t) => t.status !== 'canceled' && classifyTask(t) === 'unscheduled');
}

// ── Window ──────────────────────────────────────────────────────────────────
export interface TimelineWindow {
	startDay: number;
	endDay: number;
	days: number;
}

export const MIN_WINDOW_DAYS = 42;

/** [min − 7d, max + 14d], always containing today, at least MIN_WINDOW_DAYS wide. */
export function computeWindow(items: TimelineItem[], today: number): TimelineWindow {
	let lo = today;
	let hi = today;
	for (const it of items) {
		lo = Math.min(lo, it.startDay);
		hi = Math.max(hi, it.endDay);
	}
	lo -= 7;
	hi += 14;
	if (hi - lo + 1 < MIN_WINDOW_DAYS) hi = lo + MIN_WINDOW_DAYS - 1;
	return { startDay: lo, endDay: hi, days: hi - lo + 1 };
}

// ── Zoom ────────────────────────────────────────────────────────────────────
// A preset is the COLUMN UNIT of the chart: Day = one column per day,
// Week = one column per Monday-start week, Month = one column per month.
export type ZoomKey = 'day' | 'week' | 'month';
export const ZOOM_ORDER: ZoomKey[] = ['day', 'week', 'month'];
export const ZOOM_DAY_WIDTH: Record<ZoomKey, number> = { day: 24, week: 12, month: 4 };

export function parseZoom(raw: string | null): ZoomKey {
	return raw === 'day' || raw === 'week' || raw === 'month' ? raw : 'day';
}

// ── Scale ───────────────────────────────────────────────────────────────────
export function dayToX(day: number, win: TimelineWindow, dayWidth: number): number {
	return (day - win.startDay) * dayWidth;
}
export function xToDay(x: number, win: TimelineWindow, dayWidth: number): number {
	return win.startDay + Math.floor(x / dayWidth);
}
/** The today marker sits mid-column of today's day. */
export function todayLineX(today: number, win: TimelineWindow, dayWidth: number): number {
	return dayToX(today, win, dayWidth) + dayWidth / 2;
}

// ── Geometry ────────────────────────────────────────────────────────────────
export interface BarGeom {
	left: number;
	width: number;
	/** Hatched overdue tail after the bar, 0 when not overdue. */
	slipWidth: number;
}

export function barGeometry(
	item: TimelineItem,
	win: TimelineWindow,
	dayWidth: number,
	today: number
): BarGeom {
	const left = dayToX(item.startDay, win, dayWidth);
	const width = (item.endDay - item.startDay + 1) * dayWidth;
	const open = item.task.status !== 'done' && item.task.status !== 'canceled';
	const slipWidth =
		open && item.endDay < today
			? Math.max(0, todayLineX(today, win, dayWidth) - (left + width))
			: 0;
	return { left, width, slipWidth };
}

// ── Header helpers (all UTC — matches the storage convention) ───────────────
export function utcDate(day: number): Date {
	return new Date(day * DAY_MS);
}
export function isWeekend(day: number): boolean {
	const wd = utcDate(day).getUTCDay();
	return wd === 0 || wd === 6;
}
export function isWeekStart(day: number): boolean {
	return utcDate(day).getUTCDay() === 1; // Monday
}
export function dayNumber(day: number): number {
	return utcDate(day).getUTCDate();
}
export function weekdayShort(day: number): string {
	return utcDate(day).toLocaleDateString('en-US', { weekday: 'short', timeZone: 'UTC' });
}

export interface MonthSpan {
	label: string;
	startDay: number;
	days: number;
}
export function monthSpans(win: TimelineWindow): MonthSpan[] {
	const spans: MonthSpan[] = [];
	for (let d = win.startDay; d <= win.endDay; d++) {
		const label = utcDate(d).toLocaleDateString('en-US', {
			month: 'long',
			year: 'numeric',
			timeZone: 'UTC'
		});
		const last = spans[spans.length - 1];
		if (last && last.label === label) last.days += 1;
		else spans.push({ label, startDay: d, days: 1 });
	}
	return spans;
}

export interface WeekSpan {
	label: string;
	startDay: number;
	days: number;
}
/** Monday-start week chunks covering the window (edges may be partial weeks).
 * Labels: "Jul 6 – 12", or "Jun 29 – Jul 5" when the week crosses a month. */
export function weekSpans(win: TimelineWindow): WeekSpan[] {
	const spans: WeekSpan[] = [];
	for (let d = win.startDay; d <= win.endDay; d++) {
		const last = spans[spans.length - 1];
		if (!last || isWeekStart(d)) spans.push({ label: '', startDay: d, days: 1 });
		else last.days += 1;
	}
	for (const s of spans) {
		const end = s.startDay + s.days - 1;
		const mon = (day: number) =>
			utcDate(day).toLocaleDateString('en-US', { month: 'short', timeZone: 'UTC' });
		s.label =
			mon(s.startDay) === mon(end)
				? `${mon(s.startDay)} ${dayNumber(s.startDay)} – ${dayNumber(end)}`
				: `${mon(s.startDay)} ${dayNumber(s.startDay)} – ${mon(end)} ${dayNumber(end)}`;
	}
	return spans;
}

// ── Drag edits ──────────────────────────────────────────────────────────────
export interface DatePatch {
	start_date?: number | null;
	due_date?: number | null;
}

/** Shift the whole item by dayDelta. Only fields the task actually has are
 * returned, so a start-only bar never gains a due date from a move. */
export function applyMove(item: TimelineItem, dayDelta: number): DatePatch {
	const p: DatePatch = {};
	if (item.task.start_date != null) p.start_date = dayToTs(tsToDay(item.task.start_date) + dayDelta);
	if (item.task.due_date != null) p.due_date = dayToTs(tsToDay(item.task.due_date) + dayDelta);
	return p;
}

/** Move one edge by dayDelta, clamped so the item never inverts (1-day min).
 * Creates the missing date when resizing the open side of a one-sided item. */
export function applyResize(item: TimelineItem, edge: 'start' | 'end', dayDelta: number): DatePatch {
	if (edge === 'start') {
		return { start_date: dayToTs(Math.min(item.startDay + dayDelta, item.endDay)) };
	}
	return { due_date: dayToTs(Math.max(item.endDay + dayDelta, item.startDay)) };
}
