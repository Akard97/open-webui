import { writable, derived, get, type Writable } from 'svelte/store';
import { toast } from 'svelte-sonner';
import { browser } from '$app/environment';
import { socket, user } from '$lib/stores';
import * as api from './api';
import { midpoint } from './key';
import {
	STATUS_ORDER,
	type Team, type Workspace, type Workstream, type Label, type Task, type Member,
	type TeamRole, type TaskStatus, type TaskPriority,
	type Comment, type Activity, type Attachment, type Notification, type FeedItem, type Subtask
} from './types';

export type ViewKey = 'board' | 'list' | 'admin' | 'inbox';

export type ModalRequest =
	| { kind: 'team' }
	| { kind: 'workspace'; teamId: string }
	| { kind: 'workstream'; workspaceId: string }
	| { kind: 'members'; teamId: string };
export const openModal: Writable<ModalRequest | null> = writable(null);

export const teams: Writable<Team[]> = writable([]);
export const workspaces: Writable<Workspace[]> = writable([]);
export const workstreams: Writable<Workstream[]> = writable([]);
export const roles: Writable<Record<string, TeamRole>> = writable({});
export const currentTeamId: Writable<string | null> = writable(null);
export const currentWorkstreamId: Writable<string | null> = writable(null);
export const tasks: Writable<Task[]> = writable([]);
export const labels: Writable<Label[]> = writable([]);
export const members: Writable<Member[]> = writable([]);
export const view: Writable<ViewKey> = writable('board');
export const selectedTaskId: Writable<string | null> = writable(null);
export const loading: Writable<boolean> = writable(false);
export const directory: Writable<Record<string, { name: string }>> = writable({});

export const comments: Writable<Comment[]> = writable([]);
export const activity: Writable<Activity[]> = writable([]);
export const attachments: Writable<Attachment[]> = writable([]);
export const subtasks: Writable<Subtask[]> = writable([]);
export const notifications: Writable<Notification[]> = writable([]);
export const unreadCount: Writable<number> = writable(0);

export const feed = derived([comments, activity], ([$c, $a]): FeedItem[] => {
	const items: FeedItem[] = [
		...$c.map((comment) => ({ kind: 'comment' as const, at: comment.created_at, comment })),
		...$a.map((act) => ({ kind: 'activity' as const, at: act.created_at, activity: act }))
	];
	return items.sort((x, y) => x.at - y.at);
});

export function displayName(id: string | null | undefined): string {
	if (!id) return 'Unassigned';
	return get(directory)[id]?.name ?? id;
}
export function initials(id: string | null | undefined): string {
	const n = displayName(id);
	return n === 'Unassigned' ? '–' : n.split(' ').map((p) => p[0]).slice(0, 2).join('').toUpperCase();
}

export const currentTeam = derived([teams, currentTeamId], ([$t, $id]) => $t.find((x) => x.id === $id) ?? null);
export const currentWorkstream = derived(
	[workstreams, currentWorkstreamId],
	([$s, $id]) => $s.find((x) => x.id === $id) ?? null
);
export const selectedTask = derived(
	[tasks, selectedTaskId],
	([$t, $id]) => $t.find((x) => x.id === $id) ?? null
);
export const tasksByStatus = derived(tasks, ($tasks) => {
	const out: Record<TaskStatus, Task[]> = {
		backlog: [], todo: [], in_progress: [], in_review: [], done: [], canceled: []
	};
	for (const t of [...$tasks].sort((a, b) => a.sort_key - b.sort_key)) out[t.status]?.push(t);
	return out;
});

export function token(): string {
	return browser ? localStorage.token : '';
}

export async function loadBootstrap(): Promise<void> {
	loading.set(true);
	try {
		const b = await api.getBootstrap(token());
		teams.set(b.teams);
		workspaces.set(b.workspaces);
		workstreams.set(b.workstreams);
		roles.set(b.roles);
		unreadCount.set(b.notifications_unread ?? 0);
		const dir = await api.getDirectory(token()).catch(() => []);
		directory.set(Object.fromEntries(dir.map((u) => [u.id, { name: u.name }])));
		if (!get(currentTeamId) && b.teams.length) currentTeamId.set(b.teams[0].id);
		const team = get(currentTeam);
		if (team) labels.set(await api.listLabels(token(), team.id).catch(() => []));
		const firstStream = b.workstreams.find((s) => {
			const ws = b.workspaces.find((w) => w.id === s.workspace_id);
			return ws && ws.team_id === get(currentTeamId);
		});
		if (firstStream && !get(currentWorkstreamId)) await selectWorkstream(firstStream.id);
	} finally {
		loading.set(false);
	}
}

