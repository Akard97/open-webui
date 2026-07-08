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
 * by start, then end, then title. */
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
		(a, b) =>
			a.startDay - b.startDay || a.endDay - b.endDay || a.task.title.localeCompare(b.task.title)
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
