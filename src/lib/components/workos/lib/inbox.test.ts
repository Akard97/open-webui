import { describe, it, expect } from 'vitest';
import { groupInbox, isNeedsYou, dayLabelOf } from './inbox';
import type { Notification } from './types';

const NOW = new Date(2026, 6, 19, 12, 0, 0).getTime(); // local Jul 19 2026 noon

const mk = (over: Partial<Notification>): Notification => ({
	id: Math.random().toString(36).slice(2), user_id: 'u1', actor_id: 'u2', task_id: 't1',
	comment_id: null, type: 'commented', data: {}, read: false, archived: false,
	created_at: NOW - 3_600_000, ...over
});

describe('isNeedsYou', () => {
	it('is true only for unread mentioned/assigned', () => {
		expect(isNeedsYou(mk({ type: 'mentioned' }))).toBe(true);
		expect(isNeedsYou(mk({ type: 'assigned' }))).toBe(true);
		expect(isNeedsYou(mk({ type: 'mentioned', read: true }))).toBe(false);
		expect(isNeedsYou(mk({ type: 'commented' }))).toBe(false);
	});
});

describe('dayLabelOf', () => {
	it('labels today/yesterday/older', () => {
		expect(dayLabelOf(NOW - 60_000, NOW)).toBe('Today');
		expect(dayLabelOf(NOW - 86_400_000, NOW)).toBe('Yesterday');
		expect(dayLabelOf(NOW - 3 * 86_400_000, NOW)).not.toMatch(/Today|Yesterday/);
	});
});

describe('groupInbox', () => {
	it('splits needs-you from the feed', () => {
		const m = mk({ id: 'm', type: 'mentioned' });
		const c = mk({ id: 'c', type: 'commented' });
		const g = groupInbox([m, c], NOW);
		expect(g.needsYou.map((n) => n.id)).toEqual(['m']);
		expect(g.days[0].entries.map((e) => e.latest.id)).toEqual(['c']);
	});

	it('read mentions flow into the feed', () => {
		const m = mk({ id: 'm', type: 'mentioned', read: true });
		const g = groupInbox([m], NOW);
		expect(g.needsYou).toHaveLength(0);
		expect(g.days[0].entries[0].latest.id).toBe('m');
	});

	it('groups by day and stacks only consecutive same-task rows within a day', () => {
		const a1 = mk({ id: 'a1', task_id: 'tA', created_at: NOW - 1000 });
		const a2 = mk({ id: 'a2', task_id: 'tA', created_at: NOW - 2000 });
		const b = mk({ id: 'b', task_id: 'tB', created_at: NOW - 3000 });
		const a3 = mk({ id: 'a3', task_id: 'tA', created_at: NOW - 4000 }); // tA again, but not consecutive
		const old = mk({ id: 'old', task_id: 'tA', created_at: NOW - 86_400_000 }); // yesterday
		const g = groupInbox([a1, a2, b, a3, old], NOW);
		expect(g.days.map((d) => d.label)).toEqual(['Today', 'Yesterday']);
		const today = g.days[0].entries;
		expect(today.map((e) => e.latest.id)).toEqual(['a1', 'b', 'a3']);
		expect(today[0].stack.map((n) => n.id)).toEqual(['a1', 'a2']);
		expect(g.days[1].entries[0].stack).toHaveLength(1); // day boundary breaks the stack
	});

	it('null task_id never stacks', () => {
		const x = mk({ id: 'x', task_id: null, created_at: NOW - 1000 });
		const y = mk({ id: 'y', task_id: null, created_at: NOW - 2000 });
		const g = groupInbox([x, y], NOW);
		expect(g.days[0].entries).toHaveLength(2);
	});
});
