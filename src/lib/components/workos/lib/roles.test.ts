import { describe, it, expect } from 'vitest';
import {
	canManageTeam, canManageMembers, canCreateWorkspace, canManageWorkspace, canDeleteTask, canUseAdmin,
	canEditTask, canEditSubtask, canToggleAttachmentRequired
} from './roles';
import type { Task } from './types';

const task = (over: Partial<Task> = {}): Task => ({
	id: 't', workstream_id: 'w', team_id: 'tm', number: 1, key: 'OSL-1', title: 'x',
	status: 'todo', progress: 0, labels: [], sort_key: 1, created_by_id: 'u1',
	assignee_ids: [], created_at: 0, updated_at: 0, ...over
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
	it('task editing: creator, assignee, or workspace manager', () => {
		expect(canEditTask(task({ created_by_id: 'u1' }), 'u1', 'member', undefined)).toBe(true);
		expect(canEditTask(task({ created_by_id: 'u9', assignee_ids: ['u1'] }), 'u1', 'member', undefined)).toBe(true);
		expect(canEditTask(task({ created_by_id: 'u9', assignee_ids: [] }), 'u1', 'member', 'member')).toBe(false);
		expect(canEditTask(task({ created_by_id: 'u9' }), 'u1', 'admin', undefined)).toBe(true);
	});
	it('subtask editing: subtask author or task editor', () => {
		expect(canEditSubtask({ created_by_id: 'u1' }, task({ created_by_id: 'u9' }), 'u1', 'member', undefined)).toBe(true);
		expect(canEditSubtask({ created_by_id: 'u9' }, task({ created_by_id: 'u9' }), 'u1', 'member', undefined)).toBe(false);
	});
});

describe('canToggleAttachmentRequired', () => {
	it('creator may toggle', () => {
		expect(canToggleAttachmentRequired(task({ created_by_id: 'u1' }), { id: 'u1', role: 'user' })).toBe(true);
	});
	it('app admin may toggle', () => {
		expect(canToggleAttachmentRequired(task({ created_by_id: 'u1' }), { id: 'zz', role: 'admin' })).toBe(true);
	});
	it('assignee / other members may not', () => {
		expect(canToggleAttachmentRequired(task({ created_by_id: 'u1' }), { id: 'u2', role: 'user' })).toBe(false);
	});
	it('legacy task without creator: admin only', () => {
		const legacy = task({ created_by_id: null });
		expect(canToggleAttachmentRequired(legacy, { id: 'u1', role: 'user' })).toBe(false);
		expect(canToggleAttachmentRequired(legacy, { id: 'u1', role: 'admin' })).toBe(true);
	});
});
