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
	deleteTask: vi.fn(async () => ({ deleted: true })),
	listSubtasks: vi.fn(async () => []),
	createSubtask: vi.fn(async (t, taskId, body) => ({
		id: 'sub-1', task_id: taskId, title: body.title, completed: false,
		sort_key: 1, created_by_id: 'u1', completed_at: null, created_at: 1, updated_at: 1
	})),
	updateSubtask: vi.fn(async (t, id, body) => ({ id, task_id: 'task-1', title: 'Sub', completed: !!body.completed, sort_key: 1, created_at: 1, updated_at: 2 })),
	deleteSubtask: vi.fn(async () => ({ deleted: true })),
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

import {
	selectedTaskId, comments, activity, unreadCount, notifications,
	applyCollabEvent, applyNotificationEvent, subtasks
} from './store';

describe('subtask realtime', () => {
	it('applies subtask events only for the open task', () => {
		selectedTaskId.set('task-1');
		subtasks.set([]);
		applyCollabEvent('workos:subtask.created', {
			id: 's1', task_id: 'task-1', title: 'Draft', completed: false,
			sort_key: 1, created_by_id: 'u1', completed_at: null, created_at: 1, updated_at: 1
		});
		expect(get(subtasks).map((s) => s.id)).toEqual(['s1']);

		applyCollabEvent('workos:subtask.updated', {
			id: 's1', task_id: 'task-1', title: 'Draft', completed: true,
			sort_key: 1, created_by_id: 'u1', completed_at: 2, created_at: 1, updated_at: 2
		});
		expect(get(subtasks)[0].completed).toBe(true);

		applyCollabEvent('workos:subtask.deleted', { id: 's1', task_id: 'task-1' });
		expect(get(subtasks)).toEqual([]);
	});
});

describe('collab realtime', () => {
	it('applies comment.created only for the open task', () => {
		selectedTaskId.set('task-1');
		comments.set([]);
		applyCollabEvent('workos:comment.created', {
			id: 'c1', task_id: 'task-1', user_id: 'u2', body: 'hi', mentions: [],
			edited_at: null, created_at: 1, updated_at: 1, workstream_id: 'w1', actor_id: 'u2'
		});
		expect(get(comments).map((c) => c.id)).toEqual(['c1']);

		applyCollabEvent('workos:comment.created', {
			id: 'c2', task_id: 'other', user_id: 'u2', body: 'x', mentions: [],
			edited_at: null, created_at: 2, updated_at: 2, workstream_id: 'w1', actor_id: 'u2'
		});
		expect(get(comments).map((c) => c.id)).toEqual(['c1']); // ignored: different task
	});

	it('applies comment.deleted', () => {
		selectedTaskId.set('task-1');
		comments.set([{ id: 'c1', task_id: 'task-1', user_id: 'u2', body: 'hi', mentions: [],
			edited_at: null, created_at: 1, updated_at: 1 }]);
		applyCollabEvent('workos:comment.deleted', { id: 'c1', task_id: 'task-1' });
		expect(get(comments)).toEqual([]);
	});

	it('increments unread on notification.created', () => {
		unreadCount.set(0);
		notifications.set([]);
		applyNotificationEvent({ id: 'n1', user_id: 'u1', type: 'assigned', data: {}, read: false, created_at: 1 });
		expect(get(unreadCount)).toBe(1);
		expect(get(notifications).map((n) => n.id)).toEqual(['n1']);
	});
});