export async function selectTeam(id: string): Promise<void> {
	currentTeamId.set(id);
	currentWorkstreamId.set(null);
	tasks.set([]);
	labels.set(await api.listLabels(token(), id).catch(() => []));
}

export async function selectWorkstream(id: string): Promise<void> {
	const prev = get(currentWorkstreamId);
	if (prev && prev !== id) unsubscribeRoom(prev);
	currentWorkstreamId.set(id);
	selectedTaskId.set(null);
	tasks.set(await api.listTasks(token(), id).catch(() => []));
	subscribeRoom(id);
}

export function openTask(id: string): void {
	selectedTaskId.set(id);
	void loadTaskDetail(id);
}
export function closeTask(): void {
	selectedTaskId.set(null);
	comments.set([]);
	activity.set([]);
	attachments.set([]);
	subtasks.set([]);
}

export async function addTask(
	workstreamId: string,
	fields: { title: string; status?: TaskStatus; priority?: TaskPriority | null; assignee_id?: string | null }
): Promise<void> {
	const tempId = `temp-${Date.now()}-${Math.round(performance.now())}`;
	const optimistic: Task = {
		id: tempId, workstream_id: workstreamId, team_id: get(currentTeam)?.id ?? '', number: 0, key: '…',
		title: fields.title, status: fields.status ?? 'backlog', priority: fields.priority ?? null,
		assignee_id: fields.assignee_id ?? null, due_date: null, progress: 0, labels: [],
		sort_key: Date.now(), created_by_id: get(user)?.id ?? null, completed_at: null,
		created_at: Date.now(), updated_at: Date.now()
	};
	tasks.update((list) => [...list, optimistic]);
	try {
		const saved = await api.createTask(token(), workstreamId, fields);
		tasks.update((list) => list.map((t) => (t.id === tempId ? saved : t)));
	} catch (e) {
		tasks.update((list) => list.filter((t) => t.id !== tempId)); // rollback
		throw e;
	}
}

export async function editTask(id: string, fields: Partial<Task>): Promise<void> {
	const before = get(tasks).find((t) => t.id === id);
	tasks.update((list) => list.map((t) => (t.id === id ? { ...t, ...fields } : t)));
	try {
		const saved = await api.updateTask(token(), id, fields as any);
		tasks.update((list) => list.map((t) => (t.id === id ? saved : t)));
	} catch (e) {
		if (before) tasks.update((list) => list.map((t) => (t.id === id ? before : t)));
		throw e;
	}
}

export async function moveTask(
	id: string, status: TaskStatus, beforeKey: number | null, afterKey: number | null
): Promise<void> {
	const sort_key = midpoint(beforeKey, afterKey);
	await editTask(id, { status, sort_key });
}

export async function removeTask(id: string): Promise<void> {
	const before = get(tasks);
	tasks.update((list) => list.filter((t) => t.id !== id));
	if (get(selectedTaskId) === id) selectedTaskId.set(null);
	try {
		await api.deleteTask(token(), id);
	} catch (e) {
		tasks.set(before); // rollback
		throw e;
	}
}

export async function loadTaskDetail(taskId: string): Promise<void> {
	const [c, a, at, st] = await Promise.all([
		api.listComments(token(), taskId).catch(() => []),
		api.listActivity(token(), taskId).catch(() => []),
		api.listAttachments(token(), taskId).catch(() => []),
		api.listSubtasks(token(), taskId).catch(() => [])
	]);
	if (get(selectedTaskId) !== taskId) return; // user moved on
	comments.set(c);
	activity.set(a);
	attachments.set(at);
	subtasks.set(st);
}

export async function postComment(taskId: string, body: string): Promise<void> {
	const saved = await api.createComment(token(), taskId, { body });
	comments.update((list) => (list.some((c) => c.id === saved.id) ? list : [...list, saved]));
	void loadTaskDetail(taskId); // refresh activity (comment_added) too
}

