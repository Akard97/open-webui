import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

vi.mock('./api', () => ({
	getBootstrap: vi.fn(async () => ({ teams: [], workspaces: [], workstreams: [], roles: {} })),
	listTasks: vi.fn(async () => []),
	listLabels: vi.fn(async () => []),
	createTask: vi.fn(async (t, ws, body) => ({
		id: 'srv-1', workstream_id: ws, team_id: 'tm', number: 1, key: 'OSL-1',
		title: body.title, status: body.status ?? 'backlog', priority: null, assignee_ids: [], progress: 0,
		labels: [], sort_key: 5, created_by_id: 'u1', created_at: 0, updated_at: 0
	})),
	updateTask: vi.fn(async (t, id, body) => ({ id, ...body })),
	deleteTask: vi.fn(async () => ({ deleted: true })),
	listMyTasks: vi.fn(async () => []),
	getTask: vi.fn(async () => ({
		id: 'folded', workstream_id: 'wX', team_id: 'tm', number: 9, key: 'OSL-9', title: 'Folded',
		status: 'todo', priority: null, assignee_ids: ['u1'], progress: 0, labels: [], sort_key: 1,
		created_by_id: 'u2', created_at: 0, updated_at: 0
	})),
	listSubtasks: vi.fn(async () => []),
	createSubtask: vi.fn(async (t, taskId, body) => ({
		id: 'sub-1', task_id: taskId, title: body.title, completed: false,
		sort_key: 1, created_by_id: 'u1', completed_at: null, created_at: 1, updated_at: 1
	})),
	updateSubtask: vi.fn(async (t, id, body) => ({ id, task_id: 'task-1', title: 'Sub', completed: !!body.completed, sort_key: 1, created_at: 1, updated_at: 2 })),
	deleteSubtask: vi.fn(async () => ({ deleted: true })),
	getWorkstreamActivity: vi.fn(async () => ({ items: [], daily: [] })),
	listWorkstreamAttachments: vi.fn(async () => []),
}));

vi.mock('$lib/stores', () => {
	const { writable } = require('svelte/store');
	return { socket: writable(null), user: writable({ id: 'u1', name: 'Lara', role: 'user' }) };
});

import { tasks, tasksByStatus, applyTaskEvent, currentWorkstreamId } from './store';
import type { Task } from './types';

