import { describe, it, expect } from 'vitest';
import { activityLabel } from './activity';
import type { Activity } from './types';

const nameOf = (id: string | null | undefined) =>
	(id ? ({ u1: 'Lara', u2: 'Yusuf', u3: 'Mara' } as Record<string, string>)[id] ?? id : 'Unassigned');

const act = (over: Partial<Activity>): Activity => ({
	id: 'a', task_id: 't', user_id: 'u1', type: 'assignee_changed', data: {}, created_at: 0, ...over
});

describe('activityLabel — assignee_changed', () => {
	it('reports a single added assignee', () => {
		const s = activityLabel(act({ data: { added: ['u2'], removed: [] } }), nameOf);
		expect(s).toBe('Lara assigned Yusuf');
	});
	it('reports multiple added assignees', () => {
		const s = activityLabel(act({ data: { added: ['u2', 'u3'], removed: [] } }), nameOf);
		expect(s).toBe('Lara assigned Yusuf, Mara');
	});
	it('reports a removed assignee', () => {
		const s = activityLabel(act({ data: { added: [], removed: ['u2'] } }), nameOf);
		expect(s).toBe('Lara unassigned Yusuf');
	});
	it('reports both added and removed in one entry', () => {
		const s = activityLabel(act({ data: { added: ['u3'], removed: ['u2'] } }), nameOf);
		expect(s).toBe('Lara assigned Mara and unassigned Yusuf');
	});
	it('falls back gracefully for legacy single-value payloads', () => {
		const s = activityLabel(act({ data: { from: null, to: 'u2' } }), nameOf);
		expect(s).toBe('Lara assigned Yusuf');
	});
});

describe('activityLabel — other types still work', () => {
	it('renders a status change', () => {
		const s = activityLabel(act({ type: 'status_changed', data: { from: 'todo', to: 'in_progress' } }), nameOf);
		expect(s).toBe('Lara changed status Todo → In Progress');
	});
});
