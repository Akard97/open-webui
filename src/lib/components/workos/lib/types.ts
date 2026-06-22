export type TeamRole = 'owner' | 'admin' | 'member';
export type WorkspaceRole = 'admin' | 'member';
export type TaskStatus = 'backlog' | 'todo' | 'in_progress' | 'in_review' | 'done' | 'canceled';
export type TaskPriority = 'urgent' | 'high' | 'medium' | 'low';
export type Visibility = 'team' | 'restricted';

export interface Team {
	id: string;
	key: string;
	name: string;
	icon?: string | null;
	task_seq: number;
	archived: boolean;
	created_by_id?: string | null;
	created_at: number;
	updated_at: number;
}

export interface Workspace {
	id: string;
	team_id: string;
	name: string;
	icon?: string | null;
	visibility: Visibility;
	archived: boolean;
	created_by_id?: string | null;
	created_at: number;
	updated_at: number;
}

export interface Workstream {
	id: string;
	workspace_id: string;
	name: string;
	icon?: string | null;
	archived: boolean;
	created_by_id?: string | null;
	created_at: number;
	updated_at: number;
}

export interface Label {
	id: string;
	team_id: string;
	name: string;
	color: string;
	created_at: number;
}

export interface Task {
	id: string;
	workstream_id: string;
	team_id: string;
	number: number;
	key: string;
	title: string;
	description?: string | null;
	status: TaskStatus;
	priority?: TaskPriority | null;
	assignee_id?: string | null;
	due_date?: number | null;
	progress: number;
	labels: string[];
	sort_key: number;
	created_by_id?: string | null;
	completed_at?: number | null;
	created_at: number;
	updated_at: number;
}

export interface Member {
	id: string;
	team_id?: string;
	workspace_id?: string;
	user_id: string;
	role: TeamRole | WorkspaceRole;
	created_at: number;
}

export interface Bootstrap {
	teams: Team[];
	workspaces: Workspace[];
	workstreams: Workstream[];
	roles: Record<string, TeamRole>;
}

export interface WorkosRules {
	team_creation: 'all_users' | 'admins_only';
	default_workspace_visibility: Visibility;
}

export const STATUS_ORDER: TaskStatus[] = ['backlog', 'todo', 'in_progress', 'in_review', 'done'];

export const STATUS_LABEL: Record<TaskStatus, string> = {
	backlog: 'Backlog',
	todo: 'Todo',
	in_progress: 'In Progress',
	in_review: 'In Review',
	done: 'Done',
	canceled: 'Canceled'
};

export const PRIORITY_ORDER: TaskPriority[] = ['urgent', 'high', 'medium', 'low'];
