import type { TaskStatus } from './types';

/** "Jun 23" at local midnight, "Jun 23 · 09:30 AM" when the timestamp carries a time. */
export function formatDueDate(ts: number): string {
	const d = new Date(ts);
	const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
	if (d.getHours() === 0 && d.getMinutes() === 0) return date;
	const time = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
	return `${date} · ${time}`;
}

/** A task is overdue when it has a past due date and is not finished. */
export function isOverdue(
	dueDate: number | null | undefined,
	status: TaskStatus,
	now: number
): boolean {
	if (dueDate == null) return false;
	if (status === 'done' || status === 'canceled') return false;
	return dueDate < now;
}

/** "5 March 2024" — long day-month-year (en-GB gives day-first ordering). */
export function formatDateLong(ts: number): string {
	return new Date(ts).toLocaleDateString('en-GB', {
		day: 'numeric',
		month: 'long',
		year: 'numeric'
	});
}