export async function editComment(id: string, body: string): Promise<void> {
	const saved = await api.updateComment(token(), id, { body });
	comments.update((list) => list.map((c) => (c.id === id ? saved : c)));
}

export async function deleteCommentAction(id: string): Promise<void> {
	comments.update((list) => list.filter((c) => c.id !== id));
	await api.deleteComment(token(), id);
}

export async function uploadFiles(taskId: string, files: FileList | File[], commentId?: string): Promise<void> {
	for (const f of Array.from(files)) {
		try {
			const saved = await api.uploadAttachment(token(), taskId, f, commentId);
			attachments.update((list) => [...list, saved]);
		} catch (e: any) {
			const detail = typeof e === 'string' ? e : (e?.detail ?? 'Upload failed');
			toast.error(`Couldn't upload "${f.name}": ${detail}`);
			console.error('[workos] attachment upload failed', e);
		}
	}
	void loadTaskDetail(taskId);
}

export async function removeAttachment(id: string): Promise<void> {
	attachments.update((list) => list.filter((a) => a.id !== id));
	await api.deleteAttachment(token(), id);
}

export async function addSubtask(taskId: string, title: string): Promise<void> {
	const saved = await api.createSubtask(token(), taskId, { title });
	subtasks.update((list) => (list.some((s) => s.id === saved.id) ? list : [...list, saved]));
	const refreshed = await api.getTask(token(), taskId).catch(() => null);
	if (refreshed) tasks.update((list) => list.map((t) => (t.id === taskId ? refreshed : t)));
}

export async function editSubtask(id: string, fields: Partial<Pick<Subtask, 'title' | 'completed' | 'sort_key'>>): Promise<void> {
	const before = get(subtasks);
	subtasks.update((list) => list.map((s) => (s.id === id ? { ...s, ...fields } : s)));
	try {
		const saved = await api.updateSubtask(token(), id, fields);
		subtasks.update((list) => list.map((s) => (s.id === id ? saved : s)));
		const refreshed = await api.getTask(token(), saved.task_id).catch(() => null);
		if (refreshed) tasks.update((list) => list.map((t) => (t.id === saved.task_id ? refreshed : t)));
	} catch (e) {
		subtasks.set(before);
		throw e;
	}
}

export async function removeSubtask(id: string): Promise<void> {
	const existing = get(subtasks).find((s) => s.id === id);
	const before = get(subtasks);
	subtasks.update((list) => list.filter((s) => s.id !== id));
	try {
		await api.deleteSubtask(token(), id);
		if (existing) {
			const refreshed = await api.getTask(token(), existing.task_id).catch(() => null);
			if (refreshed) tasks.update((list) => list.map((t) => (t.id === existing.task_id ? refreshed : t)));
		}
	} catch (e) {
		subtasks.set(before);
		throw e;
	}
}

export async function loadNotifications(): Promise<void> {
	notifications.set(await api.listNotifications(token()).catch(() => []));
}

export async function markRead(ids: string[]): Promise<void> {
	notifications.update((list) => list.map((n) => (ids.includes(n.id) ? { ...n, read: true } : n)));
	const r = await api.markNotificationsRead(token(), { ids });
	unreadCount.set(r.unread);
}

export async function markAllRead(): Promise<void> {
	notifications.update((list) => list.map((n) => ({ ...n, read: true })));
	const r = await api.markNotificationsRead(token(), { all: true });
	unreadCount.set(r.unread);
}

