import { writable, derived, get, type Writable } from 'svelte/store';
import { toast } from 'svelte-sonner';
import { browser } from '$app/environment';
import { socket, user } from '$lib/stores';
import * as api from './api';
import { midpoint } from './key';
import { RoomRefs } from './rooms';
import {
	STATUS_ORDER,
	type Team, type Workspace, type Workstream, type Label, type Task, type Member,
	type TeamRole, type TaskStatus, type TaskPriority,
	type Comment, type Activity, type Attachment, type Notification, type FeedItem, type Subtask,
	type TaskFilter
} from './types';
import { applyFilters, emptyFilter } from './filters';
import { defaultColumnPrefs, parseColumnPrefs, type ColumnPrefs } from './columns';

export type ViewKey = 'board' | 'list' | 'admin' | 'inbox' | 'mywork' | 'calendar' | 'overview';

export type ModalRequest =
	| { kind: 'team' }
	| { kind: 'workspace'; teamId: string }
	| { kind: 'workstream'; workspaceId: string }
	| { kind: 'team-settings'; teamId: string }
	| { kind: 'workspace-settings'; workspaceId: string };
export const openModal: Writable<ModalRequest | null> = writable(null);

export const teams: Writable<Team[]> = writable([]);
export const workspaces: Writable<Workspace[]> = writable([]);
export const workstreams: Writable<Workstream[]> = writable([]);
export const roles: Writable<Record<string, TeamRole>> = writable({});

// Selected team, persisted per browser so a reload returns to the same team.
const CURRENT_TEAM_KEY = 'workos:current-team';
export const currentTeamId: Writable<string | null> = writable(browser ? localStorage.getItem(CURRENT_TEAM_KEY) : null);
if (browser) currentTeamId.subscribe((v) => {
	if (v) localStorage.setItem(CURRENT_TEAM_KEY, v);
	else localStorage.removeItem(CURRENT_TEAM_KEY);
});

export const currentWorkstreamId: Writable<string | null> = writable(null);
export const tasks: Writable<Task[]> = writable([]);
export const labels: Writable<Label[]> = writable([]);
export const members: Writable<Member[]> = writable([]);
export const view: Writable<ViewKey> = writable('mywork');
export const boardFilter: Writable<TaskFilter> = writable(emptyFilter());
export const myWorkFilter: Writable<TaskFilter> = writable(emptyFilter());
export const selectedTaskId: Writable<string | null> = writable(null);
export const loading: Writable<boolean> = writable(false);
export const directory: Writable<Record<string, { name: string }>> = writable({});

// Sidebar collapse, persisted like OWUI's own sidebar flag.
const NAV_COLLAPSED_KEY = 'workos:nav-collapsed';
export const navCollapsed: Writable<boolean> = writable(browser && localStorage.getItem(NAV_COLLAPSED_KEY) === '1');
if (browser) navCollapsed.subscribe((v) => localStorage.setItem(NAV_COLLAPSED_KEY, v ? '1' : '0'));

// Mobile Browse drawer (bottom-nav → workstream tree). Ephemeral by design.
export const mobileNavOpen: Writable<boolean> = writable(false);

// Which sidebar workspaces are expanded, persisted per browser so the tree
// keeps its open/closed shape across reloads.
const EXPANDED_WS_KEY = 'workos:expanded-workspaces';
function readExpandedWorkspaces(): Record<string, boolean> {
	if (!browser) return {};
	try {
		const parsed = JSON.parse(localStorage.getItem(EXPANDED_WS_KEY) ?? '{}');
		return parsed && typeof parsed === 'object' ? parsed : {};
	} catch {
		return {};
	}
}
export const expandedWorkspaces: Writable<Record<string, boolean>> = writable(readExpandedWorkspaces());
if (browser) expandedWorkspaces.subscribe((v) => localStorage.setItem(EXPANDED_WS_KEY, JSON.stringify(v)));

// List column visibility, persisted per browser like the sidebar flag.
const LIST_COLUMNS_KEY = 'workos:list-columns';
export const listColumns: Writable<ColumnPrefs> = writable(
	browser ? parseColumnPrefs(localStorage.getItem(LIST_COLUMNS_KEY)) : defaultColumnPrefs()
);
if (browser) listColumns.subscribe((v) => localStorage.setItem(LIST_COLUMNS_KEY, JSON.stringify(v)));

export const comments: Writable<Comment[]> = writable([]);
export const activity: Writable<Activity[]> = writable([]);
export const attachments: Writable<Attachment[]> = writable([]);
export const subtasks: Writable<Subtask[]> = writable([]);
export const myTasks: Writable<Task[]> = writable([]);
let myWorkActive = false;
const myWorkRooms = new Set<string>();
export const notifications: Writable<Notification[]> = writable([]);
export const unreadCount: Writable<number> = writable(0);

