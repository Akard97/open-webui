import { describe, it, expect, beforeEach } from 'vitest';
import { get } from 'svelte/store';
import {
	reviews,
	activeReviewId,
	activeReview,
	approvalQueue,
	updateItemResult,
	submitForApproval,
	approveAndPublish,
	rejectPolicy,
	startDraft,
	publishDraft,
	checklistVersions,
	checklistDraft
} from './store';
import { buildSeedReviews, buildActiveVersion } from './seed';

beforeEach(() => {
	reviews.set(buildSeedReviews());
	activeReviewId.set('rev-active');
	checklistVersions.set([]);
	checklistDraft.set(null);
});

describe('review mutators', () => {
	it('updateItemResult patches a single item result', () => {
		updateItemResult('rev-active', 'PRP1-1', { result: 'non-compliant', edited: true });
		expect(get(activeReview)!.results['PRP1-1'].result).toBe('non-compliant');
		expect(get(activeReview)!.results['PRP1-1'].edited).toBe(true);
	});

	it('submitForApproval moves a review into the queue as pending', () => {
		submitForApproval('rev-active', 'please review');
		expect(get(activeReview)!.status).toBe('pending');
		expect(get(approvalQueue).some((r) => r.id === 'rev-active')).toBe(true);
	});

	it('approveAndPublish marks approved and records a decider', () => {
		submitForApproval('rev-active', 'x');
		approveAndPublish('rev-active', 'looks good');
		const r = get(reviews).find((x) => x.id === 'rev-active')!;
		expect(r.status).toBe('approved');
		expect(r.approval.decidedBy).toBeTruthy();
	});

	it('rejectPolicy marks rejected with a note', () => {
		submitForApproval('rev-active', 'x');
		rejectPolicy('rev-active', 'fix gaps');
		expect(get(reviews).find((x) => x.id === 'rev-active')!.status).toBe('rejected');
	});
});

describe('checklist draft lifecycle', () => {
	it('publishDraft fails validation when weights are off', () => {
		checklistVersions.set([buildActiveVersion()]);
		startDraft();
		const d = get(checklistDraft)!;
		d.themes[0].weight += 10;
		checklistDraft.set(d);
		const r = publishDraft();
		expect(r.ok).toBe(false);
	});

	it('publishDraft appends a new active version on success', () => {
		checklistVersions.set([buildActiveVersion()]);
		startDraft();
		const r = publishDraft();
		expect(r.ok).toBe(true);
		const actives = get(checklistVersions).filter((v) => v.status === 'active');
		expect(actives).toHaveLength(1);
		expect(actives[0].label).toBe('v2.1');
	});
});
