import { describe, it, expect } from 'vitest';
import { get } from 'svelte/store';
import type { LibraryPolicy } from './types';
import {
	policyPopupOpen,
	selectedPolicy,
	openPolicyPopup,
	closePolicyPopup
} from './store';

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
