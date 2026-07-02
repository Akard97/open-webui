import type { Task, TeamRole, WorkspaceRole } from './types';

export function canManageTeam(role: TeamRole | undefined): boolean {
	return role === 'owner';
}

export function canManageMembers(role: TeamRole | undefined): boolean {
	return role === 'owner' || role === 'admin';
}

export function canCreateWorkspace(role: TeamRole | undefined): boolean {
	return role === 'owner' || role === 'admin';
}

export function canManageWorkspace(
	teamRole: TeamRole | undefined,
	workspaceRole: WorkspaceRole | undefined
): boolean {
	return teamRole === 'owner' || teamRole === 'admin' || workspaceRole === 'admin';
}

export function canDeleteTask(task: Task, userId: string, teamRole: TeamRole | undefined): boolean {
	return task.created_by_id === userId || teamRole === 'owner' || teamRole === 'admin';
}

export function canUseAdmin(user: { role?: string; permissions?: any } | null | undefined): boolean {
	if (!user) return false;
	return user.role === 'admin' || !!user?.permissions?.features?.workos_admin;
}

// Access console gate: system admins, or anyone who owns/administers at least
// one team (`roles` = bootstrap map teamId -> caller's role). The workos_admin
// permission flag deliberately does NOT pass — the console is team-scoped.
export function canUseAccessConsole(
	user: { role?: string } | null | undefined,
	roles: Record<string, TeamRole> | null | undefined
): boolean {
	if (!user) return false;
	if (user.role === 'admin') return true;
	return Object.values(roles ?? {}).some((r) => r === 'owner' || r === 'admin');
}

export function canDeleteComment(
	comment: { user_id: string },
	userId: string,
	role: 'owner' | 'admin' | 'member' | undefined
): boolean {
	return comment.user_id === userId || role === 'owner' || role === 'admin';
}

export function canDeleteAttachment(
	att: { created_by_id?: string | null },
	userId: string,
	role: 'owner' | 'admin' | 'member' | undefined
): boolean {
	return att.created_by_id === userId || role === 'owner' || role === 'admin';
}

export function canEditTask(
	task: Task,
	userId: string,
	teamRole: TeamRole | undefined,
	workspaceRole: WorkspaceRole | undefined
): boolean {
	return (
		task.created_by_id === userId ||
		(task.assignee_ids ?? []).includes(userId) ||
		canManageWorkspace(teamRole, workspaceRole)
	);
}

export function canEditSubtask(
	subtask: { created_by_id?: string | null },
	task: Task,
	userId: string,
	teamRole: TeamRole | undefined,
	workspaceRole: WorkspaceRole | undefined
): boolean {
	return subtask.created_by_id === userId || canEditTask(task, userId, teamRole, workspaceRole);
}
