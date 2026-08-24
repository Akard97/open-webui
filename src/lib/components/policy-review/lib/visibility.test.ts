import { describe, it, expect } from 'vitest';
import { canSeePolicyReview } from './visibility';

const cfg = (enabled: boolean) => ({ features: { enable_policy_review: enabled } });

describe('canSeePolicyReview', () => {
	it('shows the tool to everyone when the flag is on', () => {
		expect(canSeePolicyReview({ user: { role: 'user' }, config: cfg(true) })).toBe(true);
	});

	it('hides the tool from plain users when the flag is off', () => {
		expect(canSeePolicyReview({ user: { role: 'user' }, config: cfg(false) })).toBe(false);
	});

	it('always shows the tool to admins', () => {
		expect(canSeePolicyReview({ user: { role: 'admin' }, config: cfg(false) })).toBe(true);
	});

	it('always shows the tool to policy_checker users', () => {
		const user = { role: 'user', permissions: { features: { policy_checker: true } } };
		expect(canSeePolicyReview({ user, config: cfg(false) })).toBe(true);
	});

	it('treats a missing flag as off (config not loaded yet)', () => {
		expect(canSeePolicyReview({ user: { role: 'user' }, config: undefined })).toBe(false);
		expect(canSeePolicyReview({ user: { role: 'user' }, config: {} })).toBe(false);
	});

	it('treats a missing or false policy_checker permission as no access', () => {
		expect(canSeePolicyReview({ user: { role: 'user', permissions: {} }, config: cfg(false) })).toBe(false);
		const user = { role: 'user', permissions: { features: { policy_checker: false } } };
		expect(canSeePolicyReview({ user, config: cfg(false) })).toBe(false);
	});

	it('handles a null user (logged-out edge) without crashing', () => {
		expect(canSeePolicyReview({ user: null, config: cfg(false) })).toBe(false);
		expect(canSeePolicyReview({ user: null, config: cfg(true) })).toBe(true);
	});
});
