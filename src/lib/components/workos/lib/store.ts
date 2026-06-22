import { writable, derived, get, type Writable } from 'svelte/store';
import { browser } from '$app/environment';
import { socket, user } from '$lib/stores';
import * as api from './api';
import { midpoint } from './key';
import {
	STATUS_ORDER,
	type Team, type Workspace, type Workstream, type Label, type Task, type Member,
	type TeamRole, type TaskStatus, type TaskPriority
} from './types';

export type ViewKey = 'board' | 'list' | 'admin';

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
}
export function closeTask(): void {
	selectedTaskId.set(null);
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
	for (const ev of [...TASK_EVENTS, 'connect']) {
		if (handlers[ev]) s.off(ev, handlers[ev]);
	}
	const ws = get(currentWorkstreamId);
	if (ws) unsubscribeRoom(ws);
	bound = false;
}
