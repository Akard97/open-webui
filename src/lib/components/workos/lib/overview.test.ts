import { describe, it, expect } from 'vitest';
import type { Task } from './types';
import { computeKpis, isOverdue, daysLate, startOfLocalDay, addLocalDays, agoLabel, localWeekStart, weeklyMomentum, completionTime, priorityPairs, statusMix, teamRows, attentionList } from './overview';

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

describe('priorityPairs / statusMix', () => {
	it('priority pairs cover OPEN and sum to open count; None only when present', () => {
		const list = [
			task({ priority: 'urgent' }), task({ priority: 'high' }), task({ priority: null }),
			task({ priority: 'urgent', status: 'done', completed_at: NOW })
		];
		const pairs = priorityPairs(list);
		expect(pairs.map((p) => p.key)).toEqual(['urgent', 'high', 'medium', 'low', 'none']);
		expect(pairs.reduce((s, p) => s + p.n, 0)).toBe(3);
		expect(priorityPairs([task({ priority: 'low' })]).some((p) => p.key === 'none')).toBe(false);
	});

	it('statusMix covers non-canceled tasks in STATUS_ORDER and pct sums to 100', () => {
		const mix = statusMix([
			task({ status: 'todo' }), task({ status: 'in_progress' }),
			task({ status: 'done', completed_at: NOW }), task({ status: 'canceled' })
		]);
		expect(mix.total).toBe(3);
		expect(mix.slices.map((s) => s.status)).toEqual(['backlog', 'todo', 'in_progress', 'in_review', 'done']);
		expect(Math.round(mix.slices.reduce((s, x) => s + x.pct, 0))).toBe(100);
	});
});

describe('teamRows', () => {
	const names: Record<string, string> = { a: 'Amal', b: 'Basel', c: 'Celine' };
	const nameOf = (id: string) => names[id] ?? id;

	it('counts a multi-assignee task fully for each assignee', () => {
		const rows = teamRows([task({ assignee_ids: ['a', 'b'] })], NOW, nameOf);
		expect(rows.filter((r) => r.userId).map((r) => r.open)).toEqual([1, 1]);
	});

	it('load is relative to the busiest member; unassigned row last, capped at 1', () => {
		const rows = teamRows([
			task({ assignee_ids: ['a'] }), task({ assignee_ids: ['a'] }), task({ assignee_ids: ['b'] }),
			task({}), task({}), task({})
		], NOW, nameOf);
		const a = rows.find((r) => r.userId === 'a')!;
		const b = rows.find((r) => r.userId === 'b')!;
		const un = rows[rows.length - 1];
		expect(a.load).toBe(1);
		expect(b.load).toBe(0.5);
		expect(un.userId).toBeNull();
		expect(un.open).toBe(3);
		expect(un.load).toBe(1); // 3/2 capped
		expect(un.health).toBeNull();
	});

	it('health: 2+ overdue/behind → needs_support; exactly 1 → watch; else on_track', () => {
		const overdue1 = task({ assignee_ids: ['a'], due_date: dueUtc(2026, 5, 10) });
		const overdue2 = task({ assignee_ids: ['a'], due_date: dueUtc(2026, 5, 11) });
		const fine = task({ assignee_ids: ['b'] });
		const oneLate = task({ assignee_ids: ['c'], due_date: dueUtc(2026, 5, 10) });
		const rows = teamRows([overdue1, overdue2, fine, oneLate], NOW, nameOf);
		expect(rows.find((r) => r.userId === 'a')!.health).toBe('needs_support');
		expect(rows.find((r) => r.userId === 'b')!.health).toBe('on_track');
		expect(rows.find((r) => r.userId === 'c')!.health).toBe('watch');
	});

	it('sorts by open desc then name', () => {
		const rows = teamRows([
			task({ assignee_ids: ['c'] }), task({ assignee_ids: ['b'] }), task({ assignee_ids: ['b'] }),
			task({ assignee_ids: ['a'] })
		], NOW, nameOf);
		expect(rows.map((r) => r.userId)).toEqual(['b', 'a', 'c']);
	});
});

describe('attentionList', () => {
	it('classifies once per task with severity ordering: overdue, behind, at_risk, due_soon', () => {
		const overdue = task({ due_date: dueUtc(2026, 5, 14) });
		const overdueWorse = task({ due_date: dueUtc(2026, 5, 10) });
		// behind: planned far ahead of actual (started 20d ago, due in 10d, 0% done → gap ≥ 25)
		const behind = task({ start_date: dueUtc(2026, 4, 28), due_date: dueUtc(2026, 5, 27), progress: 0 });
		// at risk: gap in [10, 25)
		const atRisk = task({ start_date: dueUtc(2026, 5, 7), due_date: dueUtc(2026, 6, 17), progress: 10 });
		const dueToday = task({ due_date: dueUtc(2026, 5, 17), progress: 100 });
		const calm = task({ due_date: dueUtc(2026, 6, 30) });
		const items = attentionList([calm, dueToday, atRisk, behind, overdue, overdueWorse], NOW);
		expect(items.map((i) => i.cls)).toEqual(['overdue', 'overdue', 'behind', 'at_risk', 'due_soon']);
		expect(items[0].task.id).toBe(overdueWorse.id); // most late first
		expect(items[0].daysLate).toBe(7);
		expect(items[4].dueLabel).toBe('today');
		expect(items.some((i) => i.task.id === calm.id)).toBe(false);
	});
});
