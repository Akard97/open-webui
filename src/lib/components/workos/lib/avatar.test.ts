import { describe, expect, it } from 'vitest';
import type { AvatarColors } from './avatar';
import {
	AVATAR_BACKGROUNDS,
	AVATAR_PALETTE,
	avatarColor,
	avatarColors,
	LABEL_PALETTE
} from './avatar';

function relativeLuminance(hex: string): number {
	const channels = hex
		.slice(1)
		.match(/.{2}/g)!
		.map((part) => parseInt(part, 16) / 255);
	const linear = channels.map((value) =>
		value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
	);
	return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

function contrastRatio(a: string, b: string): number {
	const [lighter, darker] = [relativeLuminance(a), relativeLuminance(b)].sort(
		(x, y) => y - x
	);
	return (lighter + 0.05) / (darker + 0.05);
}

describe('avatarColor', () => {
	it('uses the approved Osool avatar backgrounds in order', () => {
		expect(AVATAR_BACKGROUNDS).toEqual([
			'#00313f',
			'#026c80',
			'#00a5ba',
			'#769a4a',
			'#dfa244',
			'#c96b5d',
			'#54c2d1',
			'#a4c979'
		]);
		expect(AVATAR_PALETTE.map(({ background }) => background)).toEqual(AVATAR_BACKGROUNDS);
	});

	it('keeps the avatar palette separate from the label palette', () => {
		expect(AVATAR_BACKGROUNDS).not.toBe(LABEL_PALETTE);
		expect(AVATAR_BACKGROUNDS).not.toEqual(LABEL_PALETTE);
		expect(LABEL_PALETTE).toEqual([
			'#00a5ba',
			'#769a4a',
			'#d97706',
			'#dc2626',
			'#7c3aed',
			'#0ea5e9',
			'#db2777',
			'#ca8a04'
		]);
	});

	it('assigns a deterministic pair and keeps avatarColor as a background wrapper', () => {
		for (const key of ['user-42', 'Ahmad Alsawarieh', '']) {
			const colors: AvatarColors = avatarColors(key);
			expect(avatarColors(key)).toEqual(colors);
			expect(avatarColor(key)).toBe(colors.background);
		}
	});

	it('spreads different inputs across more than one palette color', () => {
		const colors = new Set(
			['alice', 'bob', 'carol', 'dave', 'erin', 'frank'].map(
				(key) => avatarColors(key).background
			)
		);
		expect(colors.size).toBeGreaterThan(1);
	});

	it('gives every avatar pair at least 4.5:1 contrast', () => {
		for (const { background, foreground } of AVATAR_PALETTE) {
			expect(contrastRatio(background, foreground)).toBeGreaterThanOrEqual(4.5);
		}
	});

	it('uses the stronger accessible brand foreground, with black as the fallback', () => {
		for (const { background, foreground } of AVATAR_PALETTE) {
			const whiteRatio = contrastRatio(background, '#ffffff');
			const inkRatio = contrastRatio(background, '#00313f');
			const strongerBrand = whiteRatio >= inkRatio ? '#ffffff' : '#00313f';
			const expected = Math.max(whiteRatio, inkRatio) >= 4.5 ? strongerBrand : '#000000';

			expect(foreground).toBe(expected);
		}
	});
});
