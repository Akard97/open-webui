import { describe, it, expect } from 'vitest';
import { filterOverview, addableUsers, addableWorkspaceMembers, isLastOwner } from './accessConsole';
import type { AccessTeamOverview, Member } from './types';

const row = (over: Partial<AccessTeamOverview> = {}): AccessTeamOverview => ({
	team: {
		id: 't1', key: 'OSL', name: 'Acme', task_seq: 0, archived: false, created_at: 0, updated_at: 0
	},
	my_role: 'owner',
	owner_ids: ['u1'],
	member_count: 1,
	workspaces: [],
	...over
});

const member = (user_id: string, role: string): Member =>
	({ id: `m-${user_id}`, user_id, role, created_at: 0 }) as Member;

describe('filterOverview', () => {
	const rows = [
		row(),
		row({
			team: { id: 't2', key: 'FIN', name: 'Finance', task_seq: 0, archived: false, created_at: 0, updated_at: 0 },
			workspaces: [{ id: 'w1', name: 'Compensation', visibility: 'restricted', archived: false, member_count: 2 }]
		})
	];
	it('returns everything for a blank query', () => {
		expect(filterOverview(rows, '')).toHaveLength(2);
		expect(filterOverview(rows, '   ')).toHaveLength(2);
	});
	it('matches team name and key case-insensitively', () => {
		expect(filterOverview(rows, 'acme').map((r) => r.team.id)).toEqual(['t1']);
		expect(filterOverview(rows, 'fin').map((r) => r.team.id)).toEqual(['t2']);
	});
	it('matches workspace names too', () => {
		expect(filterOverview(rows, 'compensation').map((r) => r.team.id)).toEqual(['t2']);
	});
	it('no match -> empty', () => {
		expect(filterOverview(rows, 'zzz')).toEqual([]);
	});
});

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