const mk = (over: Partial<Task>): Task => ({
	id: 'x', workstream_id: 'w1', team_id: 'tm', number: 1, key: 'OSL-1', title: 't',
	status: 'todo', assignee_ids: [], progress: 0, labels: [], sort_key: 1, created_by_id: 'u1',
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

import { myTasks, applyMyWorkTaskEvent, loadMyWork, foldInMyWorkFromNotification, boardFilter } from './store';

const mkT = (over: Partial<Task>): Task => ({
	id: 'x', workstream_id: 'w1', team_id: 'tm', number: 1, key: 'OSL-1', title: 't',
	status: 'todo', assignee_ids: [], progress: 0, labels: [], sort_key: 1, created_by_id: 'u9',
	created_at: 0, updated_at: 0, ...over
});

describe('tasksByStatus filtering', () => {
	beforeEach(() => { boardFilter.set({ statuses: [], priorities: [], labelIds: [], assigneeIds: [], text: '' }); });
	it('applies the board filter before grouping', () => {
		tasks.set([mkT({ id: 'a', status: 'todo', title: 'Alpha' }), mkT({ id: 'b', status: 'todo', title: 'Beta' })]);
		boardFilter.set({ statuses: [], priorities: [], labelIds: [], assigneeIds: [], text: 'alpha' });
		const grouped = get(tasksByStatus);
		expect(grouped.todo.map((t) => t.id)).toEqual(['a']);
	});
});

describe('my work reconcile', () => {
	beforeEach(() => myTasks.set([]));

	it('adds a created-by-me task on task.created', () => {
		applyMyWorkTaskEvent('workos:task.created', mkT({ id: 'a', created_by_id: 'u1' }), 'u1');
		expect(get(myTasks).map((t) => t.id)).toEqual(['a']);
	});
	it('adds an assigned-to-me task and dedupes', () => {
		applyMyWorkTaskEvent('workos:task.created', mkT({ id: 'a', assignee_ids: ['u1'] }), 'u1');
		applyMyWorkTaskEvent('workos:task.created', mkT({ id: 'a', assignee_ids: ['u1'] }), 'u1');
		expect(get(myTasks).filter((t) => t.id === 'a')).toHaveLength(1);
	});
	it('removes a task on update when I am no longer assignee/creator', () => {
		myTasks.set([mkT({ id: 'a', assignee_ids: ['u1'], created_by_id: 'u9' })]);
		applyMyWorkTaskEvent('workos:task.updated', mkT({ id: 'a', assignee_ids: [], created_by_id: 'u9' }), 'u1');
		expect(get(myTasks)).toHaveLength(0);
	});
	it('removes a task on delete', () => {
		myTasks.set([mkT({ id: 'a', created_by_id: 'u1' })]);
		applyMyWorkTaskEvent('workos:task.deleted', { id: 'a' }, 'u1');
		expect(get(myTasks)).toHaveLength(0);
	});
	it('folds in a task from a new assigned notification while active', async () => {
		await loadMyWork(); // sets myWorkActive = true; mocked listMyTasks returns []
		await foldInMyWorkFromNotification({ type: 'assigned', task_id: 'folded' });
		expect(get(myTasks).map((t) => t.id)).toContain('folded');
	});
});

import { workspaces, workstreams, applyNavEvent } from './store';

const mkWs = (over: any) => ({ id: 'ws1', team_id: 'tm', name: 'Eng', visibility: 'team', archived: false, created_at: 0, updated_at: 0, ...over });
const mkSt = (over: any) => ({ id: 's1', workspace_id: 'ws1', name: 'Plat', archived: false, created_at: 0, updated_at: 0, ...over });

import { wsActivity, applyOverviewActivityEvent, loadWorkstreamActivity } from './store';
import * as api from './api';

describe('loadWorkstreamActivity stale-error guard', () => {
	it('does not clobber a newer workstream\'s state when an older load rejects late', async () => {
		let rejectDeferred!: (e: unknown) => void;
		vi.mocked(api.getWorkstreamActivity).mockImplementationOnce(
			() => new Promise((_resolve, reject) => { rejectDeferred = reject; })
		);

		currentWorkstreamId.set('ws-A');
		const pending = loadWorkstreamActivity('ws-A'); // resets wsActivity synchronously

		const wsBState = { items: [{ id: 'b1' } as any], daily: [{ day: '2026-07-01', n: 2 }], loaded: true, error: false };
		currentWorkstreamId.set('ws-B');
		wsActivity.set(wsBState);

		rejectDeferred(new Error('late failure for A'));
		await pending;

		expect(get(wsActivity)).toEqual(wsBState);
	});
});

describe('applyOverviewActivityEvent', () => {
	it('prepends for the current workstream, dedupes, and bumps today bucket', () => {
		currentWorkstreamId.set('ws1');
		tasks.set([{ id: 'tsk', key: 'K-1', title: 'Task' } as any]);
		const d = new Date();
		const p = (n: number) => String(n).padStart(2, '0');
		const today = `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
		wsActivity.set({ items: [], daily: [{ day: today, n: 0 }], loaded: true, error: false });
		const payload = { id: 'a1', task_id: 'tsk', team_id: 'tm', user_id: 'u1', type: 'status_changed', data: {}, created_at: Date.now(), workstream_id: 'ws1' };
		applyOverviewActivityEvent(payload);
		applyOverviewActivityEvent(payload); // duplicate → ignored
		const s = get(wsActivity);
		expect(s.items).toHaveLength(1);
		expect(s.items[0].task_key).toBe('K-1'); // resolved from tasks store
		expect(s.daily[0].n).toBe(1);
	});

	it('ignores events for other workstreams', () => {
		currentWorkstreamId.set('ws1');
		wsActivity.set({ items: [], daily: [], loaded: true, error: false });
		applyOverviewActivityEvent({ id: 'a2', task_id: 'x', workstream_id: 'other', type: 'created', created_at: 1 });
		expect(get(wsActivity).items).toHaveLength(0);
	});
});

describe('nav reconcile (sidebar carry-over)', () => {
	beforeEach(() => { workspaces.set([]); workstreams.set([]); });

	it('adds a team-visible workspace on workspace.created', () => {
		applyNavEvent('workos:workspace.created', mkWs({ id: 'a', visibility: 'team' }));
		expect(get(workspaces).map((w) => w.id)).toEqual(['a']);
	});
	it('applies a restricted workspace on workspace.created (server routes to members only)', () => {
		applyNavEvent('workos:workspace.created', mkWs({ id: 'b', visibility: 'restricted' }));
		expect(get(workspaces).map((w) => w.id)).toEqual(['b']);
	});
	it('rebuilds the subtree on a team→restricted flip sequence (deleted → updated → workstream.created)', () => {
		// member client: starts with the team-visible workspace + child stream
		workspaces.set([mkWs({ id: 'ws1', visibility: 'team' })]);
		workstreams.set([mkSt({ id: 's1', workspace_id: 'ws1' })]);
		// (1) team-room deleted event drops the subtree
		applyNavEvent('workos:workspace.deleted', { id: 'ws1' });
		expect(get(workspaces)).toHaveLength(0);
		expect(get(workstreams)).toHaveLength(0);
		// (2) member user-room updated event restores the workspace
		applyNavEvent('workos:workspace.updated', mkWs({ id: 'ws1', visibility: 'restricted' }));
		expect(get(workspaces).map((w) => w.visibility)).toEqual(['restricted']);
		// (3) member user-room workstream.created restores the child
		applyNavEvent('workos:workstream.created', mkSt({ id: 's1', workspace_id: 'ws1' }));
		expect(get(workstreams).map((s) => s.id)).toEqual(['s1']);
	});
	it('removes a workspace on workspace.deleted', () => {
		workspaces.set([mkWs({ id: 'a' })]);
		applyNavEvent('workos:workspace.deleted', { id: 'a' });
		expect(get(workspaces)).toHaveLength(0);
	});
	it('adds a workstream only when its workspace is visible', () => {
		applyNavEvent('workos:workstream.created', mkSt({ id: 's9', workspace_id: 'ghost' }));
		expect(get(workstreams)).toHaveLength(0); // unknown workspace -> ignored
		workspaces.set([mkWs({ id: 'ws1' })]);
		applyNavEvent('workos:workstream.created', mkSt({ id: 's9', workspace_id: 'ws1' }));
		expect(get(workstreams).map((s) => s.id)).toEqual(['s9']);
	});
});

describe('files view realtime', () => {
	it('attachment events refetch while the Files view is open on that workstream', async () => {
		const api = await import('./api');
		const { view, applyFilesEvent } = await import('./store');
		view.set('files');
		currentWorkstreamId.set('w1');
		(api.listWorkstreamAttachments as any).mockClear();
		applyFilesEvent('workos:attachment.created', { id: 'a1', workstream_id: 'w1' });
		applyFilesEvent('workos:attachment.deleted', { id: 'a1', workstream_id: 'w1' });
		expect(api.listWorkstreamAttachments).toHaveBeenCalledTimes(2);
	});
	it('ignores other views, other workstreams, and other events', async () => {
		const api = await import('./api');
		const { view, applyFilesEvent } = await import('./store');
		(api.listWorkstreamAttachments as any).mockClear();
		view.set('board');
		currentWorkstreamId.set('w1');
		applyFilesEvent('workos:attachment.created', { id: 'a1', workstream_id: 'w1' });
		view.set('files');
		applyFilesEvent('workos:attachment.created', { id: 'a1', workstream_id: 'other' });
		applyFilesEvent('workos:comment.created', { id: 'c1', workstream_id: 'w1' });
		expect(api.listWorkstreamAttachments).not.toHaveBeenCalled();
	});
	it('loadWorkstreamFiles marks loaded and keeps items on success', async () => {
		const api = await import('./api');
		const { wsFiles, loadWorkstreamFiles } = await import('./store');
		(api.listWorkstreamAttachments as any).mockResolvedValueOnce([
			{ id: 'f1', task_id: 't1', name: 'a.txt', size: 1, created_at: 1, storage_key: 'k',
			  task_key: 'OSL-1', task_title: 'T', task_status: 'todo' }
		]);
		currentWorkstreamId.set('w1');
		await loadWorkstreamFiles('w1');
		expect(get(wsFiles)).toMatchObject({ loaded: true, error: false });
		expect(get(wsFiles).items.map((f) => f.id)).toEqual(['f1']);
	});
	it('loadWorkstreamFiles discards a stale response after workstream switch', async () => {
		const api = await import('./api');
		const { wsFiles, loadWorkstreamFiles } = await import('./store');
		(api.listWorkstreamAttachments as any).mockImplementationOnce(async () => {
			currentWorkstreamId.set('w2'); // user moved on mid-flight
			return [{ id: 'stale' }];
		});
		currentWorkstreamId.set('w1');
		await loadWorkstreamFiles('w1');
		expect(get(wsFiles).items).toEqual([]);
	});
});

describe('create dialog store plumbing', () => {
	it('addTask forwards assignees + attachment flag to the API', async () => {
		const api = await import('./api');
		const { addTask } = await import('./store');
		await addTask('w1', { title: 'New', assignee_ids: ['u2'], attachment_required: true });
		expect(api.createTask).toHaveBeenLastCalledWith(
			expect.anything(), 'w1',
			expect.objectContaining({ assignee_ids: ['u2'], attachment_required: true })
		);
	});

	it('editTask rolls back and swallows ATTACHMENT_REQUIRED', async () => {
		const api = await import('./api');
		const { editTask } = await import('./store');
		tasks.set([mk({ id: 'a', status: 'todo', attachment_required: true })]);
		(api.updateTask as any).mockRejectedValueOnce('ATTACHMENT_REQUIRED');
		await editTask('a', { status: 'done' }); // must not throw
		expect(get(tasks)[0].status).toBe('todo'); // rolled back
	});

	it('editTask rolls back and swallows the last-assignee-cleared error, with a toast', async () => {
		const api = await import('./api');
		const { editTask } = await import('./store');
		tasks.set([mk({ id: 'a', assignee_ids: ['u2'] })]);
		(api.updateTask as any).mockRejectedValueOnce('Task needs at least one assignee.');
		await editTask('a', { assignee_ids: [] }); // must not throw
		expect(get(tasks)[0].assignee_ids).toEqual(['u2']); // rolled back
	});

	it('addTask drops the temp row instead of duplicating when a realtime event beats the create response', async () => {
		const api = await import('./api');
		const { addTask } = await import('./store');
		let resolveCreate!: (t: Task) => void;
		(api.createTask as any).mockImplementationOnce(
			() => new Promise<Task>((resolve) => { resolveCreate = resolve; })
		);
		const promise = addTask('w1', { title: 'New' });
		// Simulate the realtime workos:task.created event landing before api.createTask resolves.
		const serverTask = mk({ id: 'srv-1', title: 'New' });
		tasks.update((list) => [...list, serverTask]);
		resolveCreate(serverTask);
		await promise;
		const rows = get(tasks).filter((t) => t.title === 'New');
		expect(rows).toHaveLength(1);
		expect(rows[0].id).toBe('srv-1');
		expect(get(tasks).some((t) => t.id.startsWith('temp-'))).toBe(false);
	});

	it('openTaskCreate opens the task modal with prefill', async () => {
		const { openTaskCreate, openModal } = await import('./store');
		openTaskCreate('w1', { status: 'todo' });
		expect(get(openModal)).toEqual({ kind: 'task', workstreamId: 'w1', prefill: { status: 'todo' } });
	});
});
