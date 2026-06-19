import { describe, it, expect } from 'vitest';
import {
	resolveMode,
	isLocked,
	countResults,
	openCount,
	resolvedCount,
	itemNumber,
	topGaps,
	initOpenMap
} from './reviewView';
import type { ChecklistVersion, ItemResult, Theme } from './types';

const THEMES: Theme[] = [
	{ id: 'T1', name: 'Policy Foundation', weight: 28, gate: true, threshold: 85 },
	{ id: 'T2', name: 'Governance and Accountability', weight: 28, gate: true, threshold: 85 },
	{ id: 'T3', name: 'People and Communication', weight: 16, gate: false, threshold: 85 }
];

// Each section gets `count` items so we can exercise counts/gaps.
function version(specs: { theme: string; items: number }[]): ChecklistVersion {
	return {
		id: 'v',
		label: 'v',
		status: 'active',
		publishedAt: null,
		publishedBy: null,
		changeSummary: '',
		themes: THEMES,
		verdictBands: { approved: 85, conditional: 70 },
		standards: [],
		sections: specs.map((s, i) => ({
			id: `PRP${i + 1}`,
			theme: s.theme,
			title: `Section ${i + 1}`,
			codes: 'c',
			intent: 'i',
			items: Array.from({ length: s.items }, (_, k) => ({
				id: `PRP${i + 1}-${k + 1}`,
				n: k + 1,
				text: `Item ${i + 1}.${k + 1}`,
				codes: 'OEC',
				assessment: 'auto' as const
			}))
		}))
	};
}

const res = (pairs: Record<string, ItemResult['result']>): Record<string, ItemResult> =>
	Object.fromEntries(Object.entries(pairs).map(([k, v]) => [k, { result: v }]));

describe('resolveMode', () => {
	it('draft + checker → reviewer', () => expect(resolveMode('draft', true, false)).toBe('reviewer'));
	it('rejected + checker → reviewer', () => expect(resolveMode('rejected', true, false)).toBe('reviewer'));
	it('pending + approver → decide', () => expect(resolveMode('pending', false, true)).toBe('decide'));
	it('pending + checker (not approver) → readonly', () => expect(resolveMode('pending', true, false)).toBe('readonly'));
	it('approved + anyone → readonly', () => expect(resolveMode('approved', true, true)).toBe('readonly'));
	it('admin on draft (both gates) → reviewer', () => expect(resolveMode('draft', true, true)).toBe('reviewer'));
	it('admin on pending (both gates) → decide, not reviewer', () => expect(resolveMode('pending', true, true)).toBe('decide'));
});

describe('isLocked', () => {
	it('draft and rejected are editable', () => {
		expect(isLocked('draft')).toBe(false);
		expect(isLocked('rejected')).toBe(false);
	});
	it('pending and approved are locked', () => {
		expect(isLocked('pending')).toBe(true);
		expect(isLocked('approved')).toBe(true);
	});
});

describe('countResults / openCount / resolvedCount', () => {
	const v = version([{ theme: 'T1', items: 2 }, { theme: 'T2', items: 2 }]);
	const c = countResults(
		v,
		res({ 'PRP1-1': 'compliant', 'PRP1-2': 'non-compliant', 'PRP2-1': 'human' })
	); // PRP2-2 missing → pending

	it('tallies every bucket and total', () => {
		expect(c).toEqual({ compliant: 1, 'non-compliant': 1, human: 1, pending: 1, total: 4 });
	});
	it('openCount = human + pending', () => expect(openCount(c)).toBe(2));
	it('resolvedCount = compliant + non-compliant', () => expect(resolvedCount(c)).toBe(2));
});

describe('itemNumber', () => {
	it('strips the PRP prefix and joins with n', () => {
		expect(itemNumber('PRP1', 2)).toBe('1.2');
		expect(itemNumber('PRP12', 3)).toBe('12.3');
	});
});

describe('topGaps', () => {
	it('returns non-compliant items, sorted by theme rank, with stripped ref', () => {
		const v = version([{ theme: 'T3', items: 1 }, { theme: 'T1', items: 1 }]);
		const gaps = topGaps(v, res({ 'PRP1-1': 'non-compliant', 'PRP2-1': 'non-compliant' }));
		expect(gaps.map((g) => g.theme)).toEqual(['T1', 'T3']); // PRP2 is T1 → first
		expect(gaps[0]).toMatchObject({ ref: '2.1', theme: 'T1', sectionId: 'PRP2', n: 1 });
	});
	it('honours the limit', () => {
		const v = version([{ theme: 'T1', items: 6 }]);
		const all = Object.fromEntries(Array.from({ length: 6 }, (_, k) => [`PRP1-${k + 1}`, 'non-compliant']));
		expect(topGaps(v, res(all as Record<string, ItemResult['result']>)).length).toBe(5);
	});
});

describe('initOpenMap', () => {
	it('starts every section collapsed', () => {
		const v = version([{ theme: 'T1', items: 1 }, { theme: 'T2', items: 1 }]);
		expect(initOpenMap(v)).toEqual({ PRP1: false, PRP2: false });
	});
	it('can open all when asked', () => {
		const v = version([{ theme: 'T1', items: 1 }]);
		expect(initOpenMap(v, true)).toEqual({ PRP1: true });
	});
});
