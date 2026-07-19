import { writable, derived, readable, get, type Writable, type Readable } from 'svelte/store';
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
	type Comment, type Activity, type Attachment, type Notification, type NotificationCounts,
	type FeedItem, type Subtask,
	type TaskFilter, type WorkstreamFile
} from './types';
import { applyFilters, emptyFilter } from './filters';
import { defaultColumnPrefs, parseColumnPrefs, type ColumnPrefs } from './columns';
import { parseZoom, type ZoomKey } from './timeline';
import { LABEL_PALETTE } from './avatar';

export type ViewKey = 'board' | 'list' | 'admin' | 'inbox' | 'mywork' | 'calendar' | 'overview' | 'timeline' | 'files';

export type ModalRequest =
	| { kind: 'team' }
	| { kind: 'workspace'; teamId: string }
	| { kind: 'workstream'; workspaceId: string }
	| { kind: 'team-settings'; teamId: string }
	| { kind: 'workspace-settings'; workspaceId: string }
	| { kind: 'task'; workstreamId: string; prefill?: { status?: TaskStatus; start_date?: number | null; due_date?: number | null } };
export const openModal: Writable<ModalRequest | null> = writable(null);

export function openTaskCreate(
	workstreamId: string,
	prefill?: { status?: TaskStatus; start_date?: number | null; due_date?: number | null }
): void {
	openModal.set({ kind: 'task', workstreamId, ...(prefill ? { prefill } : {}) });
}

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

// Timeline zoom preset, persisted per browser like the list columns.
const TIMELINE_ZOOM_KEY = 'workos:timeline-zoom';
export const timelineZoom: Writable<ZoomKey> = writable(
	browser ? parseZoom(localStorage.getItem(TIMELINE_ZOOM_KEY)) : 'day'
);
if (browser) timelineZoom.subscribe((v) => localStorage.setItem(TIMELINE_ZOOM_KEY, v));

export const comments: Writable<Comment[]> = writable([]);
export const activity: Writable<Activity[]> = writable([]);
export const attachments: Writable<Attachment[]> = writable([]);
export const subtasks: Writable<Subtask[]> = writable([]);
export const myTasks: Writable<Task[]> = writable([]);
let myWorkActive = false;
const myWorkRooms = new Set<string>();
export const notifications: Writable<Notification[]> = writable([]);
export const unreadCount: Writable<number> = writable(0);

const EMPTY_COUNTS = (): NotificationCounts => ({
	unread: 0, by_type: { assigned: 0, mentioned: 0, commented: 0, status_changed: 0 }
});
export const notificationCounts: Writable<NotificationCounts> = writable(EMPTY_COUNTS());
export const archivedNotifications: Writable<Notification[]> = writable([]);
export const notificationsHasMore: Writable<boolean> = writable(false);
export const archivedHasMore: Writable<boolean> = writable(false);
const NOTIF_PAGE = 50;
// Split-pane inbox: the opened notification's task may be in neither `tasks` nor
// `myTasks`, so it is fetched into this third `selectedTask` fallback.
export const inboxTask: Writable<Task | null> = writable(null);
// "Gone" (404/403 — deleted or access revoked): permanent, the pane shows
// "Task no longer available".
export const inboxTaskError: Writable<boolean> = writable(false);
// Transient load failure (network/5xx): the task still exists — retryable,
// must never present as loss.
export const inboxTaskLoadError: Writable<boolean> = writable(false);
// Comment to scroll-to + highlight in the detail pane (mentioned/commented opens).
export const highlightCommentId: Writable<string | null> = writable(null);
// Workstream room joined for the split-pane task (ref-counted, so overlap with
// the current-workstream / my-work rooms is safe). Left again on closeTask.
let inboxRoomKey: string | null = null;
// Monotonic open counter — a stale openInboxNotification resolution must not
// clobber a newer selection (rapid A→B clicks).
let inboxOpenSeq = 0;
// Split-pane gate: the 256px sidebar + 400px list leave a usable detail pane
// only at ≥1280px viewports; below that the inbox keeps the dialog flow.
export const inboxSplit: Readable<boolean> = readable(false, (set) => {
	if (!browser) return;
	const mq = window.matchMedia('(min-width: 1280px)');
	const update = () => set(mq.matches);
	update();
	mq.addEventListener('change', update);
	return () => mq.removeEventListener('change', update);
});

