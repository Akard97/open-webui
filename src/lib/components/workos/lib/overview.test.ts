import { describe, it, expect } from 'vitest';
import type { Task } from './types';
import { computeKpis, isOverdue, daysLate, startOfLocalDay, addLocalDays, agoLabel, localWeekStart, weeklyMomentum, completionTime } from './overview';

// now = local 2026-06-17 (Wednesday) 12:00
const NOW = new Date(2026, 5, 17, 12, 0).getTime();
const dueUtc = (y: number, m: number, d: number) => Date.UTC(y, m, d);

let seq = 0;
function task(over: Partial<Task>): Task {
	seq += 1;
	return {
		id: `t${seq}`, workstream_id: 'ws', team_id: 'tm', number: seq, key: `K-${seq}`,
		title: `Task ${seq}`, status: 'todo', priority: null, assignee_ids: [],
		start_date: null, due_date: null, progress: 0, labels: [], sort_key: seq,
		created_by_id: 'u1', completed_at: null,
		created_at: NOW - 30 * 86_400_000, updated_at: NOW,
		...over
	} as Task;
}

describe('isOverdue / daysLate', () => {
	it('not overdue during the due day, overdue after it ends', () => {
		const dueToday = dueUtc(2026, 5, 17);
		expect(isOverdue(task({ due_date: dueToday }), NOW)).toBe(false);
		const dueYesterday = dueUtc(2026, 5, 16);
		expect(isOverdue(task({ due_date: dueYesterday }), NOW)).toBe(true);
		expect(daysLate(dueYesterday, NOW)).toBe(1);
	});
	it('done/canceled tasks are never overdue', () => {
		const past = dueUtc(2026, 5, 1);
		expect(isOverdue(task({ due_date: past, status: 'done' }), NOW)).toBe(false);
		expect(isOverdue(task({ due_date: past, status: 'canceled' }), NOW)).toBe(false);
	});
});

describe('computeKpis', () => {
	it('counts open/in_progress/in_review and excludes canceled everywhere', () => {
		const k = computeKpis([
			task({ status: 'in_progress' }), task({ status: 'in_review' }),
			task({ status: 'todo' }), task({ status: 'done', completed_at: NOW - 1000 }),
			task({ status: 'canceled' })
		], NOW);
		expect(k.open).toBe(3);
		expect(k.inProgress).toBe(1);
		expect(k.inReview).toBe(1);
	});

	it('dueThisWeek spans today..today+6 local days; dueTomorrow only tomorrow', () => {
		const k = computeKpis([
			task({ due_date: dueUtc(2026, 5, 17) }), // today → in week
			task({ due_date: dueUtc(2026, 5, 18) }), // tomorrow → in week + tomorrow
			task({ due_date: dueUtc(2026, 5, 23) }), // today+6 → in week
			task({ due_date: dueUtc(2026, 5, 24) }), // today+7 → NOT in week
			task({ due_date: dueUtc(2026, 5, 16) })  // yesterday → overdue, not in week
		], NOW);
		expect(k.dueThisWeek).toBe(3);
		expect(k.dueTomorrow).toBe(1);
		expect(k.overdue).toBe(1);
		expect(k.oldestOverdueDays).toBe(1);
	});

	it('completed7d/prev7d use rolling windows over status done + completed_at', () => {
		const k = computeKpis([
			task({ status: 'done', completed_at: NOW - 2 * 86_400_000 }),
			task({ status: 'done', completed_at: NOW - 9 * 86_400_000 }),
			task({ status: 'done', completed_at: NOW - 20 * 86_400_000 }),
			task({ status: 'todo', completed_at: NOW - 1000 }) // not done → never counted
		], NOW);
		expect(k.completed7d).toBe(1);
		expect(k.completedPrev7d).toBe(1);
	});

	it('new7d counts by created_at regardless of status', () => {
		const k = computeKpis([
			task({ created_at: NOW - 3 * 86_400_000, status: 'done', completed_at: NOW - 1000 }),
			task({ created_at: NOW - 8 * 86_400_000 })
		], NOW);
		expect(k.new7d).toBe(1);
	});
});

describe('agoLabel', () => {
	it('formats seconds/minutes/hours/days', () => {
		expect(agoLabel(NOW - 42_000, NOW)).toBe('42s');
		expect(agoLabel(NOW - 5 * 60_000, NOW)).toBe('5m');
		expect(agoLabel(NOW - 3 * 3_600_000, NOW)).toBe('3h');
		expect(agoLabel(NOW - 2 * 86_400_000, NOW)).toBe('2d');
	});
});

describe('weeklyMomentum', () => {
	// NOW is Wednesday 2026-06-17; its Monday is 2026-06-15 local.
	it('localWeekStart returns the local Monday', () => {
		expect(localWeekStart(NOW)).toBe(new Date(2026, 5, 15).getTime());
		// Sunday belongs to the week started the previous Monday
		expect(localWeekStart(new Date(2026, 5, 21, 10, 0).getTime())).toBe(new Date(2026, 5, 15).getTime());
	});

	it('bins created and completed into local Monday-start weeks, oldest first', () => {
		const mon = new Date(2026, 5, 15).getTime();
		const prevMon = new Date(2026, 5, 8).getTime();
		const bins = weeklyMomentum([
			task({ created_at: mon + 3_600_000 }),                                        // this week: created
			task({ created_at: prevMon + 3_600_000 }),                                    // last week: created
			task({ created_at: prevMon + 1, status: 'done', completed_at: mon + 1000 }),  // created last wk, done this wk
			task({ status: 'canceled', created_at: mon + 1 })                             // excluded
		], NOW, 2);
		expect(bins).toHaveLength(2);
		expect(bins[0].start).toBe(prevMon);
		expect(bins[0].created).toBe(2);
		expect(bins[0].completed).toBe(0);
		expect(bins[1].created).toBe(1);
		expect(bins[1].completed).toBe(1);
		expect(bins[1].current).toBe(true);
		expect(bins[0].current).toBe(false);
	});
});

describe('completionTime', () => {
	it('averages created→completed over the calendar window, 1 decimal, null when empty', () => {
		const windowStart = new Date(2026, 5, 15 - 7 * 5).getTime(); // 6-week window start
		const ct = completionTime([
			task({ status: 'done', created_at: NOW - 5 * 86_400_000, completed_at: NOW - 86_400_000 }),   // 4d
			task({ status: 'done', created_at: NOW - 3 * 86_400_000, completed_at: NOW - 86_400_000 }),   // 2d
			task({ status: 'done', created_at: windowStart - 20 * 86_400_000, completed_at: windowStart - 10 * 86_400_000 }) // prev window: 10d
		], NOW, 6);
		expect(ct.avgDays).toBe(3);
		expect(ct.prevAvgDays).toBe(10);
		expect(completionTime([], NOW, 6)).toEqual({ avgDays: null, prevAvgDays: null });
	});
});
