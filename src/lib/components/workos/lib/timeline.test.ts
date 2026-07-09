import { describe, it, expect } from 'vitest';
import type { Task } from './types';
import {
	DAY_MS, tsToDay, dayToTs, todayDay,
	classifyTask, timelineItems, unscheduledTasks,
	computeWindow, MIN_WINDOW_DAYS,
	ZOOM_DAY_WIDTH, parseZoom, dayToX, xToDay, todayLineX, barGeometry, isWeekend, isWeekStart, dayNumber, monthSpans, weekSpans,
	applyMove, applyResize
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
	it('sorts by creation date (oldest first), then title', () => {
		const items = timelineItems([
			makeTask({ id: 'newest', title: 'A', created_at: 300, start_date: dayToTs(s) }),
			makeTask({ id: 'tie-z', title: 'Z', created_at: 100, start_date: dayToTs(s + 2), due_date: dayToTs(e) }),
			makeTask({ id: 'tie-a', title: 'A', created_at: 100, due_date: dayToTs(e) })
		]);
		expect(items.map((i) => i.task.id)).toEqual(['tie-a', 'tie-z', 'newest']);
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

describe('zoom + scale', () => {
	it('parseZoom accepts the three column units and defaults to day', () => {
		expect(parseZoom('day')).toBe('day');
		expect(parseZoom('week')).toBe('week');
		expect(parseZoom('month')).toBe('month');
		expect(parseZoom(null)).toBe('day');
		expect(parseZoom('quarter')).toBe('day'); // legacy stored value
	});
	it('dayToX/xToDay round-trip at every preset width', () => {
		const win = { startDay: 100, endDay: 199, days: 100 };
		for (const w of Object.values(ZOOM_DAY_WIDTH)) {
			expect(dayToX(107, win, w)).toBe(7 * w);
			expect(xToDay(7 * w, win, w)).toBe(107);
			expect(xToDay(7 * w + w - 1, win, w)).toBe(107); // anywhere in the column
		}
	});
	it('todayLineX sits mid-column', () => {
		const win = { startDay: 100, endDay: 199, days: 100 };
		expect(todayLineX(107, win, 24)).toBe(7 * 24 + 12);
	});
});

describe('barGeometry', () => {
	const win = { startDay: 100, endDay: 199, days: 100 };
	const w = 24;
	it('bar spans inclusive days', () => {
		const item = { task: makeTask({ status: 'in_progress' }), kind: 'bar' as const, startDay: 110, endDay: 114 };
		const g = barGeometry(item, win, w, 120);
		expect(g.left).toBe(10 * w);
		expect(g.width).toBe(5 * w); // 5 inclusive days
	});
	it('open + past-due grows a slip tail up to the today line', () => {
		const item = { task: makeTask({ status: 'in_progress' }), kind: 'bar' as const, startDay: 110, endDay: 114 };
		const g = barGeometry(item, win, w, 120);
		// tail: from bar end (day 115 boundary) to mid-column of day 120
		expect(g.slipWidth).toBe(todayLineX(120, win, w) - (g.left + g.width));
		expect(g.slipWidth).toBeGreaterThan(0);
	});
	it('done tasks and future tasks have no slip', () => {
		const done = { task: makeTask({ status: 'done' }), kind: 'bar' as const, startDay: 110, endDay: 114 };
		expect(barGeometry(done, win, w, 120).slipWidth).toBe(0);
		const future = { task: makeTask({ status: 'todo' }), kind: 'bar' as const, startDay: 130, endDay: 134 };
		expect(barGeometry(future, win, w, 120).slipWidth).toBe(0);
	});
	it('due today → no slip (the due day is not overdue)', () => {
		const item = { task: makeTask({ status: 'todo' }), kind: 'bar' as const, startDay: 118, endDay: 120 };
		expect(barGeometry(item, win, w, 120).slipWidth).toBe(0);
	});
});

describe('header helpers', () => {
	it('weekend/week-start use UTC weekdays', () => {
		const sat = Date.UTC(2026, 6, 11) / DAY_MS; // 2026-07-11 = Saturday
		expect(isWeekend(sat)).toBe(true);
		expect(isWeekend(sat + 1)).toBe(true); // Sunday
		expect(isWeekend(sat + 2)).toBe(false); // Monday
		expect(isWeekStart(sat + 2)).toBe(true);
	});
	it('dayNumber reads the UTC date', () => {
		expect(dayNumber(Date.UTC(2026, 6, 9) / DAY_MS)).toBe(9);
	});
	it('monthSpans groups the window by UTC month with day counts', () => {
		const start = Date.UTC(2026, 5, 28) / DAY_MS; // Jun 28
		const win = { startDay: start, endDay: start + 9, days: 10 }; // Jun 28 – Jul 7
		const spans = monthSpans(win);
		expect(spans).toEqual([
			{ label: 'June 2026', startDay: start, days: 3 },
			{ label: 'July 2026', startDay: start + 3, days: 7 }
		]);
	});
	it('weekSpans chunks into Monday-start weeks with cross-month labels', () => {
		const sat = Date.UTC(2026, 5, 27) / DAY_MS; // 2026-06-27 = Saturday
		const win = { startDay: sat, endDay: sat + 15, days: 16 }; // Jun 27 – Jul 12
		const spans = weekSpans(win);
		expect(spans.map((s) => [s.startDay, s.days])).toEqual([
			[sat, 2], // partial Sat–Sun edge
			[sat + 2, 7], // Jun 29 – Jul 5
			[sat + 9, 7] // Jul 6 – 12
		]);
		expect(spans[1].label).toBe('Jun 29 – Jul 5');
		expect(spans[2].label).toBe('Jul 6 – 12');
	});
});

describe('applyMove', () => {
	const s = D('2026-07-01'), e = D('2026-07-05');
	it('shifts both dates of a full bar', () => {
		const item = timelineItems([makeTask({ start_date: dayToTs(s), due_date: dayToTs(e) })])[0];
		expect(applyMove(item, 3)).toEqual({ start_date: dayToTs(s + 3), due_date: dayToTs(e + 3) });
		expect(applyMove(item, -2)).toEqual({ start_date: dayToTs(s - 2), due_date: dayToTs(e - 2) });
	});
	it('start-only bar moves only start_date', () => {
		const item = timelineItems([makeTask({ start_date: dayToTs(s) })])[0];
		expect(applyMove(item, 4)).toEqual({ start_date: dayToTs(s + 4) });
	});
	it('milestone moves only due_date', () => {
		const item = timelineItems([makeTask({ due_date: dayToTs(e) })])[0];
		expect(applyMove(item, -1)).toEqual({ due_date: dayToTs(e - 1) });
	});
});

describe('applyResize', () => {
	const s = D('2026-07-01'), e = D('2026-07-05');
	const bar = () => timelineItems([makeTask({ start_date: dayToTs(s), due_date: dayToTs(e) })])[0];
	it('start edge moves start_date only', () => {
		expect(applyResize(bar(), 'start', 2)).toEqual({ start_date: dayToTs(s + 2) });
	});
	it('end edge moves due_date only', () => {
		expect(applyResize(bar(), 'end', -1)).toEqual({ due_date: dayToTs(e - 1) });
	});
	it('clamps to a 1-day minimum (start cannot pass end, end cannot pass start)', () => {
		expect(applyResize(bar(), 'start', 99)).toEqual({ start_date: dayToTs(e) });
		expect(applyResize(bar(), 'end', -99)).toEqual({ due_date: dayToTs(s) });
	});
	it('end edge on a start-only bar creates a due_date ≥ start', () => {
		const item = timelineItems([makeTask({ start_date: dayToTs(s) })])[0];
		expect(applyResize(item, 'end', 3)).toEqual({ due_date: dayToTs(s + 3) });
		expect(applyResize(item, 'end', -5)).toEqual({ due_date: dayToTs(s) });
	});
	it('start edge on a milestone creates a start_date ≤ due', () => {
		const item = timelineItems([makeTask({ due_date: dayToTs(e) })])[0];
		expect(applyResize(item, 'start', -3)).toEqual({ start_date: dayToTs(e - 3) });
		expect(applyResize(item, 'start', 4)).toEqual({ start_date: dayToTs(e) });
	});
});
