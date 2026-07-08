import { describe, it, expect } from 'vitest';
import type { Task } from './types';
import {
	DAY_MS, tsToDay, dayToTs, todayDay,
	classifyTask, timelineItems, unscheduledTasks,
	computeWindow, MIN_WINDOW_DAYS
} from './timeline';

// Minimal task factory — only the fields the timeline math reads.
export function makeTask(over: Partial<Task> = {}): Task {
	return {
		id: over.id ?? 't1', workstream_id: 'ws1', team_id: 'tm1', number: 1, key: 'T-1',
		title: 'Task', status: 'todo', priority: null, assignee_ids: [],
		start_date: null, due_date: null, progress: 0, labels: [], sort_key: 0,
		created_by_id: null, completed_at: null, created_at: 0, updated_at: 0,
		...over
	} as Task;
}

// Day index for an ISO date (tests use exact UTC midnights, like storage).
const D = (iso: string) => {
	const [y, m, d] = iso.split('-').map(Number);
	return Date.UTC(y, m - 1, d) / DAY_MS;
};

describe('day encoding', () => {
	it('round-trips UTC midnights', () => {
		const ts = Date.UTC(2026, 6, 9); // 2026-07-09T00:00Z
		expect(tsToDay(ts)).toBe(ts / DAY_MS);
		expect(dayToTs(tsToDay(ts))).toBe(ts);
	});
	it('floors timestamps that carry a time component', () => {
		const noon = Date.UTC(2026, 6, 9, 12, 30);
		expect(tsToDay(noon)).toBe(Date.UTC(2026, 6, 9) / DAY_MS);
	});
	it('todayDay encodes the LOCAL calendar date as a UTC day index', () => {
		const now = new Date(2026, 6, 9, 23, 30).getTime(); // 11:30pm local, July 9
		expect(todayDay(now)).toBe(Date.UTC(2026, 6, 9) / DAY_MS);
	});
});

describe('classifyTask', () => {
	it('start+due → bar', () => {
		expect(classifyTask(makeTask({ start_date: dayToTs(D('2026-07-01')), due_date: dayToTs(D('2026-07-05')) }))).toBe('bar');
	});
	it('start-only → bar (1-day)', () => {
		expect(classifyTask(makeTask({ start_date: dayToTs(D('2026-07-01')) }))).toBe('bar');
	});
	it('due-only → milestone', () => {
		expect(classifyTask(makeTask({ due_date: dayToTs(D('2026-07-05')) }))).toBe('milestone');
	});
	it('dateless → unscheduled', () => {
		expect(classifyTask(makeTask())).toBe('unscheduled');
	});
});

describe('timelineItems', () => {
	const s = D('2026-07-01'), e = D('2026-07-05');
	it('builds inclusive day ranges and drops canceled + unscheduled', () => {
		const items = timelineItems([
			makeTask({ id: 'a', start_date: dayToTs(s), due_date: dayToTs(e) }),
			makeTask({ id: 'b' }), // unscheduled
			makeTask({ id: 'c', status: 'canceled', start_date: dayToTs(s), due_date: dayToTs(e) })
		]);
		expect(items.map((i) => i.task.id)).toEqual(['a']);
		expect(items[0]).toMatchObject({ kind: 'bar', startDay: s, endDay: e });
	});
	it('start-only → 1-day bar; due-only → milestone on its day', () => {
		const items = timelineItems([
			makeTask({ id: 'a', start_date: dayToTs(s) }),
			makeTask({ id: 'b', due_date: dayToTs(e) })
		]);
		expect(items.find((i) => i.task.id === 'a')).toMatchObject({ kind: 'bar', startDay: s, endDay: s });
		expect(items.find((i) => i.task.id === 'b')).toMatchObject({ kind: 'milestone', startDay: e, endDay: e });
	});
	it('clamps due-before-start to a 1-day bar at start', () => {
		const items = timelineItems([makeTask({ start_date: dayToTs(e), due_date: dayToTs(s) })]);
		expect(items[0]).toMatchObject({ startDay: e, endDay: e });
	});
	it('sorts by startDay, then endDay, then title', () => {
		const items = timelineItems([
			makeTask({ id: 'late', title: 'B', start_date: dayToTs(s + 2), due_date: dayToTs(e) }),
			makeTask({ id: 'longer', title: 'Z', start_date: dayToTs(s), due_date: dayToTs(e + 1) }),
			makeTask({ id: 'first', title: 'A', start_date: dayToTs(s), due_date: dayToTs(e) })
		]);
		expect(items.map((i) => i.task.id)).toEqual(['first', 'longer', 'late']);
	});
});

describe('unscheduledTasks', () => {
	it('returns dateless, non-canceled tasks only', () => {
		const out = unscheduledTasks([
			makeTask({ id: 'a' }),
			makeTask({ id: 'b', status: 'canceled' }),
			makeTask({ id: 'c', due_date: dayToTs(D('2026-07-05')) })
		]);
		expect(out.map((t) => t.id)).toEqual(['a']);
	});
});

describe('computeWindow', () => {
	const today = D('2026-07-09');
	it('pads 7 days before the min and 14 after the max', () => {
		const items = timelineItems([
			makeTask({ start_date: dayToTs(D('2026-07-01')), due_date: dayToTs(D('2026-08-20')) })
		]);
		const w = computeWindow(items, today);
		expect(w.startDay).toBe(D('2026-07-01') - 7);
		expect(w.endDay).toBe(D('2026-08-20') + 14);
		expect(w.days).toBe(w.endDay - w.startDay + 1);
	});
	it('always contains today and enforces the minimum width', () => {
		const w = computeWindow([], today);
		expect(w.startDay).toBeLessThanOrEqual(today);
		expect(w.endDay).toBeGreaterThanOrEqual(today);
		expect(w.days).toBeGreaterThanOrEqual(MIN_WINDOW_DAYS);
	});
});
