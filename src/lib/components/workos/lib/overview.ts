// Overview page metrics — every number on the Overview derives from a pure
// function here so it can be unit-tested. Spec: docs/superpowers/specs/
// 2026-07-02-workos-overview-design.md §2–§3 (canonical definitions).
import type { Task, TaskPriority, TaskStatus } from './types';
import { dueDayStartLocal, dueDayEndLocal, taskHealth, plannedProgress, actualProgress } from './progress';
import { PRIORITY_ORDER, STATUS_ORDER } from './types';

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

export function localWeekStart(now: number): number {
	const d = new Date(now);
	const dow = (d.getDay() + 6) % 7; // Monday = 0
	return new Date(d.getFullYear(), d.getMonth(), d.getDate() - dow).getTime();
}

export interface WeekBin {
	start: number; end: number; label: string;
	created: number; completed: number; current: boolean;
}

export function weeklyMomentum(all: Task[], now: number, weeks: number): WeekBin[] {
	const w = all.filter(notCanceled);
	const thisWeek = localWeekStart(now);
	const bins: WeekBin[] = [];
	for (let i = weeks - 1; i >= 0; i--) {
		const start = addLocalDays(thisWeek, -7 * i);
		const end = addLocalDays(start, 7);
		bins.push({
			start, end,
			label: new Date(start).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
			created: w.filter((t) => t.created_at >= start && t.created_at < end).length,
			completed: w.filter(
				(t) => t.status === 'done' && t.completed_at != null && t.completed_at >= start && t.completed_at < end
			).length,
			current: i === 0
		});
	}
	return bins;
}

export interface CompletionTime { avgDays: number | null; prevAvgDays: number | null }

// Average created→completed lead time over the chart's calendar window
// (labelled "avg completion time" in the UI — we do not measure in_progress→done).
export function completionTime(all: Task[], now: number, weeks: number): CompletionTime {
	const w = all.filter(notCanceled);
	const start = addLocalDays(localWeekStart(now), -7 * (weeks - 1));
	const prevStart = addLocalDays(start, -7 * weeks);
	const avg = (a: number, b: number): number | null => {
		const xs = w
			.filter((t) => t.status === 'done' && t.completed_at != null && t.completed_at >= a && t.completed_at < b)
			.map((t) => (t.completed_at as number) - t.created_at);
		if (!xs.length) return null;
		return Math.round((xs.reduce((s, x) => s + x, 0) / xs.length / DAY) * 10) / 10;
	};
	return { avgDays: avg(start, now + 1), prevAvgDays: avg(prevStart, start) };
}

export interface PriorityPair { key: TaskPriority | 'none'; label: string; n: number }

export function priorityPairs(all: Task[]): PriorityPair[] {
	const open = all.filter(isOpen);
	const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
	const pairs: PriorityPair[] = PRIORITY_ORDER.map((p) => ({
		key: p, label: cap(p), n: open.filter((t) => t.priority === p).length
	}));
	const none = open.filter((t) => !t.priority).length;
	if (none > 0) pairs.push({ key: 'none', label: 'None', n: none });
	return pairs;
}

export interface StatusSlice { status: TaskStatus; n: number; pct: number }

export function statusMix(all: Task[]): { total: number; slices: StatusSlice[] } {
	const w = all.filter(notCanceled);
	const slices = STATUS_ORDER.map((s) => {
		const n = w.filter((t) => t.status === s).length;
		return { status: s, n, pct: w.length ? (n / w.length) * 100 : 0 };
	});
	return { total: w.length, slices };
}

export type MemberHealth = 'needs_support' | 'watch' | 'on_track';
export interface TeamRow {
	userId: string | null; open: number; inProgress: number; inReview: number;
	overdue: number; load: number; health: MemberHealth | null;
}

// Multi-assignee rule (spec §3.4): a task counts fully for EACH assignee, so
// columns may sum past the global totals. Load is relative to the busiest member.
export function teamRows(all: Task[], now: number, nameOf: (id: string) => string): TeamRow[] {
	const open = all.filter(isOpen);
	const byUser = new Map<string, Task[]>();
	const unassigned: Task[] = [];
	for (const t of open) {
		const ids = t.assignee_ids ?? [];
		if (!ids.length) { unassigned.push(t); continue; }
		for (const id of ids) byUser.set(id, [...(byUser.get(id) ?? []), t]);
	}
	const rows: TeamRow[] = [...byUser.entries()].map(([userId, ts]) => {
		const overdueN = ts.filter((t) => isOverdue(t, now)).length;
		const behind = ts.filter((t) => taskHealth(t, now) === 'behind').length;
		const atRisk = ts.filter((t) => taskHealth(t, now) === 'at_risk').length;
		const riskHigh = overdueN + behind;
		const health: MemberHealth =
			riskHigh >= 2 ? 'needs_support' : riskHigh === 1 || atRisk >= 2 ? 'watch' : 'on_track';
		return {
			userId,
			open: ts.length,
			inProgress: ts.filter((t) => t.status === 'in_progress').length,
			inReview: ts.filter((t) => t.status === 'in_review').length,
			overdue: overdueN, load: 0, health
		};
	});
	rows.sort((a, b) => b.open - a.open || nameOf(a.userId as string).localeCompare(nameOf(b.userId as string)));
	const maxOpen = Math.max(1, ...rows.map((r) => r.open));
	for (const r of rows) r.load = r.open / maxOpen;
	if (unassigned.length) {
		rows.push({
			userId: null, open: unassigned.length, inProgress: 0, inReview: 0,
			overdue: 0, load: Math.min(1, unassigned.length / maxOpen), health: null
		});
	}
	return rows;
}

export type AttentionClass = 'overdue' | 'behind' | 'at_risk' | 'due_soon';
export interface AttentionItem {
	task: Task; cls: AttentionClass;
	daysLate: number | null; gap: number | null; dueLabel: 'today' | 'tomorrow' | null;
}

const CLS_RANK: Record<AttentionClass, number> = { overdue: 0, behind: 1, at_risk: 2, due_soon: 3 };

export function attentionList(all: Task[], now: number): AttentionItem[] {
	const open = all.filter(isOpen);
	const startToday = startOfLocalDay(now);
	const startTomorrow = addLocalDays(startToday, 1);
	const startAfter = addLocalDays(startToday, 2);
	const items: AttentionItem[] = [];
	for (const t of open) {
		if (isOverdue(t, now)) {
			items.push({ task: t, cls: 'overdue', daysLate: daysLate(t.due_date as number, now), gap: null, dueLabel: null });
			continue;
		}
		const h = taskHealth(t, now);
		if (h === 'behind' || h === 'at_risk') {
			const gap = (plannedProgress(t.start_date, t.due_date, now) ?? 0) - actualProgress(t);
			items.push({ task: t, cls: h, daysLate: null, gap, dueLabel: null });
			continue;
		}
		if (t.due_date != null) {
			const day = dueDayStartLocal(t.due_date);
			if (day >= startToday && day < startAfter) {
				items.push({
					task: t, cls: 'due_soon', daysLate: null, gap: null,
					dueLabel: day < startTomorrow ? 'today' : 'tomorrow'
				});
			}
		}
	}
	return items.sort((a, b) => {
		if (CLS_RANK[a.cls] !== CLS_RANK[b.cls]) return CLS_RANK[a.cls] - CLS_RANK[b.cls];
		if (a.cls === 'overdue' || a.cls === 'due_soon') return (a.task.due_date ?? 0) - (b.task.due_date ?? 0);
		return (b.gap ?? 0) - (a.gap ?? 0);
	});
}