export interface WsActivityItem extends Activity { task_key?: string; task_title?: string; workstream_id?: string }
export interface WsActivityState {
	items: WsActivityItem[]; daily: { day: string; n: number }[]; loaded: boolean; error: boolean;
}
export const wsActivity: Writable<WsActivityState> = writable({ items: [], daily: [], loaded: false, error: false });

export interface WsFilesState {
	items: WorkstreamFile[];
	loaded: boolean;
	error: boolean;
}
export const wsFiles: Writable<WsFilesState> = writable({ items: [], loaded: false, error: false });

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
	// inboxTask FIRST: it is freshly fetched and realtime-reconciled, while
	// `myTasks` can be stale (it persists after leaving My Work and only
	// reconciles while My Work is active) — a stale copy must not shadow it.
	// Then the current workstream's live `tasks`; `myTasks` is the last resort.
	[tasks, myTasks, inboxTask, selectedTaskId],
	([$t, $my, $inbox, $id]) =>
		($inbox && $inbox.id === $id ? $inbox : null) ??
		$t.find((x) => x.id === $id) ??
		$my.find((x) => x.id === $id) ??
		null
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

export async function loadBootstrap(opts: { selectDefaultWorkstream?: boolean } = {}): Promise<void> {
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
		// URL deep links (urlSync.hydrateFromUrl) perform their own selection;
		// skipping the default here keeps it to exactly one selectWorkstream
		// call per load (spec: bootstrap default-selection interplay).
		if (opts.selectDefaultWorkstream !== false && firstStream && !get(currentWorkstreamId))
			await selectWorkstream(firstStream.id);
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
	inboxTask.set(null);
	inboxTaskError.set(false);
	inboxTaskLoadError.set(false);
	highlightCommentId.set(null);
	if (inboxRoomKey) {
		leaveRoom(inboxRoomKey);
		inboxRoomKey = null;
	}
}

export async function addTask(
	workstreamId: string,
	fields: {
		title: string; description?: string; status?: TaskStatus; priority?: TaskPriority | null;
		assignee_ids?: string[]; start_date?: number | null; due_date?: number | null;
		labels?: string[]; attachment_required?: boolean;
	}
): Promise<void> {
	const tempId = `temp-${Date.now()}-${Math.round(performance.now())}`;
	const optimistic: Task = {
		id: tempId, workstream_id: workstreamId, team_id: get(currentTeam)?.id ?? '', number: 0, key: '…',
		title: fields.title, description: fields.description ?? null, status: fields.status ?? 'backlog',
		priority: fields.priority ?? null,
		assignee_ids: fields.assignee_ids ?? [], start_date: fields.start_date ?? null,
		due_date: fields.due_date ?? null, progress: 0, attachment_required: fields.attachment_required ?? false,
		labels: fields.labels ?? [],
		sort_key: Date.now(), created_by_id: get(user)?.id ?? null, completed_at: null,
		created_at: Date.now(), updated_at: Date.now()
	};
	tasks.update((list) => [...list, optimistic]);
	try {
		const saved = await api.createTask(token(), workstreamId, fields);
		tasks.update((list) =>
			// A realtime task.created event may have already inserted the saved
			// row while this request was in flight — drop the temp row rather
			// than mapping it, so we don't end up with a duplicate id.
			list.some((t) => t.id === saved.id)
				? list.filter((t) => t.id !== tempId)
				: list.map((t) => (t.id === tempId ? saved : t))
		);
	} catch (e) {
		tasks.update((list) => list.filter((t) => t.id !== tempId)); // rollback
		throw e;
	}
}

