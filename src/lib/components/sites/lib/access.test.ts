import { describe, expect, it } from 'vitest';
import { isEveryoneGrant, siteAccessLevel } from './access';

const everyone = { principal_type: 'user', principal_id: '*', permission: 'read' };

describe('isEveryoneGrant', () => {
	it.each([
		[everyone, true],
		[{ principal_type: 'group', principal_id: '*', permission: 'read' }, false],
		[{ principal_type: 'user', principal_id: '*', permission: 'write' }, false],
		[{ principal_type: 'user', principal_id: 'u1', permission: 'read' }, false],
		[null, false],
		[undefined, false]
	])('%j -> %s', (grant, expected) => {
		expect(isEveryoneGrant(grant as any)).toBe(expected);
	});
});

describe('siteAccessLevel', () => {
	it.each([
		[{ public: true, access_grants: [] }, 'public'],
		[{ public: false, access_grants: [everyone] }, 'internal'],
		[
			{
				public: false,
				access_grants: [{ principal_type: 'user', principal_id: 'u1', permission: 'read' }]
			},
			'specific'
		],
		// a group literally named '*' is a specific grant, not "everyone"
		[
			{
				public: false,
				access_grants: [{ principal_type: 'group', principal_id: '*', permission: 'read' }]
			},
			'specific'
		],
		[{ public: false, access_grants: [] }, 'private'],
		[{ public: false }, 'private'],
		[null, 'private']
	])('%j -> %s', (site, expected) => {
		expect(siteAccessLevel(site as any)).toBe(expected);
	});
});