/** Reconcile a collaboration room event into the open task's feed. */
export function applyCollabEvent(event: string, payload: any): void {
	const open = get(selectedTaskId);
	if (!payload || payload.task_id !== open) return;
	if (event === 'workos:comment.created') {
		comments.update((l) => (l.some((c) => c.id === payload.id) ? l : [...l, payload]));
	} else if (event === 'workos:comment.updated') {
		comments.update((l) => l.map((c) => (c.id === payload.id ? { ...c, ...payload } : c)));
	} else if (event === 'workos:comment.deleted') {
		comments.update((l) => l.filter((c) => c.id !== payload.id));
	} else if (event === 'workos:activity.created') {
		activity.update((l) => (l.some((a) => a.id === payload.id) ? l : [...l, payload]));
	} else if (event === 'workos:attachment.created') {
		attachments.update((l) => (l.some((a) => a.id === payload.id) ? l : [...l, payload]));
	} else if (event === 'workos:attachment.deleted') {
		attachments.update((l) => l.filter((a) => a.id !== payload.id));
	} else if (event === 'workos:subtask.created') {
		subtasks.update((l) => (l.some((s) => s.id === payload.id) ? l : [...l, payload]));
	} else if (event === 'workos:subtask.updated') {
		subtasks.update((l) => l.map((s) => (s.id === payload.id ? { ...s, ...payload } : s)));
	} else if (event === 'workos:subtask.deleted') {
		subtasks.update((l) => l.filter((s) => s.id !== payload.id));
	}
}

export function applyNotificationEvent(payload: any): void {
	if (!payload || !payload.id) return;
	notifications.update((l) => (l.some((n) => n.id === payload.id) ? l : [payload, ...l]));
	if (!payload.read) unreadCount.update((n) => n + 1);
}

/** Reconcile a realtime event into local state. Exported for tests + the socket wiring. */
export function applyTaskEvent(event: string, payload: any): void {
	const ws = get(currentWorkstreamId);
	if (!payload || payload.workstream_id !== ws) return;
	if (event === 'workos:task.created') {
		tasks.update((list) => (list.some((t) => t.id === payload.id) ? list : [...list, payload]));
	} else if (event === 'workos:task.updated') {
		tasks.update((list) => list.map((t) => (t.id === payload.id ? payload : t)));
	} else if (event === 'workos:task.deleted') {
		tasks.update((list) => list.filter((t) => t.id !== payload.id));
		if (get(selectedTaskId) === payload.id) selectedTaskId.set(null);
	}
}

// ──────────────────────────── socket wiring ────────────────────────────

const TASK_EVENTS = ['workos:task.created', 'workos:task.updated', 'workos:task.deleted'];
const COLLAB_EVENTS = [
	'workos:comment.created', 'workos:comment.updated', 'workos:comment.deleted',
	'workos:activity.created', 'workos:attachment.created', 'workos:attachment.deleted',
	'workos:subtask.created', 'workos:subtask.updated', 'workos:subtask.deleted'
];

function subscribeRoom(workstreamId: string): void {
	const s = get(socket);
	if (!s || !browser) return;
	s.emit('workos:subscribe', { auth: { token: token() }, workstream_id: workstreamId });
}

function unsubscribeRoom(workstreamId: string): void {
	const s = get(socket);
	if (!s || !browser) return;
	s.emit('workos:unsubscribe', { workstream_id: workstreamId });
}

let bound = false;
const handlers: Record<string, (...args: any[]) => void> = {};

export function connectRealtime(): void {
	const s = get(socket);
	if (!s || bound) return;
	for (const ev of TASK_EVENTS) {
		handlers[ev] = (payload: any) => applyTaskEvent(ev, payload);
		s.on(ev, handlers[ev]);
	}
	for (const ev of COLLAB_EVENTS) {
		handlers[ev] = (payload: any) => applyCollabEvent(ev, payload);
		s.on(ev, handlers[ev]);
	}
	handlers['workos:notification.created'] = (payload: any) => applyNotificationEvent(payload);
	s.on('workos:notification.created', handlers['workos:notification.created']);
	// Re-subscribe on reconnect so the room is rejoined.
	handlers['connect'] = () => {
		const ws = get(currentWorkstreamId);
		if (ws) subscribeRoom(ws);
	};
	s.on('connect', handlers['connect']);
	bound = true;
	const ws = get(currentWorkstreamId);
	if (ws) subscribeRoom(ws);
}

export function disconnectRealtime(): void {
	const s = get(socket);
	if (!s) {
		bound = false;
		return;
	}
	for (const ev of [...TASK_EVENTS, ...COLLAB_EVENTS, 'workos:notification.created', 'connect']) {
		if (handlers[ev]) s.off(ev, handlers[ev]);
	}
	const ws = get(currentWorkstreamId);
	if (ws) unsubscribeRoom(ws);
	bound = false;
}
