import { describe, it, expect } from 'vitest';
import { midpoint, needsRebalance, rebalance, parseKey } from './key';

describe('ordering helpers', () => {
	it('midpoint between two keys', () => {
		expect(midpoint(10, 20)).toBe(15);
	});
	it('midpoint at the top (no before)', () => {
		expect(midpoint(null, 20)).toBe(10);
	});
	it('midpoint at the bottom (no after)', () => {
		expect(midpoint(10, null)).toBe(1010);
	});
	it('midpoint of empty column', () => {
		expect(midpoint(null, null)).toBe(1000);
	});
	it('flags rebalance when neighbors converge', () => {
		expect(needsRebalance([1, 1.0000001])).toBe(true);
		expect(needsRebalance([1, 2, 3])).toBe(false);
	});
	it('rebalance produces evenly spaced ascending keys', () => {
		expect(rebalance(3)).toEqual([1000, 2000, 3000]);
	});
	it('parseKey splits prefix and number', () => {
		expect(parseKey('OSL-2841')).toEqual({ prefix: 'OSL', number: 2841 });
		expect(parseKey('nope')).toBeNull();
	});
});