export interface WsActivityItem extends Activity { task_key?: string; task_title?: string; workstream_id?: string }
export interface WsActivityState {
	items: WsActivityItem[]; daily: { day: string; n: number }[]; loaded: boolean; error: boolean;
}
export const wsActivity: Writable<WsActivityState> = writable({ items: [], daily: [], loaded: false, error: false });

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
	// Falls back to myTasks so opening a task from My Work (whose tasks aren't in the
	// current workstream's `tasks` store) still resolves and renders the detail drawer.
	[tasks, myTasks, selectedTaskId],
	([$t, $my, $id]) => $t.find((x) => x.id === $id) ?? $my.find((x) => x.id === $id) ?? null
);
export const tasksByStatus = derived([tasks, boardFilter], ([$tasks, $filter]) => {
	const out: Record<TaskStatus, Task[]> = {
		backlog: [], todo: [], in_progress: [], in_review: [], done: [], canceled: []
	};
	for (const t of applyFilters([...$tasks].sort((a, b) => a.sort_key - b.sort_key), $filter)) out[t.status]?.push(t);
	return out;
});

// Flat, filtered task list — the single source for the calendar grid + rail.
// Mirrors tasksByStatus' filtering (same applyFilters predicate), ungrouped.
export const filteredTasks = derived([tasks, boardFilter], ([$tasks, $filter]) =>
	applyFilters($tasks, $filter)
);

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
		const savedTeam = get(currentTeamId);
		if ((!savedTeam || !b.teams.some((t) => t.id === savedTeam)) && b.teams.length) {
			currentTeamId.set(b.teams[0].id);
		}
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

// Refresh just the team-scoped directory (assignee picker source) — e.g. after
// team membership changes, so newly added members become assignable immediately.
export async function reloadDirectory(): Promise<void> {
	const dir = await api.getDirectory(token()).catch(() => []);
	directory.set(Object.fromEntries(dir.map((u) => [u.id, { name: u.name }])));
}

export async function selectTeam(id: string): Promise<void> {
	currentTeamId.set(id);
	currentWorkstreamId.set(null);
	tasks.set([]);
	labels.set(await api.listLabels(token(), id).catch(() => []));
}

// Rotating palette so freshly created tags don't all share one color.
const LABEL_PALETTE = ['#00a5ba', '#769a4a', '#d97706', '#dc2626', '#7c3aed', '#0ea5e9', '#db2777', '#ca8a04'];

export async function createLabel(name: string): Promise<Label | null> {
	const team = get(currentTeam);
	const trimmed = name.trim();
	if (!team || !trimmed) return null;
	const color = LABEL_PALETTE[get(labels).length % LABEL_PALETTE.length];
	try {
		const created = await api.createLabel(token(), team.id, { name: trimmed, color });
		labels.update((ls) => [...ls, created]);
		return created;
	} catch {
		toast.error('Failed to create tag');
		return null;
	}
}

export async function selectWorkstream(id: string): Promise<void> {
	const prev = get(currentWorkstreamId);
	if (prev && prev !== id) leaveRoom(streamKey(prev));
	currentWorkstreamId.set(id);
	selectedTaskId.set(null);
	tasks.set(await api.listTasks(token(), id).catch(() => []));
	enterRoom(streamKey(id));
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
	fields: {
		title: string; status?: TaskStatus; priority?: TaskPriority | null;
		assignee_ids?: string[]; start_date?: number | null; due_date?: number | null;
	}
): Promise<void> {
	const tempId = `temp-${Date.now()}-${Math.round(performance.now())}`;
	const optimistic: Task = {
		id: tempId, workstream_id: workstreamId, team_id: get(currentTeam)?.id ?? '', number: 0, key: '…',
		title: fields.title, status: fields.status ?? 'backlog', priority: fields.priority ?? null,
		assignee_ids: fields.assignee_ids ?? [], start_date: fields.start_date ?? null,
		due_date: fields.due_date ?? null, progress: 0, labels: [],
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
		const { deleted_label_ids, ...task } = saved;
		dropLabels(deleted_label_ids);
		tasks.update((list) => list.map((t) => (t.id === id ? (task as Task) : t)));
	} catch (e) {
		if (before) tasks.update((list) => list.map((t) => (t.id === id ? before : t)));
		throw e;
	}
}

