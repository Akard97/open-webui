import { describe, it, expect } from 'vitest';
import { addableUsers, addableWorkspaceMembers, isLastOwner } from './members';
import type { Member } from './types';

const member = (user_id: string, role: string): Member =>
	({ id: `m-${user_id}`, user_id, role, created_at: 0 }) as Member;

describe('addableUsers', () => {
	it('excludes existing members from the roster', () => {
		const roster = [
			{ id: 'u1', name: 'Lara' },
			{ id: 'u2', name: 'Yusuf' }
		];
		expect(addableUsers(roster, [member('u1', 'owner')])).toEqual([{ id: 'u2', name: 'Yusuf' }]);
		expect(addableUsers(roster, [])).toHaveLength(2);
	});
});

describe('addableWorkspaceMembers', () => {
	it('offers team members not yet on the workspace', () => {
		const team = [member('u1', 'owner'), member('u2', 'member')];
		const ws = [member('u1', 'admin')];
		expect(addableWorkspaceMembers(team, ws).map((m) => m.user_id)).toEqual(['u2']);
	});
	it('empty when everyone is already added', () => {
		const team = [member('u1', 'owner')];
		expect(addableWorkspaceMembers(team, [member('u1', 'admin')])).toEqual([]);
	});
});

describe('isLastOwner', () => {
	it('true only for the sole owner', () => {
		expect(isLastOwner(['u1'], 'u1')).toBe(true);
		expect(isLastOwner(['u1'], 'u2')).toBe(false);
		expect(isLastOwner(['u1', 'u2'], 'u1')).toBe(false);
		expect(isLastOwner([], 'u1')).toBe(false);
	});
});
