import { describe, it, expect } from 'vitest';
import type { LibraryPolicy } from './types';

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
