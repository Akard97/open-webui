import { describe, it, expect } from 'vitest';
import { get } from 'svelte/store';
import type { LibraryPolicy } from './types';
import {
	policyPopupOpen,
	selectedPolicy,
	openPolicyPopup,
	closePolicyPopup
} from './store';
import { isFresh, filterPolicies, groupByFunctionDesc, recentlyUpdated } from './library';
import { POLICIES, FN_META } from './seed';

describe('LibraryPolicy extension', () => {
	it('accepts the new optional library fields', () => {
		const p: LibraryPolicy = {
			code: 'POL-TEST-001',
			title: 'Test',
			fn: 'FIN',
			owner: 'Tester',
			version: '1.0',
			status: 'approved',
			score: null,
			pages: 1,
			nextReview: '—',
			updatedDays: 0,
			// New optional fields:
			summary: 'Short test summary.',
			outline: ['1. Scope', '2. Definitions'],
			effectiveDate: '2026-01-01',
			related: ['POL-FIN-009']
		};
		expect(p.summary).toBe('Short test summary.');
		expect(p.outline?.length).toBe(2);
		expect(p.effectiveDate).toBe('2026-01-01');
		expect(p.related?.length).toBe(1);
	});
});

describe('policy popup store', () => {
	const sample = (code: string, fn: string): LibraryPolicy => ({
		code,
		title: 'X',
		fn,
		owner: 'O',
		version: '1.0',
		status: 'approved',
		score: null,
		pages: 1,
		nextReview: '—',
		updatedDays: 0
	});

	it('openPolicyPopup sets both stores', () => {
		openPolicyPopup(sample('POL-X-001', 'FIN'));
		expect(get(policyPopupOpen)).toBe(true);
		expect(get(selectedPolicy)?.code).toBe('POL-X-001');
	});

	it('closePolicyPopup only flips open flag', () => {
		openPolicyPopup(sample('POL-X-002', 'HR'));
		closePolicyPopup();
		expect(get(policyPopupOpen)).toBe(false);
		expect(get(selectedPolicy)?.code).toBe('POL-X-002');
	});
});

describe('isFresh', () => {
	it('returns true for null-safe boundaries', () => {
		expect(isFresh(0)).toBe(true);
		expect(isFresh(7)).toBe(true);
		expect(isFresh(8)).toBe(false);
		expect(isFresh(null)).toBe(false);
		expect(isFresh(undefined as unknown as number)).toBe(false);
	});
});

describe('filterPolicies', () => {
	const approved = POLICIES.filter((p) => p.status === 'approved');

	it('returns all approved policies on empty filters', () => {
		const r = filterPolicies(approved, { query: '', fn: 'all' });
		expect(r.length).toBe(approved.length);
	});

	it('filters by function', () => {
		const r = filterPolicies(approved, { query: '', fn: 'HR' });
		expect(r.every((p) => p.fn === 'HR')).toBe(true);
	});

	it('matches title case-insensitively', () => {
		const r = filterPolicies(approved, { query: 'risk', fn: 'all' });
		expect(r.some((p) => p.title.toLowerCase().includes('risk'))).toBe(true);
	});

	it('matches document code', () => {
		const r = filterPolicies(approved, { query: 'OSOOL-FIN-POL-007', fn: 'all' });
		expect(r.length).toBe(1);
		expect(r[0].code).toBe('OSOOL-FIN-POL-007');
	});

	it('matches owner name', () => {
		const r = filterPolicies(approved, { query: 'Al-Saqer', fn: 'all' });
		expect(r.some((p) => p.owner.includes('Al-Saqer'))).toBe(true);
	});

	it('combines function + query (AND)', () => {
		const r = filterPolicies(approved, { query: 'risk', fn: 'RM' });
		expect(r.every((p) => p.fn === 'RM' && p.title.toLowerCase().includes('risk'))).toBe(true);
	});
});

describe('groupByFunctionDesc', () => {
	const approved = POLICIES.filter((p) => p.status === 'approved');

	it('groups policies under their function key', () => {
		const groups = groupByFunctionDesc(approved, FN_META);
		const fin = groups.find((g) => g.fn === 'FIN');
		expect(fin?.policies.every((p) => p.fn === 'FIN')).toBe(true);
	});

	it('sorts groups by policy count desc', () => {
		const groups = groupByFunctionDesc(approved, FN_META);
		for (let i = 1; i < groups.length; i++) {
			expect(groups[i].policies.length).toBeLessThanOrEqual(groups[i - 1].policies.length);
		}
	});

	it('does not include empty groups', () => {
		const groups = groupByFunctionDesc([], FN_META);
		expect(groups.length).toBe(0);
	});

	it('sorts policies within a group by updatedDays asc (fresh first)', () => {
		const groups = groupByFunctionDesc(approved, FN_META);
		for (const g of groups) {
			for (let i = 1; i < g.policies.length; i++) {
				const a = g.policies[i - 1].updatedDays ?? 99999;
				const b = g.policies[i].updatedDays ?? 99999;
				expect(b).toBeGreaterThanOrEqual(a);
			}
		}
	});
});

describe('recentlyUpdated', () => {
	const approved = POLICIES.filter((p) => p.status === 'approved');

	it('returns top N sorted by updatedDays asc', () => {
		const top = recentlyUpdated(approved, 4, 30);
		expect(top.length).toBe(4);
		for (let i = 1; i < top.length; i++) {
			const a = top[i - 1].updatedDays ?? 99999;
			const b = top[i].updatedDays ?? 99999;
			expect(b).toBeGreaterThanOrEqual(a);
		}
	});

	it('falls back to top N regardless of window when fewer-than-N are inside window', () => {
		// Empty-window scenario simulated with a strict 0-day window.
		const top = recentlyUpdated(approved, 4, 0);
		expect(top.length).toBe(4);
	});

	it('never returns more than N', () => {
		const top = recentlyUpdated(approved, 2, 30);
		expect(top.length).toBe(2);
	});
});
