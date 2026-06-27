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
	assignee_ids: string[];
	start_date?: number | null;
	due_date?: number | null;
	progress: number;
	subtask_total?: number;
	subtask_completed?: number;
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
	notifications_unread: number;
}

export interface Comment {
	id: string;
	task_id: string;
	user_id: string;
	body: string;
	mentions: string[];
	edited_at?: number | null;
	created_at: number;
	updated_at: number;
}

export interface Attachment {
	id: string;
	task_id: string;
	comment_id?: string | null;
	storage_key: string;
	name: string;
	size: number;
	content_type?: string | null;
	created_by_id?: string | null;
	created_at: number;
}

export interface Subtask {
	id: string;
	task_id: string;
	title: string;
	completed: boolean;
	sort_key: number;
	created_by_id?: string | null;
	completed_at?: number | null;
	created_at: number;
	updated_at: number;
}

export type ActivityType =
	| 'created' | 'status_changed' | 'assignee_changed' | 'priority_changed'
	| 'due_changed' | 'completed' | 'reopened' | 'comment_added'
	| 'attachment_added' | 'title_changed' | 'description_changed'
	| 'start_changed' | 'subtask_created' | 'subtask_completed' | 'subtask_reopened';

export interface Activity {
	id: string;
	task_id: string;
	team_id: string;
	user_id: string;
	type: ActivityType;
	data: Record<string, any>;
	created_at: number;
}

export type NotificationType = 'assigned' | 'mentioned' | 'commented' | 'status_changed';

export interface Notification {
	id: string;
	user_id: string;
	actor_id?: string | null;
	task_id?: string | null;
	comment_id?: string | null;
	type: NotificationType;
	data: Record<string, any>;
	read: boolean;
	created_at: number;
}

export type FeedItem =
	| { kind: 'comment'; at: number; comment: Comment }
	| { kind: 'activity'; at: number; activity: Activity };

export interface WorkosRules {
	team_creation: 'all_users' | 'admins_only';
	default_workspace_visibility: Visibility;
	notifications?: Partial<Record<NotificationType, boolean>>;
	max_attachment_mb?: number;
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

export interface TaskFilter {
	statuses: TaskStatus[];
	priorities: TaskPriority[];
	labelIds: string[];
	assigneeIds: string[];
	text: string;
}
