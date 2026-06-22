import { describe, it, expect } from 'vitest';
import {
	canManageTeam, canManageMembers, canCreateWorkspace, canManageWorkspace, canDeleteTask, canUseAdmin
} from './roles';
import type { Task } from './types';

const task = (over: Partial<Task> = {}): Task => ({
	id: 't', workstream_id: 'w', team_id: 'tm', number: 1, key: 'OSL-1', title: 'x',
	status: 'todo', progress: 0, labels: [], sort_key: 1, created_by_id: 'u1',
	created_at: 0, updated_at: 0, ...over
});

describe('roles', () => {
	it('only owner manages the team', () => {
		expect(canManageTeam('owner')).toBe(true);
		expect(canManageTeam('admin')).toBe(false);
		expect(canManageTeam(undefined)).toBe(false);
	});
	it('owner/admin manage members and create workspaces', () => {
		expect(canManageMembers('admin')).toBe(true);
		expect(canManageMembers('member')).toBe(false);
		expect(canCreateWorkspace('owner')).toBe(true);
		expect(canCreateWorkspace('member')).toBe(false);
	});
	it('workspace management: team owner/admin OR workspace admin', () => {
		expect(canManageWorkspace('admin', undefined)).toBe(true);
		expect(canManageWorkspace('member', 'admin')).toBe(true);
		expect(canManageWorkspace('member', 'member')).toBe(false);
	});
	it('task deletion: creator or team admin', () => {
		expect(canDeleteTask(task({ created_by_id: 'u1' }), 'u1', 'member')).toBe(true);
		expect(canDeleteTask(task({ created_by_id: 'u9' }), 'u1', 'member')).toBe(false);
		expect(canDeleteTask(task({ created_by_id: 'u9' }), 'u1', 'admin')).toBe(true);
	});
	it('admin center: system admin or workos_admin permission', () => {
		expect(canUseAdmin({ role: 'admin', permissions: {} })).toBe(true);
		expect(canUseAdmin({ role: 'user', permissions: { features: { workos_admin: true } } })).toBe(true);
		expect(canUseAdmin({ role: 'user', permissions: { features: { workos_admin: false } } })).toBe(false);
	});
});
