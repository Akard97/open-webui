import { describe, it, expect } from 'vitest';
import { computeSortKey, resolveRename, SORT_SPACING } from './subtaskPanel';

const row = (id: string, sort_key: number) => ({ id, sort_key });

describe('computeSortKey', () => {
	const list = [row('a', 1000), row('b', 2000), row('c', 3000), row('d', 4000)];

	it('returns [] when fromIndex === toIndex', () => {
		expect(computeSortKey(list, 1, 1)).toEqual([]);
	});

	it('returns [] for out-of-range indices', () => {
		expect(computeSortKey(list, -1, 2)).toEqual([]);
		expect(computeSortKey(list, 0, 4)).toEqual([]);
		expect(computeSortKey([], 0, 0)).toEqual([]);
	});

	it('moves between neighbors via midpoint', () => {
		// move d (idx 3) to final idx 1 → between a(1000) and b(2000)
		expect(computeSortKey(list, 3, 1)).toEqual([{ id: 'd', sort_key: 1500 }]);
	});

	it('moves to top via first − SORT_SPACING', () => {
		expect(computeSortKey(list, 2, 0)).toEqual([{ id: 'c', sort_key: 1000 - SORT_SPACING }]);
	});

	it('moves to bottom via last + SORT_SPACING', () => {
		expect(computeSortKey(list, 0, 3)).toEqual([{ id: 'a', sort_key: 4000 + SORT_SPACING }]);
	});

	it('swaps a two-item list', () => {
		const two = [row('a', 1000), row('b', 2000)];
		expect(computeSortKey(two, 0, 1)).toEqual([{ id: 'a', sort_key: 2000 + SORT_SPACING }]);
		expect(computeSortKey(two, 1, 0)).toEqual([{ id: 'b', sort_key: 1000 - SORT_SPACING }]);
	});

	it('adjacent move down lands between the next pair', () => {
		// move a (idx 0) to final idx 1 → between b(2000) and c(3000)
		expect(computeSortKey(list, 0, 1)).toEqual([{ id: 'a', sort_key: 2500 }]);
	});

	it('renumbers the whole list when the midpoint degenerates', () => {
		// b and c share a key → midpoint equals both → not strictly between
		const tight = [row('a', 1000), row('b', 2000), row('c', 2000), row('d', 4000)];
		// move d to final idx 2 → between b(2000) and c(2000) → renumber
		expect(computeSortKey(tight, 3, 2)).toEqual([
			{ id: 'a', sort_key: 1 * SORT_SPACING },
			{ id: 'b', sort_key: 2 * SORT_SPACING },
			{ id: 'd', sort_key: 3 * SORT_SPACING },
			{ id: 'c', sort_key: 4 * SORT_SPACING }
		]);
	});

	it('does not mutate the input list', () => {
		const input = [row('a', 1000), row('b', 2000)];
		computeSortKey(input, 0, 1);
		expect(input).toEqual([row('a', 1000), row('b', 2000)]);
	});
});

describe('resolveRename', () => {
	it('commits a changed, trimmed title', () => {
		expect(resolveRename('Old', '  New title  ')).toEqual({ action: 'commit', title: 'New title' });
	});
	it('reverts when the draft is empty or whitespace-only', () => {
		expect(resolveRename('Old', '')).toEqual({ action: 'revert' });
		expect(resolveRename('Old', '   ')).toEqual({ action: 'revert' });
	});
	it('reverts when the trimmed draft is unchanged', () => {
		expect(resolveRename('Same', ' Same ')).toEqual({ action: 'revert' });
	});
});