// Drop tags the server auto-deleted (orphaned by an unassign or task delete) from the picker.
function dropLabels(ids: string[] | undefined): void {
	if (!ids?.length) return;
	const gone = new Set(ids);
	labels.update((ls) => ls.filter((l) => !gone.has(l.id)));
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
		const res = await api.deleteTask(token(), id);
		dropLabels(res.deleted_label_ids);
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

export async function loadWorkstreamActivity(id: string): Promise<void> {
	wsActivity.set({ items: [], daily: [], loaded: false, error: false });
	try {
		const r = await api.getWorkstreamActivity(token(), id);
		if (get(currentWorkstreamId) !== id) return; // user moved on
		wsActivity.set({ items: r.items, daily: r.daily, loaded: true, error: false });
	} catch {
		if (get(currentWorkstreamId) !== id) return; // user moved on
		wsActivity.set({ items: [], daily: [], loaded: true, error: true });
	}
}

function localDayKey(now: number): string {
	const d = new Date(now);
	const p = (n: number) => String(n).padStart(2, '0');
	return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

/** Fold a workstream-room activity event into the Overview pulse + today's histogram
 * bucket. task_key/title fall back to the tasks store (realtime payloads lack them). */
export function applyOverviewActivityEvent(payload: any): void {
	if (!payload || !payload.id || payload.workstream_id !== get(currentWorkstreamId)) return;
	const t = get(tasks).find((x) => x.id === payload.task_id);
	const item: WsActivityItem = {
		...payload,
		task_key: payload.task_key ?? t?.key,
		task_title: payload.task_title ?? t?.title
	};
	const todayKey = localDayKey(Date.now());
	wsActivity.update((s) => {
		if (s.items.some((a) => a.id === item.id)) return s; // duplicate → no-op
		return {
			...s,
			items: [item, ...s.items].slice(0, 30),
			daily: s.daily.map((d) => (d.day === todayKey ? { ...d, n: d.n + 1 } : d))
		};
	});
}

export async function loadMyWork(): Promise<void> {
	myWorkActive = true;
	const mine = await api.listMyTasks(token()).catch(() => []);
	myTasks.set(mine);
	for (const id of new Set(mine.map((t) => t.workstream_id))) {
		const key = streamKey(id);
		myWorkRooms.add(key);
		enterRoom(key);
	}
}

export function teardownMyWork(): void {
	myWorkActive = false;
	for (const key of myWorkRooms) leaveRoom(key);
	myWorkRooms.clear();
}

/** Reconcile a task realtime event into the cross-team My Work list. */
export function applyMyWorkTaskEvent(event: string, payload: any, uid: string): void {
	if (!payload || !payload.id) return;
	if (event === 'workos:task.deleted') {
		myTasks.update((l) => l.filter((t) => t.id !== payload.id));
		return;
	}
	const mine = payload.created_by_id === uid || (payload.assignee_ids ?? []).includes(uid);
	myTasks.update((l) => {
		const exists = l.some((t) => t.id === payload.id);
		if (mine) return exists ? l.map((t) => (t.id === payload.id ? payload : t)) : [...l, payload];
		return exists ? l.filter((t) => t.id !== payload.id) : l;
	});
}

/** A new assigned/mentioned notification may reference a task in a workstream My Work
 * has not subscribed to yet — pull it in and join its room. */
export async function foldInMyWorkFromNotification(payload: any): Promise<void> {
	if (!myWorkActive || !payload || (payload.type !== 'assigned' && payload.type !== 'mentioned')) return;
	const taskId = payload.task_id;
	if (!taskId || get(myTasks).some((t) => t.id === taskId)) return;
	const t = await api.getTask(token(), taskId).catch(() => null);
	if (!t) return;
	myTasks.update((l) => (l.some((x) => x.id === t.id) ? l : [...l, t]));
	const key = streamKey(t.workstream_id);
	myWorkRooms.add(key);
	enterRoom(key);
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

export async function openNotification(n: Notification): Promise<void> {
	if (!n.read) await markRead([n.id]);
	if (n.data?.workstream_id) await selectWorkstream(n.data.workstream_id);
	if (n.task_id) openTask(n.task_id);
	view.set('board');
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

/** Reconcile a workspace/workstream nav event into the sidebar tree.
 * The server routes restricted-workspace events to authorized sockets only
 * (member user rooms), so restricted payloads are applied like team ones —
 * including add-if-absent, which the team→restricted flip flow relies on.
 * Workstreams are still only accepted when their parent workspace is visible. */
export function applyNavEvent(event: string, payload: any): void {
	if (!payload || !payload.id) return;
	if (event === 'workos:workspace.created' || event === 'workos:workspace.updated') {
		workspaces.update((l) => {
			const exists = l.some((w) => w.id === payload.id);
			return exists ? l.map((w) => (w.id === payload.id ? payload : w)) : [...l, payload];
		});
	} else if (event === 'workos:workspace.deleted') {
		workspaces.update((l) => l.filter((w) => w.id !== payload.id));
		workstreams.update((l) => l.filter((s) => s.workspace_id !== payload.id));
	} else if (event === 'workos:workstream.created' || event === 'workos:workstream.updated') {
		workstreams.update((l) => {
			if (!get(workspaces).some((w) => w.id === payload.workspace_id)) return l;
			const exists = l.some((s) => s.id === payload.id);
			return exists ? l.map((s) => (s.id === payload.id ? payload : s)) : [...l, payload];
		});
	} else if (event === 'workos:workstream.deleted') {
		workstreams.update((l) => l.filter((s) => s.id !== payload.id));
	}
}

// ──────────────────────────── socket wiring ────────────────────────────

const TASK_EVENTS = ['workos:task.created', 'workos:task.updated', 'workos:task.deleted'];
const NAV_EVENTS = [
	'workos:workspace.created', 'workos:workspace.updated', 'workos:workspace.deleted',
	'workos:workstream.created', 'workos:workstream.updated', 'workos:workstream.deleted'
];
const COLLAB_EVENTS = [
	'workos:comment.created', 'workos:comment.updated', 'workos:comment.deleted',
	'workos:activity.created', 'workos:attachment.created', 'workos:attachment.deleted',
	'workos:subtask.created', 'workos:subtask.updated', 'workos:subtask.deleted'
];

function streamKey(id: string): string { return `stream:${id}`; }
function teamKey(id: string): string { return `team:${id}`; }

function emitSub(key: string): void {
	const s = get(socket);
	if (!s || !browser) return;
	const [kind, id] = [key.slice(0, key.indexOf(':')), key.slice(key.indexOf(':') + 1)];
	// No token in the payload — the server authorizes the join from the
	// connection's established session identity.
	if (kind === 'team') s.emit('workos:subscribe', { team_id: id });
	else s.emit('workos:subscribe', { workstream_id: id });
}
function emitUnsub(key: string): void {
	const s = get(socket);
	if (!s || !browser) return;
	const [kind, id] = [key.slice(0, key.indexOf(':')), key.slice(key.indexOf(':') + 1)];
	if (kind === 'team') s.emit('workos:unsubscribe', { team_id: id });
	else s.emit('workos:unsubscribe', { workstream_id: id });
}

const rooms = new RoomRefs(emitSub, emitUnsub);
export function enterRoom(key: string): void { rooms.enter(key); }
export function leaveRoom(key: string): void { rooms.leave(key); }

let bound = false;
const handlers: Record<string, (...args: any[]) => void> = {};

export function connectRealtime(): void {
	const s = get(socket);
	if (!s || bound) return;
	for (const ev of TASK_EVENTS) {
		handlers[ev] = (payload: any) => {
			applyTaskEvent(ev, payload);
			if (myWorkActive) applyMyWorkTaskEvent(ev, payload, get(user)?.id ?? '');
		};
		s.on(ev, handlers[ev]);
	}
	for (const ev of COLLAB_EVENTS) {
		handlers[ev] = (payload: any) => {
			applyCollabEvent(ev, payload);
			if (ev === 'workos:activity.created') applyOverviewActivityEvent(payload);
		};
		s.on(ev, handlers[ev]);
	}
	for (const ev of NAV_EVENTS) {
		handlers[ev] = (payload: any) => applyNavEvent(ev, payload);
		s.on(ev, handlers[ev]);
	}
	// Subscribe to every team room so workspace/workstream nav events arrive live.
	for (const t of get(teams)) enterRoom(teamKey(t.id));
	handlers['workos:notification.created'] = (payload: any) => {
		applyNotificationEvent(payload);
		void foldInMyWorkFromNotification(payload);
	};
	s.on('workos:notification.created', handlers['workos:notification.created']);
	// Re-subscribe every held room on reconnect.
	handlers['connect'] = () => {
		for (const key of rooms.keys()) emitSub(key);
	};
	s.on('connect', handlers['connect']);
	bound = true;
}

export function disconnectRealtime(): void {
	const s = get(socket);
	if (!s) {
		bound = false;
		return;
	}
	for (const ev of [...TASK_EVENTS, ...COLLAB_EVENTS, ...NAV_EVENTS, 'workos:notification.created', 'connect']) {
		if (handlers[ev]) s.off(ev, handlers[ev]);
	}
	for (const key of rooms.keys()) emitUnsub(key);
	rooms.clear();
	myWorkRooms.clear();
	myWorkActive = false;
	bound = false;
}
