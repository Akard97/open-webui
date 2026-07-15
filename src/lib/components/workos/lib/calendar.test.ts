import { describe, it, expect } from 'vitest';
import { dayKey, sameDay, isToday, monthGrid, weekDays, agendaDays, utcDayStart } from './calendar';
import type { Task } from './types';

describe('dayKey / sameDay / isToday', () => {
	it('strips the time component', () => {
		const noon = new Date(2026, 5, 29, 12, 30).getTime();
		const midnight = new Date(2026, 5, 29, 0, 0).getTime();
		expect(dayKey(noon)).toBe(dayKey(midnight));
		expect(sameDay(noon, midnight)).toBe(true);
		expect(sameDay(noon, new Date(2026, 5, 30, 12).getTime())).toBe(false);
	});
	it('isToday compares calendar days', () => {
		const now = new Date(2026, 5, 29, 9).getTime();
		expect(isToday(new Date(2026, 5, 29, 23).getTime(), now)).toBe(true);
		expect(isToday(new Date(2026, 5, 28, 23).getTime(), now)).toBe(false);
	});
});

describe('utcDayStart', () => {
	it('returns UTC midnight of the same calendar y/m/d regardless of wall-clock time', () => {
		const morning = new Date(2026, 5, 29, 0, 15);
		const evening = new Date(2026, 5, 29, 23, 45);
		expect(utcDayStart(morning)).toBe(Date.UTC(2026, 5, 29));
		expect(utcDayStart(evening)).toBe(Date.UTC(2026, 5, 29));
	});
	it('round-trips through the create dialog\'s toISOString prefill to the same y/m/d', () => {
		// Mirrors TaskCreateDialog's toDateInput: new Date(ts).toISOString().slice(0, 10).
		const clicked = new Date(2026, 0, 1, 23, 0); // late local New Year's Day
		const iso = new Date(utcDayStart(clicked)).toISOString().slice(0, 10);
		expect(iso).toBe('2026-01-01');
	});
});

describe('monthGrid', () => {
	it('June 2026 is a 5-week grid, Sunday-first, May 31 → Jul 4', () => {
		const g = monthGrid(new Date(2026, 5, 15));
		expect(g.length).toBe(35);
		expect(g[0].getDay()).toBe(0);            // Sunday
		expect(g[0].getMonth()).toBe(4);          // May
		expect(g[0].getDate()).toBe(31);
		expect(g[34].getMonth()).toBe(6);         // July
		expect(g[34].getDate()).toBe(4);
		for (let i = 0; i < g.length; i += 7) expect(g[i].getDay()).toBe(0);
	});
	it('May 2026 needs 6 weeks (42 days)', () => {
		const g = monthGrid(new Date(2026, 4, 10));
		expect(g.length).toBe(42);
		expect(g[0].getDay()).toBe(0);
	});
});

describe('weekDays', () => {
	it('Mon 2026-06-29 → Sun Jun 28 .. Sat Jul 4', () => {
		const w = weekDays(new Date(2026, 5, 29));
		expect(w.length).toBe(7);
		expect(w[0].getDay()).toBe(0);
		expect(w[0].getDate()).toBe(28);
		expect(w[6].getMonth()).toBe(6);
		expect(w[6].getDate()).toBe(4);
	});
});

describe('agendaDays', () => {
	const mk = (id: string, due: number | null): Task =>
		({ id, due_date: due, status: 'todo' }) as Task;
	const cursor = new Date(2026, 6, 15); // July 2026

	it('groups tasks by local day, ascending', () => {
		const a = mk('a', new Date(2026, 6, 20, 9).getTime());
		const b = mk('b', new Date(2026, 6, 3, 23).getTime());
		const c = mk('c', new Date(2026, 6, 20, 18).getTime());
		const days = agendaDays([a, b, c], cursor);
		expect(days.map((d) => d.date.getDate())).toEqual([3, 20]);
		expect(days[1].tasks.map((t) => t.id)).toEqual(['a', 'c']);
	});

	it('excludes undated tasks and other months', () => {
		const inJuly = mk('x', new Date(2026, 6, 1).getTime());
		const june = mk('y', new Date(2026, 5, 30).getTime());
		const undated = mk('z', null);
		const days = agendaDays([inJuly, june, undated], cursor);
		expect(days).toHaveLength(1);
		expect(days[0].tasks.map((t) => t.id)).toEqual(['x']);
	});

	it('returns empty for a month with no due tasks', () => {
		expect(agendaDays([mk('a', null)], cursor)).toEqual([]);
	});
});