export async function editTask(id: string, fields: Partial<Task>): Promise<void> {
	const before = get(tasks).find((t) => t.id === id);
	tasks.update((list) => list.map((t) => (t.id === id ? { ...t, ...fields } : t)));
	const beforeInbox = get(inboxTask);
	inboxTask.update((t) => (t && t.id === id ? { ...t, ...fields } : t));
	// `selectedTask` may be serving the `myTasks` fallback copy (My Work detail,
	// or an inbox open whose getTask failed) — mirror the edit there too, or a
	// successful save renders as a rollback on screen.
	const beforeMy = get(myTasks).find((t) => t.id === id);
	myTasks.update((list) => list.map((t) => (t.id === id ? { ...t, ...fields } : t)));
	try {
		const saved = await api.updateTask(token(), id, fields as any);
		const { deleted_label_ids, ...task } = saved;
		dropLabels(deleted_label_ids);
		tasks.update((list) => list.map((t) => (t.id === id ? (task as Task) : t)));
		inboxTask.update((t) => (t && t.id === id ? { ...t, ...(task as Task) } : t));
		myTasks.update((list) => list.map((t) => (t.id === id ? { ...t, ...(task as Task) } : t)));
	} catch (e) {
		if (before) tasks.update((list) => list.map((t) => (t.id === id ? before : t)));
		if (beforeInbox) inboxTask.update((t) => (t && t.id === id ? beforeInbox : t));
		if (beforeMy) myTasks.update((list) => list.map((t) => (t.id === id ? beforeMy : t)));
		// request() rejects with { detail, status }; tolerate a bare string too
		// (same defensive idiom as the dialog error handlers).
		const detail = typeof e === 'string' ? e : (e as any)?.detail;
		if (detail === 'ATTACHMENT_REQUIRED') {
			toast.error('Attach a file before completing this task');
			return; // handled: rolled back + user informed
		}
		if (detail === 'Task needs at least one assignee.') {
			toast.error('A task needs at least one assignee');
			return; // handled: rolled back + user informed
		}
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

// Pagination cursors are SERVER-owned: derived only from the tail of a server
// page, never from the rendered list — a locally inserted row (e.g. an unarchived
// old notification sorting to the list's tail) would otherwise become the cursor
// and permanently skip every row between the real page boundary and itself.
type NotifCursor = { before: number; beforeId: string } | null;
let notifCursor: NotifCursor = null;
let archCursor: NotifCursor = null;
const cursorOf = (page: Notification[]): NotifCursor =>
	page.length ? { before: page[page.length - 1].created_at, beforeId: page[page.length - 1].id } : null;

// Every inbox mutation bumps this at its optimistic apply; list fetches capture
// it at request start and DISCARD their response if it advanced mid-flight. A
// list snapshotted server-side before a mutation committed would otherwise
// resurrect rows the mutation already moved (an archived row back in the active
// list, read flags reverted) — the mutation's own optimistic state is correct.
let notifMutSeq = 0;

export async function loadNotifications(): Promise<void> {
	const seq = notifMutSeq;
	const [list, counts] = await Promise.all([
		api.listNotifications(token(), { limit: NOTIF_PAGE }).catch(() => [] as Notification[]),
		api.getNotificationCounts(token()).catch(() => null)
	]);
	if (seq !== notifMutSeq) return; // stale snapshot — a mutation won the race
	notifications.set(list);
	notifCursor = cursorOf(list);
	notificationsHasMore.set(list.length === NOTIF_PAGE);
	if (counts) {
		notificationCounts.set(counts);
		unreadCount.set(counts.unread);
	}
}

export async function loadMoreNotifications(): Promise<void> {
	const cur = get(notifications);
	// Bulk mutations (sweep read) can empty the page while more rows exist on
	// the server — with no row to derive a cursor from, refill from page 1.
	if (!cur.length) return loadNotifications();
	const oldest = cur[cur.length - 1];
	const c = notifCursor ?? { before: oldest.created_at, beforeId: oldest.id };
	const seq = notifMutSeq;
	let more: Notification[];
	try {
		more = await api.listNotifications(token(), {
			limit: NOTIF_PAGE, before: c.before, beforeId: c.beforeId
		});
	} catch {
		// Failure is NOT an empty page: leave cursor + hasMore untouched so the
		// Load more control survives and a retry re-requests the same window.
		toast.error('Failed to load more notifications');
		return;
	}
	if (seq !== notifMutSeq) return; // stale page — discard before it moves the cursor
	if (more.length) notifCursor = cursorOf(more);
	notifications.update((l) => [...l, ...more.filter((n) => !l.some((x) => x.id === n.id))]);
	notificationsHasMore.set(more.length === NOTIF_PAGE);
}

export async function loadArchivedNotifications(): Promise<void> {
	const seq = notifMutSeq;
	const list = await api
		.listNotifications(token(), { archived: true, limit: NOTIF_PAGE })
		.catch(() => [] as Notification[]);
	if (seq !== notifMutSeq) return; // stale snapshot — a mutation won the race
	archivedNotifications.set(list);
	archCursor = cursorOf(list);
	archivedHasMore.set(list.length === NOTIF_PAGE);
}

export async function loadMoreArchivedNotifications(): Promise<void> {
	const cur = get(archivedNotifications);
	if (!cur.length) return loadArchivedNotifications(); // emptied by bulk unarchive → refill
	const oldest = cur[cur.length - 1];
	const c = archCursor ?? { before: oldest.created_at, beforeId: oldest.id };
	const seq = notifMutSeq;
	let more: Notification[];
	try {
		more = await api.listNotifications(token(), {
			archived: true, limit: NOTIF_PAGE, before: c.before, beforeId: c.beforeId
		});
	} catch {
		toast.error('Failed to load more notifications');
		return;
	}
	if (seq !== notifMutSeq) return; // stale page — discard before it moves the cursor
	if (more.length) archCursor = cursorOf(more);
	archivedNotifications.update((l) => [...l, ...more.filter((n) => !l.some((x) => x.id === n.id))]);
	archivedHasMore.set(more.length === NOTIF_PAGE);
}

/** Decrement unread + per-type counts for rows that were unread until now. */
function decrementCounts(rows: Notification[]): void {
	const affected = rows.filter((n) => !n.read);
	if (!affected.length) return;
	notificationCounts.update((c) => {
		const by = { ...c.by_type };
		for (const n of affected) by[n.type] = Math.max(0, (by[n.type] ?? 0) - 1);
		return { unread: Math.max(0, c.unread - affected.length), by_type: by };
	});
}

/** Inverse of decrementCounts — re-add unread rows' count contributions. */
function incrementCounts(rows: Notification[]): void {
	const affected = rows.filter((n) => !n.read);
	if (!affected.length) return;
	notificationCounts.update((c) => {
		const by = { ...c.by_type };
		for (const n of affected) by[n.type] = (by[n.type] ?? 0) + 1;
		return { unread: c.unread + affected.length, by_type: by };
	});
}

/** Failure-rollback primitive: restore ONLY the rows the failed operation itself
 * changed, in place. Rows it never touched — realtime arrivals and concurrent
 * mutations (which may have committed server-side) — are left alone; a whole-list
 * snapshot restore would locally revert a neighbour's committed success. */
function revertOwnRows(store: Writable<Notification[]>, rows: Notification[]): void {
	store.update((list) => list.map((n) => rows.find((r) => r.id === n.id) ?? n));
}

/** Failure-rollback primitive for rows the failed operation REMOVED from a list:
 * re-insert the originals (deduped — a concurrent mutation may have already
 * brought one back) and restore newest-first order. */
function reinsertRows(store: Writable<Notification[]>, rows: Notification[]): void {
	store.update((list) =>
		[...rows.filter((r) => !list.some((n) => n.id === r.id)), ...list]
			.sort((a, b) => b.created_at - a.created_at)
	);
}

export async function archiveNotificationsAction(ids: string[], archived = true): Promise<void> {
	notifMutSeq++; // invalidate in-flight list snapshots (see notifMutSeq)
	const moving = archived
		? get(notifications).filter((n) => ids.includes(n.id))
		: get(archivedNotifications).filter((n) => ids.includes(n.id));
	if (archived) {
		decrementCounts(moving);
		notifications.update((l) => l.filter((n) => !ids.includes(n.id)));
		archivedNotifications.update((l) => [
			...moving.map((n) => ({ ...n, read: true, archived: true })), ...l
		]);
	} else {
		archivedNotifications.update((l) => l.filter((n) => !ids.includes(n.id)));
		notifications.update((l) =>
			[...moving.map((n) => ({ ...n, archived: false })), ...l].sort((a, b) => b.created_at - a.created_at)
		);
	}
	try {
		const r = await api.archiveNotifications(token(), { ids, archived });
		unreadCount.set(r.unread);
	} catch (e) {
		// Per-op rollback: pull this action's optimistic copies back out of the
		// destination list and restore its original rows in the source list. Rows
		// owned by concurrent mutations stay untouched (see revert helpers).
		if (archived) {
			archivedNotifications.update((l) => l.filter((n) => !ids.includes(n.id)));
			reinsertRows(notifications, moving);
			incrementCounts(moving);
		} else {
			notifications.update((l) => l.filter((n) => !ids.includes(n.id)));
			reinsertRows(archivedNotifications, moving);
		}
		throw e;
	}
}

export async function archiveAllRead(): Promise<void> {
	notifMutSeq++; // invalidate in-flight list snapshots (see notifMutSeq)
	const removed = get(notifications).filter((n) => n.read);
	notifications.update((l) => l.filter((n) => !n.read));
	try {
		await api.archiveNotifications(token(), { all_read: true, archived: true });
	} catch (e) {
		reinsertRows(notifications, removed);
		throw e;
	}
	void loadArchivedNotifications().catch(() => {});
}

/** Inbox split-pane open: mark read + resolve the task beside the list (no view switch). */
export async function openInboxNotification(n: Notification): Promise<void> {
	const seq = ++inboxOpenSeq;
	// Non-blocking: the selection must not wait on — or die with — mark-read.
	// Its own optimistic update + rollback handles the row state independently,
	// and awaiting it would let a slower A-click finish after (and clobber) a
	// faster B-click.
	if (!n.read) markRead([n.id]).catch(() => {});
	highlightCommentId.set(n.comment_id ?? null);
	inboxTask.set(null);
	inboxTaskError.set(false);
	inboxTaskLoadError.set(false);
	// Join the task's workstream room so comment/activity/task events stream into
	// the pane even when the task lives outside the current workstream. Rooms are
	// ref-counted, so overlapping the current workstream's own room is safe.
	if (inboxRoomKey) {
		leaveRoom(inboxRoomKey);
		inboxRoomKey = null;
	}
	const ws = n.data?.workstream_id;
	if (ws) {
		inboxRoomKey = streamKey(ws);
		enterRoom(inboxRoomKey);
	}
	// Clear the shared detail stores BEFORE switching — otherwise the previous
	// task's comments/activity render under the new task until its fetches land.
	comments.set([]);
	activity.set([]);
	attachments.set([]);
	subtasks.set([]);
	selectedTaskId.set(n.task_id ?? null);
	if (!n.task_id) return;
	void loadTaskDetail(n.task_id);
	let t: Task | null = null;
	let gone = false;
	try {
		t = await api.getTask(token(), n.task_id);
	} catch (e: any) {
		// Only a confirmed 404/403 means the task is really gone. Anything else
		// (network, 5xx, parse) is transient and must not present as loss.
		gone = e?.status === 404 || e?.status === 403;
	}
	if (seq !== inboxOpenSeq || get(selectedTaskId) !== n.task_id) return; // user moved on
	if (t) inboxTask.set(t);
	else if (gone) inboxTaskError.set(true);
	else inboxTaskLoadError.set(true);
}

/**
 * Deep-link task open (URL `task` param): the id may live outside both the
 * loaded workstream list and My Work. Local lists first; otherwise fetch the
 * row directly and park it in `inboxTask` — the first slot in the
 * `selectedTask` derivation — joining its workstream room so realtime keeps
 * the drawer fresh (same mechanics as the inbox split-pane; closeTask()
 * undoes all of it). Returns false when the task is gone or unreadable —
 * 404 and 403 are indistinguishable by design (see the access reference).
 */
export async function openTaskById(id: string): Promise<boolean> {
	if (get(tasks).some((t) => t.id === id) || get(myTasks).some((t) => t.id === id)) {
		openTask(id);
		return true;
	}
	let t: Task | null = null;
	try {
		t = await api.getTask(token(), id);
	} catch {
		t = null; // transient failures also report false: a deep link has no retry UI
	}
	if (!t) return false;
	if (inboxRoomKey) {
		leaveRoom(inboxRoomKey);
		inboxRoomKey = null;
	}
	inboxRoomKey = streamKey(t.workstream_id);
	enterRoom(inboxRoomKey);
	// inboxTask BEFORE selectedTaskId so the drawer renders once, with data.
	inboxTask.set(t);
	selectedTaskId.set(id);
	void loadTaskDetail(id);
	return true;
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

export async function loadWorkstreamFiles(id: string): Promise<void> {
	wsFiles.set({ items: [], loaded: false, error: false });
	try {
		const items = await api.listWorkstreamAttachments(token(), id);
		if (get(currentWorkstreamId) !== id) return; // user moved on
		wsFiles.set({ items, loaded: true, error: false });
	} catch {
		if (get(currentWorkstreamId) !== id) return; // user moved on
		wsFiles.set({ items: [], loaded: true, error: true });
	}
}

/** While the Files view is open, an attachment room event for the current
 * workstream refetches the listing (rows need the server-side task join). */
export function applyFilesEvent(event: string, payload: any): void {
	if (event !== 'workos:attachment.created' && event !== 'workos:attachment.deleted') return;
	if (get(view) !== 'files') return;
	const ws = get(currentWorkstreamId);
	if (!ws || !payload || payload.workstream_id !== ws) return;
	void loadWorkstreamFiles(ws);
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
	notifMutSeq++; // invalidate in-flight list snapshots (see notifMutSeq)
	// Only rows this op actually flips (already-read rows are untouched by both
	// the optimistic update and the rollback).
	const touched = get(notifications).filter((n) => ids.includes(n.id) && !n.read);
	decrementCounts(touched);
	notifications.update((list) => list.map((n) => (ids.includes(n.id) ? { ...n, read: true } : n)));
	try {
		const r = await api.markNotificationsRead(token(), { ids });
		unreadCount.set(r.unread);
	} catch (e) {
		// Only rows still in the active list are ours to roll back — a concurrent
		// archive may have moved a row out mid-flight (and now owns its state);
		// restoring that row's count contribution would leave a phantom unread badge.
		const present = new Set(get(notifications).map((n) => n.id));
		const own = touched.filter((n) => present.has(n.id));
		revertOwnRows(notifications, own);
		incrementCounts(own);
		if (own.length < touched.length) {
			// Count ownership for the moved rows is ambiguous — refetch server truth.
			const counts = await api.getNotificationCounts(token()).catch(() => null);
			if (counts) {
				notificationCounts.set(counts);
				unreadCount.set(counts.unread);
			}
		}
		throw e;
	}
}

export async function markAllRead(): Promise<void> {
	notifMutSeq++; // invalidate in-flight list snapshots (see notifMutSeq)
	const touched = get(notifications).filter((n) => !n.read);
	const beforeCounts = get(notificationCounts);
	notifications.update((list) => list.map((n) => ({ ...n, read: true })));
	notificationCounts.set(EMPTY_COUNTS());
	try {
		const r = await api.markNotificationsRead(token(), { all: true });
		unreadCount.set(r.unread);
	} catch (e) {
		revertOwnRows(notifications, touched);
		// The optimistic EMPTY_COUNTS wipe also covered rows beyond the loaded page,
		// so it can't be reverted per-row — refetch server truth; fall back to the
		// pre-op snapshot when even that request fails (offline).
		const counts = await api.getNotificationCounts(token()).catch(() => null);
		if (counts) {
			notificationCounts.set(counts);
			unreadCount.set(counts.unread);
		} else {
			notificationCounts.set(beforeCounts);
		}
		throw e;
	}
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
	const exists = get(notifications).some((n) => n.id === payload.id);
	if (!exists) notifications.update((l) => [payload, ...l]);
	if (!payload.read && !exists) {
		unreadCount.update((n) => n + 1);
		notificationCounts.update((c) => ({
			unread: c.unread + 1,
			by_type: { ...c.by_type, [payload.type]: (c.by_type[payload.type] ?? 0) + 1 }
		}));
	}
}

/** Reconcile a realtime event into local state. Exported for tests + the socket wiring. */
export function applyTaskEvent(event: string, payload: any): void {
	if (!payload) return;
	// Split-pane inbox: the inline task may belong to another workstream.
	if (event === 'workos:task.updated') {
		inboxTask.update((t) => (t && t.id === payload.id ? payload : t));
	} else if (event === 'workos:task.deleted' && get(inboxTask)?.id === payload.id) {
		inboxTask.set(null);
		inboxTaskError.set(true); // pane flips to "Task no longer available"
	}
	const ws = get(currentWorkstreamId);
	if (payload.workstream_id !== ws) return;
	if (event === 'workos:task.created') {
		tasks.update((list) => (list.some((t) => t.id === payload.id) ? list : [...list, payload]));
	} else if (event === 'workos:task.updated') {
		tasks.update((list) => list.map((t) => (t.id === payload.id ? payload : t)));
	} else if (event === 'workos:task.deleted') {
		tasks.update((list) => list.filter((t) => t.id !== payload.id));
		// If the inbox pane owns the selection, inboxTaskError was just set above —
		// keep the id so the pane shows "Task no longer available" instead of
		// snapping to "Select a notification". Board flow (no inbox error) clears.
		if (get(selectedTaskId) === payload.id && !get(inboxTaskError)) selectedTaskId.set(null);
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
			applyFilesEvent(ev, payload);
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
