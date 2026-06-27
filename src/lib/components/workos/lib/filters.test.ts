import { describe, it, expect } from 'vitest';
import { emptyFilter, matchesFilter, applyFilters } from './filters';
import type { Task, TaskFilter } from './types';

const mk = (over: Partial<Task>): Task => ({
	id: 'x', workstream_id: 'w1', team_id: 'tm', number: 1, key: 'OSL-1', title: 'Hello',
	status: 'todo', priority: 'high', assignee_ids: ['u1'], progress: 0, labels: ['l1'],
	sort_key: 1, created_by_id: 'u1', created_at: 0, updated_at: 0, ...over
});
const f = (over: Partial<TaskFilter>): TaskFilter => ({ ...emptyFilter(), ...over });

describe('matchesFilter', () => {
	it('empty filter matches everything', () => {
		expect(matchesFilter(mk({}), emptyFilter())).toBe(true);
	});
	it('status facet narrows by status', () => {
		expect(matchesFilter(mk({ status: 'todo' }), f({ statuses: ['done'] }))).toBe(false);
		expect(matchesFilter(mk({ status: 'done' }), f({ statuses: ['done'] }))).toBe(true);
	});
	it('priority facet narrows by priority', () => {
		expect(matchesFilter(mk({ priority: 'low' }), f({ priorities: ['high'] }))).toBe(false);
	});
	it('label facet matches when any label overlaps', () => {
		expect(matchesFilter(mk({ labels: ['l1', 'l2'] }), f({ labelIds: ['l2'] }))).toBe(true);
		expect(matchesFilter(mk({ labels: ['l1'] }), f({ labelIds: ['l9'] }))).toBe(false);
	});
	it('assignee facet matches when any assignee overlaps', () => {
		expect(matchesFilter(mk({ assignee_ids: ['u1'] }), f({ assigneeIds: ['u1'] }))).toBe(true);
		expect(matchesFilter(mk({ assignee_ids: ['u1'] }), f({ assigneeIds: ['u2'] }))).toBe(false);
	});
	it('text matches title or key, case-insensitive', () => {
		expect(matchesFilter(mk({ title: 'Migrate billing' }), f({ text: 'BILL' }))).toBe(true);
		expect(matchesFilter(mk({ key: 'OSL-42' }), f({ text: 'osl-42' }))).toBe(true);
		expect(matchesFilter(mk({ title: 'X', key: 'OSL-1' }), f({ text: 'zzz' }))).toBe(false);
	});
});

describe('applyFilters', () => {
	it('returns only matching tasks', () => {
		const tasks = [mk({ id: 'a', status: 'todo' }), mk({ id: 'b', status: 'done' })];
		expect(applyFilters(tasks, f({ statuses: ['done'] })).map((t) => t.id)).toEqual(['b']);
	});
});
