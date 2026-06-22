import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

vi.mock('./api', () => ({
	getBootstrap: vi.fn(async () => ({ teams: [], workspaces: [], workstreams: [], roles: {} })),
	listTasks: vi.fn(async () => []),
	listLabels: vi.fn(async () => []),
	createTask: vi.fn(async (t, ws, body) => ({
		id: 'srv-1', workstream_id: ws, team_id: 'tm', number: 1, key: 'OSL-1',
		title: body.title, status: body.status ?? 'backlog', priority: null, progress: 0,
		labels: [], sort_key: 5, created_by_id: 'u1', created_at: 0, updated_at: 0
	})),
	updateTask: vi.fn(async (t, id, body) => ({ id, ...body })),
	deleteTask: vi.fn(async () => ({ deleted: true }))
}));

vi.mock('$lib/stores', () => {
	const { writable } = require('svelte/store');
	return { socket: writable(null), user: writable({ id: 'u1', name: 'Lara', role: 'user' }) };
});

import { tasks, tasksByStatus, applyTaskEvent, currentWorkstreamId } from './store';
import type { Task } from './types';

const mk = (over: Partial<Task>): Task => ({
	id: 'x', workstream_id: 'w1', team_id: 'tm', number: 1, key: 'OSL-1', title: 't',
	status: 'todo', progress: 0, labels: [], sort_key: 1, created_by_id: 'u1',
	created_at: 0, updated_at: 0, ...over
});

beforeEach(() => {
	tasks.set([]);
	currentWorkstreamId.set('w1');
});

describe('store realtime reconcile', () => {
	it('applyTaskEvent created adds a task once (dedupes by id)', () => {
		applyTaskEvent('workos:task.created', mk({ id: 'a' }));
		applyTaskEvent('workos:task.created', mk({ id: 'a' }));
		expect(get(tasks).filter((t) => t.id === 'a')).toHaveLength(1);
	});
	it('applyTaskEvent updated replaces fields', () => {
		tasks.set([mk({ id: 'a', title: 'old' })]);
		applyTaskEvent('workos:task.updated', mk({ id: 'a', title: 'new' }));
		expect(get(tasks)[0].title).toBe('new');
	});
	it('applyTaskEvent deleted removes the task', () => {
		tasks.set([mk({ id: 'a' }), mk({ id: 'b' })]);
		applyTaskEvent('workos:task.deleted', { id: 'a', workstream_id: 'w1' });
		expect(get(tasks).map((t) => t.id)).toEqual(['b']);
	});
	it('ignores events for a different workstream', () => {
		applyTaskEvent('workos:task.created', mk({ id: 'z', workstream_id: 'other' }));
		expect(get(tasks)).toHaveLength(0);
	});
	it('tasksByStatus groups by status', () => {
		tasks.set([mk({ id: 'a', status: 'todo' }), mk({ id: 'b', status: 'done' })]);
		const grouped = get(tasksByStatus);
		expect(grouped.todo.map((t) => t.id)).toEqual(['a']);
		expect(grouped.done.map((t) => t.id)).toEqual(['b']);
	});
});

describe('store optimistic add', () => {
	it('addTask inserts optimistically then reconciles to the server task', async () => {
		const { addTask } = await import('./store');
		await addTask('w1', { title: 'New' });
		const ids = get(tasks).map((t) => t.id);
		expect(ids).toContain('srv-1'); // server id present after reconcile
		expect(get(tasks).filter((t) => t.title === 'New')).toHaveLength(1); // no duplicate
	});
});
