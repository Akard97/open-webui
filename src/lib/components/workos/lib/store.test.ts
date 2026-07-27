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
	listComments: vi.fn(async () => []),
	listActivity: vi.fn(async () => []),
	listAttachments: vi.fn(async () => []),
	createSubtask: vi.fn(async (t, taskId, body) => ({
		id: 'sub-1', task_id: taskId, title: body.title, completed: false,
		sort_key: 1, created_by_id: 'u1', completed_at: null, created_at: 1, updated_at: 1
	})),
	updateSubtask: vi.fn(async (t, id, body) => ({ id, task_id: 'task-1', title: 'Sub', completed: !!body.completed, sort_key: 1, created_at: 1, updated_at: 2 })),
	deleteSubtask: vi.fn(async () => ({ deleted: true })),
	getWorkstreamActivity: vi.fn(async () => ({ items: [], daily: [] })),
	listWorkstreamAttachments: vi.fn(async () => []),
	listNotifications: vi.fn(async () => []),
	getNotificationCounts: vi.fn(async () => ({
		unread: 0, by_type: { assigned: 0, subtask_assigned: 0, mentioned: 0, commented: 0, status_changed: 0 }
	})),
	archiveNotifications: vi.fn(async () => ({ unread: 0 })),
	markNotificationsRead: vi.fn(async () => ({ unread: 0 })),
	getDirectory: vi.fn(async () => []),
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

	it('editTask rolls back and swallows ATTACHMENT_REQUIRED (real HTTP error shape)', async () => {
		const api = await import('./api');
		const { editTask } = await import('./store');
		tasks.set([mk({ id: 'a', status: 'todo', attachment_required: true })]);
		// request() rejects with { detail, status } — mock the real shape, not a bare string.
		(api.updateTask as any).mockRejectedValueOnce({ detail: 'ATTACHMENT_REQUIRED', status: 400 });
		await editTask('a', { status: 'done' }); // must not throw
		expect(get(tasks)[0].status).toBe('todo'); // rolled back
	});

	it('editTask rolls back and swallows the last-assignee-cleared error, with a toast', async () => {
		const api = await import('./api');
		const { editTask } = await import('./store');
		tasks.set([mk({ id: 'a', assignee_ids: ['u2'] })]);
		(api.updateTask as any).mockRejectedValueOnce({
			detail: 'Task needs at least one assignee.', status: 400
		});
		await editTask('a', { assignee_ids: [] }); // must not throw
		expect(get(tasks)[0].assignee_ids).toEqual(['u2']); // rolled back
	});

	it('editTask still swallows bare-string sentinels (legacy error shape)', async () => {
		const api = await import('./api');
		const { editTask } = await import('./store');
		tasks.set([mk({ id: 'a', status: 'todo', attachment_required: true })]);
		(api.updateTask as any).mockRejectedValueOnce('ATTACHMENT_REQUIRED');
		await editTask('a', { status: 'done' }); // must not throw
		expect(get(tasks)[0].status).toBe('todo'); // rolled back
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

// CAREFUL: `notifications`, `unreadCount`, `applyNotificationEvent`, and
// `selectedTaskId` are ALREADY imported by the mid-file import block (~line 89)
// — re-importing them is a duplicate-binding SyntaxError. Import ONLY the new names:
import {
	notificationCounts, archivedNotifications, inboxTask, inboxTaskError,
	archiveNotificationsAction, markRead
} from './store';
import * as apiMock from './api';
import type { Notification } from './types';

const mkN = (over: Partial<Notification>): Notification => ({
	id: 'n1', user_id: 'u1', actor_id: 'u2', task_id: 't1', comment_id: null,
	type: 'commented', data: {}, read: false, archived: false, created_at: 1000, ...over
});

describe('inbox notification store', () => {
	beforeEach(() => {
		notifications.set([]);
		archivedNotifications.set([]);
		inboxTask.set(null);
		inboxTaskError.set(false);
		selectedTaskId.set(null);
		unreadCount.set(0);
		notificationCounts.set({ unread: 0, by_type: { assigned: 0, subtask_assigned: 0, mentioned: 0, commented: 0, status_changed: 0 } });
	});

	it('applyNotificationEvent prepends and bumps per-type counts', () => {
		applyNotificationEvent(mkN({ id: 'a', type: 'mentioned' }));
		applyNotificationEvent(mkN({ id: 'a', type: 'mentioned' })); // dupe ignored
		expect(get(notifications)).toHaveLength(1);
		expect(get(notificationCounts)).toEqual({
			unread: 1, by_type: { assigned: 0, subtask_assigned: 0, mentioned: 1, commented: 0, status_changed: 0 }
		});
	});

	it('markRead decrements the matching type count', async () => {
		notifications.set([mkN({ id: 'a', type: 'assigned' })]);
		notificationCounts.set({ unread: 1, by_type: { assigned: 1, subtask_assigned: 0, mentioned: 0, commented: 0, status_changed: 0 } });
		await markRead(['a']);
		expect(get(notifications)[0].read).toBe(true); // row stays, flipped to read
		expect(get(notificationCounts).by_type.assigned).toBe(0);
		expect(get(notificationCounts).unread).toBe(0);
	});

	it('archiveNotificationsAction moves the row out optimistically and marks it read', async () => {
		notifications.set([mkN({ id: 'a' }), mkN({ id: 'b' })]);
		notificationCounts.set({ unread: 2, by_type: { assigned: 0, subtask_assigned: 0, mentioned: 0, commented: 2, status_changed: 0 } });
		await archiveNotificationsAction(['a']);
		expect(get(notifications).map((n) => n.id)).toEqual(['b']);
		expect(get(archivedNotifications).map((n) => n.id)).toEqual(['a']);
		expect(get(archivedNotifications)[0].read).toBe(true);
		expect(get(notificationCounts).unread).toBe(1);
	});

	it('archive failure rolls lists and counts back', async () => {
		vi.mocked(apiMock.archiveNotifications).mockRejectedValueOnce(new Error('nope'));
		notifications.set([mkN({ id: 'a' })]);
		notificationCounts.set({ unread: 1, by_type: { assigned: 0, subtask_assigned: 0, mentioned: 0, commented: 1, status_changed: 0 } });
		await expect(archiveNotificationsAction(['a'])).rejects.toThrow();
		expect(get(notifications).map((n) => n.id)).toEqual(['a']);
		expect(get(archivedNotifications)).toHaveLength(0);
		expect(get(notificationCounts)).toEqual({
			unread: 1, by_type: { assigned: 0, subtask_assigned: 0, mentioned: 0, commented: 1, status_changed: 0 }
		});
	});

	it('rollback keeps realtime rows that arrived during the failed request', async () => {
		vi.mocked(apiMock.archiveNotifications).mockImplementationOnce(async () => {
			applyNotificationEvent(mkN({ id: 'live', type: 'assigned', created_at: 5000 }));
			throw new Error('nope');
		});
		notifications.set([mkN({ id: 'a' })]);
		notificationCounts.set({ unread: 1, by_type: { assigned: 0, subtask_assigned: 0, mentioned: 0, commented: 1, status_changed: 0 } });
		await expect(archiveNotificationsAction(['a'])).rejects.toThrow();
		expect(get(notifications).map((n) => n.id)).toEqual(['live', 'a']); // snapshot restore must not eat 'live'
		expect(get(archivedNotifications)).toHaveLength(0);
		expect(get(notificationCounts)).toEqual({
			unread: 2, by_type: { assigned: 1, subtask_assigned: 0, mentioned: 0, commented: 1, status_changed: 0 }
		});
	});

	it('task.deleted keeps the selection and flags the pane error', () => {
		inboxTask.set({ id: 't9', workstream_id: 'other' } as any);
		selectedTaskId.set('t9');
		applyTaskEvent('workos:task.deleted', { id: 't9', workstream_id: 'other' });
		expect(get(inboxTask)).toBeNull();
		expect(get(inboxTaskError)).toBe(true);
		expect(get(selectedTaskId)).toBe('t9'); // kept: the pane shows "Task no longer available"
	});

	it('unarchive moves the row back sorted by created_at', async () => {
		notifications.set([mkN({ id: 'b', created_at: 2000 })]);
		archivedNotifications.set([mkN({ id: 'a', created_at: 3000, read: true, archived: true })]);
		await archiveNotificationsAction(['a'], false);
		expect(get(notifications).map((n) => n.id)).toEqual(['a', 'b']);
		expect(get(archivedNotifications)).toHaveLength(0);
	});

	it('task.updated reconciles the inbox split-pane task across workstreams', () => {
		inboxTask.set({ id: 't9', workstream_id: 'other', title: 'old' } as any);
		applyTaskEvent('workos:task.updated', { id: 't9', workstream_id: 'other', title: 'new' });
		expect(get(inboxTask)?.title).toBe('new');
	});
});

import { markAllRead, loadNotifications, loadMoreNotifications } from './store';

describe('inbox rollback isolation + pagination cursor', () => {
	beforeEach(() => {
		notifications.set([]);
		archivedNotifications.set([]);
		inboxTask.set(null);
		inboxTaskError.set(false);
		selectedTaskId.set(null);
		unreadCount.set(0);
		notificationCounts.set({ unread: 0, by_type: { assigned: 0, subtask_assigned: 0, mentioned: 0, commented: 0, status_changed: 0 } });
	});

	it('failed markRead rolls back only its own rows, keeping a concurrent success', async () => {
		notifications.set([mkN({ id: 'a', created_at: 2000 }), mkN({ id: 'b', created_at: 1000 })]);
		notificationCounts.set({ unread: 2, by_type: { assigned: 0, subtask_assigned: 0, mentioned: 0, commented: 2, status_changed: 0 } });
		let rejectA: ((e: unknown) => void) | undefined;
		vi.mocked(apiMock.markNotificationsRead)
			.mockImplementationOnce(() => new Promise((_, rej) => { rejectA = rej; }))
			.mockResolvedValueOnce({ unread: 1 });
		const pa = markRead(['a']);
		await markRead(['b']); // B commits while A is still in flight
		rejectA!(new Error('nope'));
		await expect(pa).rejects.toThrow();
		const rows = get(notifications);
		expect(rows.find((n) => n.id === 'b')?.read).toBe(true); // committed success must survive A's rollback
		expect(rows.find((n) => n.id === 'a')?.read).toBe(false);
		expect(get(notificationCounts).unread).toBe(1);
	});

	it('failed archive does not revert a concurrent markRead success', async () => {
		notifications.set([mkN({ id: 'a', created_at: 2000 }), mkN({ id: 'b', created_at: 1000 })]);
		notificationCounts.set({ unread: 2, by_type: { assigned: 0, subtask_assigned: 0, mentioned: 0, commented: 2, status_changed: 0 } });
		let rejectArch: ((e: unknown) => void) | undefined;
		vi.mocked(apiMock.archiveNotifications)
			.mockImplementationOnce(() => new Promise((_, rej) => { rejectArch = rej; }));
		const pa = archiveNotificationsAction(['a']);
		await markRead(['b']); // commits mid-flight
		rejectArch!(new Error('nope'));
		await expect(pa).rejects.toThrow();
		const rows = get(notifications);
		expect(rows.map((n) => n.id).sort()).toEqual(['a', 'b']); // archive rolled back
		expect(rows.find((n) => n.id === 'b')?.read).toBe(true); // markRead success survives
		expect(get(notificationCounts).unread).toBe(1); // only 'a' restored as unread
	});

	it('markRead failure after a successful concurrent archive must not resurrect counts', async () => {
		notifications.set([mkN({ id: 'a' })]);
		notificationCounts.set({ unread: 1, by_type: { assigned: 0, subtask_assigned: 0, mentioned: 0, commented: 1, status_changed: 0 } });
		let rejectRead: ((e: unknown) => void) | undefined;
		vi.mocked(apiMock.markNotificationsRead)
			.mockImplementationOnce(() => new Promise((_, rej) => { rejectRead = rej; }));
		vi.mocked(apiMock.archiveNotifications).mockResolvedValueOnce({ unread: 0 });
		vi.mocked(apiMock.getNotificationCounts).mockResolvedValueOnce({
			unread: 0, by_type: { assigned: 0, subtask_assigned: 0, mentioned: 0, commented: 0, status_changed: 0 }
		});
		const pr = markRead(['a']);
		await archiveNotificationsAction(['a']); // archive commits while mark-read is in flight
		rejectRead!(new Error('nope'));
		await expect(pr).rejects.toThrow();
		expect(get(notifications)).toHaveLength(0); // archive result intact
		expect(get(archivedNotifications).map((n) => n.id)).toEqual(['a']);
		expect(get(notificationCounts).unread).toBe(0); // no phantom unread badge
		expect(get(notificationCounts).by_type.commented).toBe(0);
	});

	it('markAllRead failure refetches authoritative counts instead of restoring a stale snapshot', async () => {
		notifications.set([mkN({ id: 'a' })]);
		notificationCounts.set({ unread: 1, by_type: { assigned: 0, subtask_assigned: 0, mentioned: 0, commented: 1, status_changed: 0 } });
		vi.mocked(apiMock.markNotificationsRead).mockRejectedValueOnce(new Error('nope'));
		vi.mocked(apiMock.getNotificationCounts).mockResolvedValueOnce({
			unread: 3, by_type: { assigned: 2, subtask_assigned: 0, mentioned: 0, commented: 1, status_changed: 0 }
		});
		await expect(markAllRead()).rejects.toThrow();
		expect(get(notifications)[0].read).toBe(false); // own row restored
		expect(get(notificationCounts).unread).toBe(3); // server truth, not the pre-op snapshot
	});

	it('load-more cursor is server-owned — a locally unarchived old row must not move it', async () => {
		const page = [
			mkN({ id: 'p0', created_at: 1000 }), mkN({ id: 'p1', created_at: 999 }), mkN({ id: 'p2', created_at: 998 })
		];
		vi.mocked(apiMock.listNotifications).mockResolvedValueOnce(page);
		await loadNotifications();
		archivedNotifications.set([mkN({ id: 'old', created_at: 5, read: true, archived: true })]);
		await archiveNotificationsAction(['old'], false); // unarchive → sorts to the active list's tail
		vi.mocked(apiMock.listNotifications).mockResolvedValueOnce([]);
		await loadMoreNotifications();
		expect(vi.mocked(apiMock.listNotifications).mock.calls.at(-1)?.[1])
			.toMatchObject({ before: 998, beforeId: 'p2' }); // last SERVER row, not 'old'
		// An empty page must not advance the cursor either.
		vi.mocked(apiMock.listNotifications).mockResolvedValueOnce([]);
		await loadMoreNotifications();
		expect(vi.mocked(apiMock.listNotifications).mock.calls.at(-1)?.[1])
			.toMatchObject({ before: 998, beforeId: 'p2' });
	});
});

describe('inbox task load-error classification', () => {
	beforeEach(() => {
		notifications.set([]);
		inboxTask.set(null);
		inboxTaskError.set(false);
		selectedTaskId.set(null);
	});

	it('transient getTask failure flags a load error, not task-gone', async () => {
		const { openInboxNotification, inboxTaskLoadError } = await import('./store');
		vi.mocked(apiMock.getTask).mockRejectedValueOnce({ detail: 'boom', status: 500 });
		await openInboxNotification(mkN({ id: 'nx', task_id: 't1', read: true }));
		expect(get(inboxTaskError)).toBe(false);
		expect(get(inboxTaskLoadError)).toBe(true);
	});

	it('404 getTask failure flags task-gone, not a load error', async () => {
		const { openInboxNotification, inboxTaskLoadError } = await import('./store');
		vi.mocked(apiMock.getTask).mockRejectedValueOnce({ detail: 'Not found', status: 404 });
		await openInboxNotification(mkN({ id: 'nx', task_id: 't1', read: true }));
		expect(get(inboxTaskError)).toBe(true);
		expect(get(inboxTaskLoadError)).toBe(false);
	});
});

import {
	notificationsHasMore, archivedHasMore, loadArchivedNotifications, loadMoreArchivedNotifications
} from './store';

describe('load-more failure is not an empty page', () => {
	beforeEach(() => {
		notifications.set([]);
		archivedNotifications.set([]);
		notificationsHasMore.set(false);
		archivedHasMore.set(false);
	});

	it('failed loadMoreNotifications keeps rows, hasMore, and the cursor', async () => {
		const page = [mkN({ id: 'p0', created_at: 1000 }), mkN({ id: 'p1', created_at: 999 })];
		vi.mocked(apiMock.listNotifications).mockResolvedValueOnce(page);
		await loadNotifications();
		notificationsHasMore.set(true); // page < NOTIF_PAGE in the fixture; force the real precondition
		vi.mocked(apiMock.listNotifications).mockRejectedValueOnce(new Error('network'));
		await loadMoreNotifications(); // must not throw
		expect(get(notifications).map((n) => n.id)).toEqual(['p0', 'p1']); // rows intact
		expect(get(notificationsHasMore)).toBe(true); // Load more stays available
		// Retry must reuse the same server-owned cursor, not a corrupted one.
		vi.mocked(apiMock.listNotifications).mockResolvedValueOnce([]);
		await loadMoreNotifications();
		expect(vi.mocked(apiMock.listNotifications).mock.calls.at(-1)?.[1])
			.toMatchObject({ before: 999, beforeId: 'p1' });
	});

	it('failed loadMoreArchivedNotifications keeps rows, hasMore, and the cursor', async () => {
		const page = [
			mkN({ id: 'a0', created_at: 1000, archived: true }),
			mkN({ id: 'a1', created_at: 999, archived: true })
		];
		vi.mocked(apiMock.listNotifications).mockResolvedValueOnce(page);
		await loadArchivedNotifications();
		archivedHasMore.set(true);
		vi.mocked(apiMock.listNotifications).mockRejectedValueOnce(new Error('network'));
		await loadMoreArchivedNotifications(); // must not throw
		expect(get(archivedNotifications).map((n) => n.id)).toEqual(['a0', 'a1']);
		expect(get(archivedHasMore)).toBe(true);
		vi.mocked(apiMock.listNotifications).mockResolvedValueOnce([]);
		await loadMoreArchivedNotifications();
		expect(vi.mocked(apiMock.listNotifications).mock.calls.at(-1)?.[1])
			.toMatchObject({ archived: true, before: 999, beforeId: 'a1' });
	});
});

describe('stale list fetches must not clobber committed mutations', () => {
	beforeEach(() => {
		notifications.set([]);
		archivedNotifications.set([]);
		notificationsHasMore.set(false);
		archivedHasMore.set(false);
		unreadCount.set(0);
		notificationCounts.set({ unread: 0, by_type: { assigned: 0, subtask_assigned: 0, mentioned: 0, commented: 0, status_changed: 0 } });
	});

	it('a loadNotifications snapshot resolving after an archive is discarded', async () => {
		notifications.set([mkN({ id: 'a', read: true })]);
		let resolveList: ((v: unknown) => void) | undefined;
		vi.mocked(apiMock.listNotifications)
			.mockImplementationOnce(() => new Promise((res) => { resolveList = res; }) as any);
		const p = loadNotifications();
		await archiveNotificationsAction(['a']); // commits while the fetch is in flight
		resolveList!([mkN({ id: 'a', read: true })]); // server snapshot taken pre-archive
		await p;
		expect(get(notifications)).toHaveLength(0); // archived row must not resurrect
		expect(get(archivedNotifications).map((n) => n.id)).toEqual(['a']);
	});

	it('a loadMoreNotifications page resolving after an archive is discarded (rows + cursor)', async () => {
		const page = [mkN({ id: 'p0', created_at: 1000 }), mkN({ id: 'p1', created_at: 999 })];
		vi.mocked(apiMock.listNotifications).mockResolvedValueOnce(page);
		await loadNotifications();
		let resolveMore: ((v: unknown) => void) | undefined;
		vi.mocked(apiMock.listNotifications)
			.mockImplementationOnce(() => new Promise((res) => { resolveMore = res; }) as any);
		const p = loadMoreNotifications();
		await archiveNotificationsAction(['p1']); // commits mid-flight
		resolveMore!([mkN({ id: 'p1', created_at: 999 }), mkN({ id: 'p2', created_at: 998 })]); // stale window
		await p;
		expect(get(notifications).map((n) => n.id)).toEqual(['p0']); // stale page dropped entirely
		// The discarded page must not have advanced the server-owned cursor.
		vi.mocked(apiMock.listNotifications).mockResolvedValueOnce([]);
		await loadMoreNotifications();
		expect(vi.mocked(apiMock.listNotifications).mock.calls.at(-1)?.[1])
			.toMatchObject({ before: 999, beforeId: 'p1' });
	});
});

describe('editTask myTasks mirror', () => {
	beforeEach(() => {
		tasks.set([]); // task lives outside the current workstream's list
		inboxTask.set(null);
	});

	it('mirrors optimistic + confirmed edits into the myTasks fallback copy', async () => {
		const { editTask } = await import('./store');
		myTasks.set([mk({ id: 'm1', title: 'old' })]);
		await editTask('m1', { title: 'new' });
		expect(get(myTasks)[0].title).toBe('new');
	});

	it('rolls the myTasks copy back when the update fails', async () => {
		const { editTask } = await import('./store');
		myTasks.set([mk({ id: 'm1', title: 'old' })]);
		vi.mocked(apiMock.updateTask).mockRejectedValueOnce({ detail: 'boom', status: 500 });
		await expect(editTask('m1', { title: 'new' })).rejects.toMatchObject({ detail: 'boom' });
		expect(get(myTasks)[0].title).toBe('old');
	});
});

// New for URL deep-linking (Task 2): openTaskById + loadBootstrap's
// selectDefaultWorkstream option. currentTeamId isn't imported above.
import { loadBootstrap, openTaskById, currentTeamId } from './store';

describe('openTaskById (URL deep-link open)', () => {
	beforeEach(() => {
		tasks.set([]);
		myTasks.set([]);
		inboxTask.set(null);
		selectedTaskId.set(null);
	});

	it('opens directly when the task is already in the workstream list', async () => {
		tasks.set([mk({ id: 'in-list' })]);
		const result = await openTaskById('in-list');
		expect(result).toBe('opened');
		expect(get(selectedTaskId)).toBe('in-list');
		expect(get(inboxTask)).toBeNull(); // no fetch fallback needed
	});

	it('falls back to a direct fetch when the task is in no local list', async () => {
		const result = await openTaskById('folded'); // mocked getTask returns id 'folded'
		expect(result).toBe('opened');
		expect(get(selectedTaskId)).toBe('folded');
		expect(get(inboxTask)?.id).toBe('folded');
	});

	it("reports 'gone' when the fetch fails, leaving selection untouched", async () => {
		const api = await import('./api');
		(api.getTask as any).mockRejectedValueOnce(Object.assign(new Error('nope'), { status: 404 }));
		const result = await openTaskById('ghost');
		expect(result).toBe('gone');
		expect(get(selectedTaskId)).toBeNull();
		expect(get(inboxTask)).toBeNull();
	});

	it("reports 'superseded' and discards a stale fetch when the selection changed while it was in flight", async () => {
		const api = await import('./api');
		let release!: (t: unknown) => void;
		const hang = new Promise((r) => { release = r; });
		(api.getTask as any).mockImplementationOnce(() => hang); // 'slow' -> fetch fallback
		const p = openTaskById('slow');
		selectedTaskId.set('user-clicked'); // user clicks a different task mid-fetch
		release(mk({ id: 'slow', title: 'Slow' }));
		const result = await p;
		expect(result).toBe('superseded'); // treated as handled, not a failure
		expect(get(selectedTaskId)).toBe('user-clicked'); // the click wins, untouched by the stale fetch
		expect(get(inboxTask)).toBeNull(); // no store write from the discarded result
	});

	it("reports 'superseded' (not 'opened') when a competing open claims the SAME id first", async () => {
		// The reviewer's inversion case: id equality with what THIS call was
		// fetching must not be read as "this call is the one that opened it" --
		// a different call can legitimately land the very same id first.
		const api = await import('./api');
		let release!: (t: unknown) => void;
		const hang = new Promise((r) => { release = r; });
		(api.getTask as any).mockImplementationOnce(() => hang); // 'tX' -> fetch fallback for call A
		const pA = openTaskById('tX');
		// A competing open (a different call/session) commits the SAME id first.
		selectedTaskId.set('tX');
		inboxTask.set(mk({ id: 'tX', title: 'Competing' }));
		release(mk({ id: 'tX', title: 'From A (stale)' }));
		const resultA = await pA;
		expect(resultA).toBe('superseded');
		expect(get(inboxTask)?.title).toBe('Competing'); // A's stale fetch never overwrote the winner
	});
});

describe('loadBootstrap selectDefaultWorkstream option', () => {
	it('skips the default workstream selection when told to', async () => {
		const api = await import('./api');
		(api.getBootstrap as any).mockResolvedValueOnce({
			teams: [{ id: 'tm', name: 'T' }],
			workspaces: [{ id: 'wsp', team_id: 'tm', name: 'W', visibility: 'team' }],
			workstreams: [{ id: 'w1', workspace_id: 'wsp', name: 'S' }],
			roles: { tm: 'member' }
		});
		currentWorkstreamId.set(null);
		await loadBootstrap({ selectDefaultWorkstream: false });
		expect(get(currentWorkstreamId)).toBeNull();
	});

	it('still auto-selects by default (regression)', async () => {
		const api = await import('./api');
		(api.getBootstrap as any).mockResolvedValueOnce({
			teams: [{ id: 'tm', name: 'T' }],
			workspaces: [{ id: 'wsp', team_id: 'tm', name: 'W', visibility: 'team' }],
			workstreams: [{ id: 'w1', workspace_id: 'wsp', name: 'S' }],
			roles: { tm: 'member' }
		});
		currentWorkstreamId.set(null);
		currentTeamId.set('tm');
		await loadBootstrap();
		expect(get(currentWorkstreamId)).toBe('w1');
	});
});
