import { describe, it, expect } from 'vitest';

import { resolveMode, THEME_LIST } from './theme';

describe('resolveMode', () => {
	it('returns light for the light theme regardless of OS preference', () => {
		expect(resolveMode('light', false)).toBe('light');
		expect(resolveMode('light', true)).toBe('light');
	});

	it('returns dark for dark and oled-dark', () => {
		expect(resolveMode('dark', false)).toBe('dark');
		expect(resolveMode('oled-dark', false)).toBe('dark');
	});

	it('resolves system from the OS preference', () => {
		expect(resolveMode('system', true)).toBe('dark');
		expect(resolveMode('system', false)).toBe('light');
	});

	it('treats any unknown theme as dark', () => {
		expect(resolveMode('whatever', false)).toBe('dark');
	});
});

describe('THEME_LIST', () => {
	it('lists every theme class applyTheme manages', () => {
		expect(THEME_LIST).toEqual(['dark', 'light', 'oled-dark']);
	});
});
