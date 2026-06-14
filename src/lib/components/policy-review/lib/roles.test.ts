import { describe, it, expect } from 'vitest';
import { policyRoleLabel } from './roles';

describe('policyRoleLabel', () => {
	it('labels an approver as OE Approver (regardless of checker flag)', () => {
		expect(policyRoleLabel(true, true)).toBe('Organizational Excellence · Approver');
		expect(policyRoleLabel(true, false)).toBe('Organizational Excellence · Approver');
	});

	it('labels a checker-only user as OE Reviewer', () => {
		expect(policyRoleLabel(false, true)).toBe('Organizational Excellence · Reviewer');
	});

	it('labels a user with no policy permissions as a plain Viewer', () => {
		expect(policyRoleLabel(false, false)).toBe('Viewer');
	});
});
