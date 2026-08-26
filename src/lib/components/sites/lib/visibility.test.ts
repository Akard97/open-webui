import { describe, expect, it } from 'vitest';
import { canSeeSites } from './visibility';

describe('canSeeSites', () => {
	it.each([
		[{ user: { role: 'admin' } }, true],
		[{ user: { role: 'user', permissions: { features: { site_publisher: true } } } }, true],
		[{ user: { role: 'user', permissions: { features: { site_publisher: false } } } }, false],
		[{ user: { role: 'user', permissions: { features: {} } } }, false],
		[{ user: { role: 'user' } }, false],
		[{ user: undefined }, false]
	])('%j -> %s', (ctx, expected) => {
		expect(canSeeSites(ctx as any)).toBe(expected);
	});
});
