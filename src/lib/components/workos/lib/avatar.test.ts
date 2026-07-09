import { describe, expect, it } from 'vitest';
import { avatarColor, LABEL_PALETTE } from './avatar';

describe('avatarColor', () => {
	it('is deterministic — the same input always yields the same color', () => {
		expect(avatarColor('user-42')).toBe(avatarColor('user-42'));
		expect(avatarColor('Ahmad Alsawarieh')).toBe(avatarColor('Ahmad Alsawarieh'));
	});

	it('returns a color from LABEL_PALETTE', () => {
		expect(LABEL_PALETTE).toContain(avatarColor('user-42'));
		expect(LABEL_PALETTE).toContain(avatarColor(''));
	});

	it('spreads different inputs across more than one palette color', () => {
		const colors = new Set(['alice', 'bob', 'carol', 'dave', 'erin', 'frank'].map(avatarColor));
		expect(colors.size).toBeGreaterThan(1);
	});

	it('matches the legacy per-user avatar hash so existing users keep their color', () => {
		// Same hash as the deleted per-workstream Avatar component (h = h*31 + charCode, |0, abs),
		// against the same 8-color palette, applied directly to LABEL_PALETTE.
		function legacyHash(s: string): number {
			let h = 0;
			for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
			return Math.abs(h);
		}
		for (const name of ['Ahmad Alsawarieh', 'Jane Doe', 'u-1', 'u-2', '?']) {
			expect(avatarColor(name)).toBe(LABEL_PALETTE[legacyHash(name) % LABEL_PALETTE.length]);
		}
	});
});
