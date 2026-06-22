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
