// Overview page metrics — every number on the Overview derives from a pure
// function here so it can be unit-tested. Spec: docs/superpowers/specs/
// 2026-07-02-workos-overview-design.md §2–§3 (canonical definitions).
import type { Task } from './types';
import { dueDayStartLocal, dueDayEndLocal } from './progress';

const DAY = 86_400_000;

export const notCanceled = (t: Task): boolean => t.status !== 'canceled';
export const isOpen = (t: Task): boolean => t.status !== 'done' && t.status !== 'canceled';

export function startOfLocalDay(now: number): number {
	const d = new Date(now);
	return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

// DST-safe day stepping: goes through Date parts, not ms arithmetic.
export function addLocalDays(dayStart: number, n: number): number {
	const d = new Date(dayStart);
	return new Date(d.getFullYear(), d.getMonth(), d.getDate() + n).getTime();
}

export function isOverdue(t: Pick<Task, 'status' | 'due_date'>, now: number): boolean {
	if (t.status === 'done' || t.status === 'canceled' || t.due_date == null) return false;
	return now > dueDayEndLocal(t.due_date);
}

export function daysLate(due: number, now: number): number {
	return Math.max(1, Math.ceil((now - dueDayEndLocal(due)) / DAY));
}

export function agoLabel(ts: number, now: number): string {
	const s = Math.max(0, Math.floor((now - ts) / 1000));
	if (s < 60) return `${s}s`;
	const m = Math.floor(s / 60);
	if (m < 60) return `${m}m`;
	const h = Math.floor(m / 60);
	if (h < 24) return `${h}h`;
	return `${Math.floor(h / 24)}d`;
}

export interface OverviewKpis {
	open: number; inProgress: number; inReview: number;
	dueThisWeek: number; dueTomorrow: number;
	overdue: number; oldestOverdueDays: number | null;
	completed7d: number; completedPrev7d: number;
	new7d: number;
}

export function computeKpis(all: Task[], now: number): OverviewKpis {
	const w = all.filter(notCanceled);
	const open = w.filter(isOpen);
	const startToday = startOfLocalDay(now);
	const endWindow = addLocalDays(startToday, 7); // exclusive → today + next 6 days
	const startTomorrow = addLocalDays(startToday, 1);
	const startAfterTomorrow = addLocalDays(startToday, 2);

	let dueThisWeek = 0, dueTomorrow = 0, overdue = 0;
	let oldest: number | null = null;
	for (const t of open) {
		if (t.due_date == null) continue;
		if (isOverdue(t, now)) {
			overdue += 1;
			const late = daysLate(t.due_date, now);
			oldest = oldest == null ? late : Math.max(oldest, late);
			continue;
		}
		const day = dueDayStartLocal(t.due_date);
		if (day >= startToday && day < endWindow) dueThisWeek += 1;
		if (day >= startTomorrow && day < startAfterTomorrow) dueTomorrow += 1;
	}

	const doneIn = (a: number, b: number): number =>
		w.filter((t) => t.status === 'done' && t.completed_at != null && t.completed_at > a && t.completed_at <= b).length;

	return {
		open: open.length,
		inProgress: open.filter((t) => t.status === 'in_progress').length,
		inReview: open.filter((t) => t.status === 'in_review').length,
		dueThisWeek, dueTomorrow, overdue, oldestOverdueDays: oldest,
		completed7d: doneIn(now - 7 * DAY, now),
		completedPrev7d: doneIn(now - 14 * DAY, now - 7 * DAY),
		new7d: w.filter((t) => t.created_at > now - 7 * DAY && t.created_at <= now).length
	};
}
