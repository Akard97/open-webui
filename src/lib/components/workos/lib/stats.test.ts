import { describe, it, expect } from 'vitest';
import { computeStats, needsAttention } from './stats';
import type { Task, TaskStatus } from './types';

const DAY = 86_400_000;
const NOW = new Date(2024, 2, 6, 12, 0, 0).getTime(); // 2024-03-06 12:00 local

const mk = (
	id: string,
	o: Partial<Task> = {}
): Task => ({
	id, workstream_id: 'w1', team_id: 'tm', number: 1, key: `OSL-${id}`, title: id,
	status: (o.status ?? 'todo') as TaskStatus, priority: o.priority ?? null,
	assignee_ids: o.assignee_ids ?? [], progress: 0, labels: [], sort_key: 1,
	created_by_id: 'u1', due_date: o.due_date ?? null, completed_at: o.completed_at ?? null,
	created_at: 0, updated_at: 0
});

describe('computeStats', () => {
	it('counts buckets, statuses, priorities, and completion', () => {
		const tasks = [
			mk('a', { status: 'in_progress', priority: 'urgent', due_date: NOW - DAY }), // overdue
			mk('b', { status: 'todo', priority: 'high', due_date: NOW + 3600_000 }),      // today
			mk('c', { status: 'done', priority: 'medium', completed_at: NOW - 2 * DAY }), // done this week
			mk('d', { status: 'done', priority: 'low', completed_at: NOW - 10 * DAY }),   // done, old
			mk('e', { status: 'canceled' }),
			mk('f', { status: 'backlog' })
		];
		const s = computeStats(tasks, NOW);
		expect(s.overdue).toBe(1);
		expect(s.dueToday).toBe(1);
		expect(s.inProgress).toBe(1);
		expect(s.doneThisWeek).toBe(1);
		expect(s.byStatus.done).toBe(2);
		expect(s.byStatus.canceled).toBe(1);
		expect(s.byPriority.urgent).toBe(1);
		expect(s.byPriority.none).toBe(2); // e (canceled) + f (backlog) have null priority
		// total excludes canceled: a,b,c,d,f = 5; done = 2 → 2/5 = 0.4
		expect(s.total).toBe(5);
		expect(s.completionRate).toBeCloseTo(0.4, 5);
	});

	it('doneThisWeek includes the exact 7-day boundary and excludes earlier', () => {
		const tasks = [
			mk('edge', { status: 'done', completed_at: NOW - 7 * DAY }),
			mk('past', { status: 'done', completed_at: NOW - 7 * DAY - 1 })
		];
		const s = computeStats(tasks, NOW);
		expect(s.doneThisWeek).toBe(1);
	});

	it('completionRate is 0 when there are no non-canceled tasks', () => {
		expect(computeStats([], NOW).completionRate).toBe(0);
		expect(computeStats([mk('x', { status: 'canceled' })], NOW).completionRate).toBe(0);
	});
});

describe('needsAttention', () => {
	it('unions overdue, due-today, and urgent/high open tasks, de-duplicated', () => {
		const tasks = [
			mk('overdueUrgent', { status: 'in_progress', priority: 'urgent', due_date: NOW - DAY }),
			mk('today', { due_date: NOW + 3600_000 }),
			mk('highLater', { priority: 'high', due_date: NOW + 30 * DAY }),
			mk('doneHigh', { status: 'done', priority: 'high' }), // excluded: resolved
			mk('lowLater', { priority: 'low', due_date: NOW + 30 * DAY }) // excluded: not urgent/high, not due soon
		];
		const ids = needsAttention(tasks, NOW).map((t) => t.id);
		expect(ids).toEqual(['overdueUrgent', 'today', 'highLater']);
	});
});
