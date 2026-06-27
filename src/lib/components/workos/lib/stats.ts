import { bucketByDueDate } from './buckets';
import type { Task, TaskStatus } from './types';

const WEEK = 7 * 86_400_000;

export type PriorityKey = 'urgent' | 'high' | 'medium' | 'low' | 'none';

export interface MyWorkStats {
	overdue: number;
	dueToday: number;
	inProgress: number;
	doneThisWeek: number;
	completionRate: number; // 0..1
	total: number;          // non-canceled count (completion denominator)
	byStatus: Record<TaskStatus, number>;
	byPriority: Record<PriorityKey, number>;
}

export function computeStats(tasks: Task[], now: number): MyWorkStats {
	const b = bucketByDueDate(tasks, now);
	const byStatus: Record<TaskStatus, number> = {
		backlog: 0, todo: 0, in_progress: 0, in_review: 0, done: 0, canceled: 0
	};
	const byPriority: Record<PriorityKey, number> = {
		urgent: 0, high: 0, medium: 0, low: 0, none: 0
	};
	const weekAgo = now - WEEK;
	let done = 0, total = 0, doneThisWeek = 0;
	for (const t of tasks) {
		byStatus[t.status]++;
		byPriority[t.priority ?? 'none']++;
		if (t.status !== 'canceled') {
			total++;
			if (t.status === 'done') done++;
		}
		if (t.status === 'done' && (t.completed_at ?? 0) >= weekAgo) doneThisWeek++;
	}
	return {
		overdue: b.overdue.length,
		dueToday: b.today.length,
		inProgress: byStatus.in_progress,
		doneThisWeek,
		completionRate: total === 0 ? 0 : done / total,
		total,
		byStatus,
		byPriority
	};
}

// overdue ∪ due-today ∪ (urgent|high priority, still open), de-duplicated, overdue first.
export function needsAttention(tasks: Task[], now: number): Task[] {
	const b = bucketByDueDate(tasks, now);
	const urgentHigh = tasks.filter(
		(t) =>
			(t.priority === 'urgent' || t.priority === 'high') &&
			t.status !== 'done' &&
			t.status !== 'canceled'
	);
	const seen = new Set<string>();
	const out: Task[] = [];
	for (const t of [...b.overdue, ...b.today, ...urgentHigh]) {
		if (seen.has(t.id)) continue;
		seen.add(t.id);
		out.push(t);
	}
	return out;
}
