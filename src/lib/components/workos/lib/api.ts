import { WEBUI_API_BASE_URL } from '$lib/constants';
import type {
	Bootstrap, Team, Workspace, Workstream, Label, Task, Member, WorkosRules,
	TaskStatus, TaskPriority, Visibility, TeamRole, WorkspaceRole
} from './types';

const BASE = `${WEBUI_API_BASE_URL}/workos`;

async function request<T>(token: string, path: string, method = 'GET', body?: unknown): Promise<T> {
	let error: unknown = null;
	const res = await fetch(`${BASE}${path}`, {
		method,
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			authorization: `Bearer ${token}`
		},
		...(body !== undefined ? { body: JSON.stringify(body) } : {})
	})
		.then(async (r) => {
			if (!r.ok) throw await r.json();
			return r.json();
		})
		.catch((err) => {
			error = err?.detail ?? err;
			console.error('[workos api]', error);
			return null;
		});
	if (error) throw error;
	return res as T;
}

// Bootstrap
export const getBootstrap = (token: string) => request<Bootstrap>(token, '/bootstrap');

// Teams
export const listTeams = (token: string) => request<Team[]>(token, '/teams');
export const createTeam = (token: string, body: { name: string; key: string; icon?: string }) =>
	request<Team>(token, '/teams', 'POST', body);
export const getTeam = (token: string, id: string) => request<Team>(token, `/teams/${id}`);
export const updateTeam = (token: string, id: string, body: Partial<Pick<Team, 'name' | 'icon' | 'archived'>>) =>
	request<Team>(token, `/teams/${id}`, 'PATCH', body);
export const deleteTeam = (token: string, id: string) => request<{ deleted: boolean }>(token, `/teams/${id}`, 'DELETE');
export const listTeamMembers = (token: string, id: string) => request<Member[]>(token, `/teams/${id}/members`);
export const addTeamMember = (token: string, id: string, body: { user_id: string; role: TeamRole }) =>
	request<Member>(token, `/teams/${id}/members`, 'POST', body);
export const updateTeamMember = (token: string, id: string, userId: string, body: { role: TeamRole }) =>
	request<Member>(token, `/teams/${id}/members/${userId}`, 'PATCH', body);
export const removeTeamMember = (token: string, id: string, userId: string) =>
	request<{ removed: boolean }>(token, `/teams/${id}/members/${userId}`, 'DELETE');

// Workspaces
export const listWorkspaces = (token: string, teamId: string) =>
	request<Workspace[]>(token, `/teams/${teamId}/workspaces`);
export const createWorkspace = (
	token: string, teamId: string, body: { name: string; icon?: string; visibility: Visibility }
) => request<Workspace>(token, `/teams/${teamId}/workspaces`, 'POST', body);
export const getWorkspace = (token: string, id: string) => request<Workspace>(token, `/workspaces/${id}`);
export const updateWorkspace = (
	token: string, id: string, body: Partial<Pick<Workspace, 'name' | 'icon' | 'visibility' | 'archived'>>
) => request<Workspace>(token, `/workspaces/${id}`, 'PATCH', body);
export const deleteWorkspace = (token: string, id: string) =>
	request<{ deleted: boolean }>(token, `/workspaces/${id}`, 'DELETE');
export const listWorkspaceMembers = (token: string, id: string) =>
	request<Member[]>(token, `/workspaces/${id}/members`);
export const addWorkspaceMember = (token: string, id: string, body: { user_id: string; role: WorkspaceRole }) =>
	request<Member>(token, `/workspaces/${id}/members`, 'POST', body);
export const updateWorkspaceMember = (token: string, id: string, userId: string, body: { role: WorkspaceRole }) =>
	request<Member>(token, `/workspaces/${id}/members/${userId}`, 'PATCH', body);
export const removeWorkspaceMember = (token: string, id: string, userId: string) =>
	request<{ removed: boolean }>(token, `/workspaces/${id}/members/${userId}`, 'DELETE');

// Workstreams
export const listWorkstreams = (token: string, workspaceId: string) =>
	request<Workstream[]>(token, `/workspaces/${workspaceId}/workstreams`);
export const createWorkstream = (token: string, workspaceId: string, body: { name: string; icon?: string }) =>
	request<Workstream>(token, `/workspaces/${workspaceId}/workstreams`, 'POST', body);
export const updateWorkstream = (
	token: string, id: string, body: Partial<Pick<Workstream, 'name' | 'icon' | 'archived'>>
) => request<Workstream>(token, `/workstreams/${id}`, 'PATCH', body);
export const deleteWorkstream = (token: string, id: string) =>
	request<{ deleted: boolean }>(token, `/workstreams/${id}`, 'DELETE');

// Tasks
export const listTasks = (token: string, workstreamId: string) =>
	request<Task[]>(token, `/workstreams/${workstreamId}/tasks`);
export const createTask = (
	token: string, workstreamId: string,
	body: { title: string; description?: string; status?: TaskStatus; priority?: TaskPriority | null;
		assignee_id?: string | null; due_date?: number | null; labels?: string[] }
) => request<Task>(token, `/workstreams/${workstreamId}/tasks`, 'POST', body);
export const getTask = (token: string, id: string) => request<Task>(token, `/tasks/${id}`);
export const updateTask = (
	token: string, id: string,
	body: Partial<Pick<Task, 'title' | 'description' | 'status' | 'priority' | 'assignee_id' | 'due_date'
		| 'progress' | 'labels' | 'sort_key'>>
) => request<Task>(token, `/tasks/${id}`, 'PATCH', body);
export const deleteTask = (token: string, id: string) => request<{ deleted: boolean }>(token, `/tasks/${id}`, 'DELETE');

// Labels
export const listLabels = (token: string, teamId: string) => request<Label[]>(token, `/teams/${teamId}/labels`);
export const createLabel = (token: string, teamId: string, body: { name: string; color: string }) =>
	request<Label>(token, `/teams/${teamId}/labels`, 'POST', body);
export const updateLabel = (token: string, id: string, body: { name?: string; color?: string }) =>
	request<Label>(token, `/labels/${id}`, 'PATCH', body);
export const deleteLabel = (token: string, id: string) => request<{ deleted: boolean }>(token, `/labels/${id}`, 'DELETE');

// Directory
export const getDirectory = (token: string) => request<{ id: string; name: string }[]>(token, '/directory');

// Admin
export const adminListTeams = (token: string) =>
	request<{ team: Team; owner_ids: string[]; member_count: number }[]>(token, '/admin/teams');
export const getAdminSettings = (token: string) => request<WorkosRules>(token, '/admin/settings');
export const updateAdminSettings = (token: string, body: Partial<WorkosRules>) =>
	request<WorkosRules>(token, '/admin/settings', 'PATCH', body);
