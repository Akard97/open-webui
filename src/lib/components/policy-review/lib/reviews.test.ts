import { describe, it, expect } from 'vitest';
import { buildActiveVersion, buildSeedReviews } from './seed';
import { versionFor, summarizeReview, REVIEW_STATUS_META } from './reviews';

const versions = [buildActiveVersion()];
const reviews = buildSeedReviews();
const byId = (id: string) => reviews.find((r) => r.id === id)!;

describe('versionFor', () => {
	it('resolves the snapshot version a review was created against', () => {
		const v = versionFor(byId('rev-active'), versions);
		expect(v?.id).toBe('v2.0');
	});
	it('falls back to the active version when the snapshot id is unknown', () => {
		const v = versionFor({ ...byId('rev-active'), checklistVersionId: 'nope' }, versions);
		expect(v?.status).toBe('active');
	});
});

describe('summarizeReview', () => {
	it('reports a numeric score and verdict for a fully-answered review', () => {
		const s = summarizeReview(byId('rev-pending-1'), versions[0]);
		expect(typeof s.overall).toBe('number');
		expect(s.open).toBe(0); // pending review has no unresolved items
		expect(['approved', 'conditional', 'rejected']).toContain(s.verdictKey);
	});
	it('counts unresolved (human + pending) items as open for an in-progress review', () => {
		const s = summarizeReview(byId('rev-active'), versions[0]);
		expect(s.open).toBeGreaterThan(0);
		expect(s.verdictKey).toBe('draft');
	});
});

describe('REVIEW_STATUS_META', () => {
	it('has an entry for every review status', () => {
		['draft', 'pending', 'approved', 'rejected'].forEach((k) => {
			expect(REVIEW_STATUS_META[k as keyof typeof REVIEW_STATUS_META]).toBeTruthy();
		});
	});
});
