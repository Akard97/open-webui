import type { Task } from './types';

// Local start-of-day epoch (ms). The calendar groups and compares tasks by
// local calendar day, ignoring the time component of a due date.
export function dayKey(ms: number): number {
	const d = new Date(ms);
	return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

export function sameDay(a: number, b: number): boolean {
	return dayKey(a) === dayKey(b);
}

export function isToday(ms: number, now: number): boolean {
	return dayKey(ms) === dayKey(now);
}

// Whole-week, Sunday-first grid covering the cursor's month: leading days from
// the prior month back to the Sunday on/before the 1st, the full month, and
// trailing days forward to the Saturday on/after the last. 35 or 42 days.
export function monthGrid(cursor: Date): Date[] {
	const first = new Date(cursor.getFullYear(), cursor.getMonth(), 1);
	const start = new Date(first);
	start.setDate(1 - first.getDay());
	const last = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 0);
	const end = new Date(last);
	end.setDate(last.getDate() + (6 - last.getDay()));
	const days: Date[] = [];
	for (const d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) days.push(new Date(d));
	return days;
}

// The 7 days (Sun..Sat) of the week containing the cursor.
export function weekDays(cursor: Date): Date[] {
	const start = new Date(cursor.getFullYear(), cursor.getMonth(), cursor.getDate() - cursor.getDay());
	return Array.from({ length: 7 }, (_, i) => {
		const d = new Date(start);
		d.setDate(start.getDate() + i);
		return d;
	});
}

export function isOverdue(task: Task, now: number): boolean {
	if (task.due_date == null) return false;
	if (task.status === 'done' || task.status === 'canceled') return false;
	return dayKey(task.due_date) < dayKey(now);
}
