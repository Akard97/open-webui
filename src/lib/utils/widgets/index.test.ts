import { describe, expect, it } from 'vitest';
import { validateWidget } from './index';

describe('validateWidget: tasks', () => {
	it('accepts a minimal payload and defaults layout to list', () => {
		const result = validateWidget({ type: 'tasks', items: [{ title: 'Fix login' }] });
		expect(result.ok).toBe(true);
		if (!result.ok) return;
		expect(result.widget).toEqual({
			type: 'tasks',
			title: undefined,
			layout: 'list',
			items: [
				{
					key: '',
					title: 'Fix login',
					status: undefined,
					priority: undefined,
					due: undefined,
					progress: undefined,
					assignees: undefined,
					note: undefined,
					id: undefined,
					ws: undefined
				}
			]
		});
	});

	it('keeps a cards layout and coerces a full item', () => {
		const result = validateWidget({
			type: 'tasks',
			title: 'Focus',
			layout: 'cards',
			items: [
				{
					key: 'OSL-14',
					title: 'Migrate billing',
					status: 'in_review',
					priority: 'urgent',
					due: '2026-06-10',
					progress: '55',
					assignees: ['Lara', 42],
					note: 'past due',
					id: 't-1',
					ws: 's-1'
				}
			]
		});
		expect(result.ok).toBe(true);
		if (!result.ok) return;
		const item = (result.widget as any).items[0];
		expect((result.widget as any).layout).toBe('cards');
		expect(item.progress).toBe(55);
		expect(item.assignees).toEqual(['Lara', '42']);
		expect(item.id).toBe('t-1');
		expect(item.ws).toBe('s-1');
	});

	it('clamps out-of-range progress and drops non-numeric progress', () => {
		const result = validateWidget({
			type: 'tasks',
			items: [
				{ title: 'a', progress: 250 },
				{ title: 'b', progress: -5 },
				{ title: 'c', progress: 'soon' },
				{ title: 'd', progress: null }
			]
		});
		expect(result.ok).toBe(true);
		if (!result.ok) return;
		const items = (result.widget as any).items;
		expect(items[0].progress).toBe(100);
		expect(items[1].progress).toBe(0);
		expect(items[2].progress).toBeUndefined();
		expect(items[3].progress).toBeUndefined();
	});

	it('passes unknown status and priority strings through', () => {
		const result = validateWidget({
			type: 'tasks',
			items: [{ title: 'a', status: 'weird_state', priority: 'p0' }]
		});
		expect(result.ok).toBe(true);
		if (!result.ok) return;
		const item = (result.widget as any).items[0];
		expect(item.status).toBe('weird_state');
		expect(item.priority).toBe('p0');
	});

	it('drops title-less items and fails when none remain', () => {
		const partial = validateWidget({
			type: 'tasks',
			items: [{ note: 'no title' }, { title: 'kept' }]
		});
		expect(partial.ok).toBe(true);
		if (partial.ok) expect((partial.widget as any).items).toHaveLength(1);

		const empty = validateWidget({ type: 'tasks', items: [{ note: 'no title' }] });
		expect(empty.ok).toBe(false);
	});

	it('rejects empty items', () => {
		expect(validateWidget({ type: 'tasks', items: [] }).ok).toBe(false);
		expect(validateWidget({ type: 'tasks' }).ok).toBe(false);
	});

	it('mentions tasks in the unknown-type error', () => {
		const result = validateWidget({ type: 'nope' });
		expect(result.ok).toBe(false);
		if (!result.ok) expect(result.error).toContain('tasks');
	});
});
