import { describe, expect, it } from 'vitest';
import { nextSelection } from './selection';

const s = (id: string) => ({ id });

describe('nextSelection', () => {
	it('selects the item that takes the removed slot', () => {
		expect(nextSelection([s('a'), s('b'), s('c')], 'b')).toBe('c');
	});
	it('selects previous when removing the last item', () => {
		expect(nextSelection([s('a'), s('b')], 'b')).toBe('a');
	});
	it('returns null when removing the only item', () => {
		expect(nextSelection([s('a')], 'a')).toBeNull();
	});
	it('returns first id when removedId not found', () => {
		expect(nextSelection([s('a'), s('b')], 'zz')).toBe('a');
	});
	it('returns null for empty list', () => {
		expect(nextSelection([], 'a')).toBeNull();
	});
});
