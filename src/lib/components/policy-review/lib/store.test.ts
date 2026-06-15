import { describe, it, expect, beforeEach, vi } from 'vitest';
import { get } from 'svelte/store';

// The store is now backed by the backend API (Phase 1). The obsolete
// localStorage mutators (resetReview + synchronous patch helpers) moved to
// backend coverage; here we mock ./api and assert the store maps responses and
// the pure navigation helpers behave.
//
// In the vitest node environment `browser` is false, so the store's token()
// helper returns '' (it never reads localStorage). Assertions below expect ''.

// Canned backend-shaped review (snake_case + snapshot). The mocked api
// functions echo this so we can assert the store maps it into Review shape.
function backendReview(over: Record<string, unknown> = {}) {
	return {
		id: 'rev-1',
		policy_meta: {
			name: 'Test Policy',
			code: 'POL-1',
			version: 'v1.0',
			owner: 'OE',
			reviewer: 'Rev',
			reviewDate: '2026-01-01',
			pages: 4,
			filename: ''
		},
		checklist_version_id: 'v2.0',
		results: {},
		status: 'draft',
		approval: { status: 'idle', sentAt: null, decidedAt: null, decidedBy: null, note: '' },
		strengths: [],
		created_by_name: 'Test Reviewer',
		created_at: '2026-01-01T00:00:00Z',
		...over
	};
}

vi.mock('./api', () => ({
	getActiveChecklist: vi.fn(),
	getMyReviews: vi.fn(async () => []),
	getApprovalQueue: vi.fn(async () => []),
	getLibrary: vi.fn(async () => []),
	createReviewApi: vi.fn(async () => backendReview()),
	updateResultsApi: vi.fn(async (_t, id, results) =>
		backendReview({ id, results: results as Record<string, unknown> })
	),
	submitReviewApi: vi.fn(async (_t, id) =>
		backendReview({
			id,
			status: 'pending',
			approval: { status: 'pending', sentAt: 'now', decidedAt: null, decidedBy: null, note: '' }
		})
	),
	approveReviewApi: vi.fn(async (_t, id) => backendReview({ id, status: 'approved' })),
	rejectReviewApi: vi.fn(async (_t, id) => backendReview({ id, status: 'rejected' })),
	startChecklistDraft: vi.fn(),
	publishChecklistDraft: vi.fn(),
	discardChecklistDraft: vi.fn(async () => ({ success: true }))
}));

import {
	reviews,
	activeReviewId,
	activeReview,
	approvalQueue,
	view,
	stage,
	openReview,
	goNewReview,
	createReview,
	updateItemResult,
	submitForApproval
} from './store';
import * as api from './api';

beforeEach(() => {
	reviews.set([]);
	activeReviewId.set(null);
	view.set('overview');
	stage.set('upload');
	vi.clearAllMocks();
});

describe('navigation helpers (pure, sync)', () => {
	it('openReview selects the review and routes to the workspace', () => {
		openReview('rev-pending-1');
		expect(get(activeReviewId)).toBe('rev-pending-1');
		expect(get(view)).toBe('review');
	});

	it('goNewReview clears the selection and shows an empty upload screen', () => {
		goNewReview();
		expect(get(view)).toBe('new-review');
		expect(get(stage)).toBe('upload');
		expect(get(activeReviewId)).toBe(null);
	});
});

describe('api-backed review mutators', () => {
	it('createReview calls the api and adds the mapped review, advancing to review stage', async () => {
		const created = await createReview({
			name: 'Test Policy',
			code: 'POL-1',
			version: 'v1.0',
			owner: 'OE',
			reviewer: 'Rev',
			reviewDate: '2026-01-01',
			pages: 4,
			filename: ''
		});
		expect(api.createReviewApi).toHaveBeenCalledOnce();
		// Backend snake_case is mapped to the frontend Review shape.
		expect(created.policyMeta.code).toBe('POL-1');
		expect(created.createdBy).toBe('Test Reviewer');
		expect(get(reviews).some((r) => r.id === created.id)).toBe(true);
		expect(get(activeReviewId)).toBe(created.id);
		expect(get(stage)).toBe('review');
	});

	it('updateItemResult calls the api and replaces the review from the mapped response', async () => {
		reviews.set([
			{
				id: 'rev-1',
				policyMeta: {} as never,
				checklistVersionId: 'v2.0',
				results: {},
				status: 'draft',
				approval: { status: 'idle', sentAt: null, decidedAt: null, decidedBy: null, note: '' },
				strengths: [],
				createdBy: 'Test Reviewer',
				createdAt: ''
			}
		]);
		await updateItemResult('rev-1', 'PRP1-1', { result: 'non-compliant', edited: true });
		expect(api.updateResultsApi).toHaveBeenCalledWith('', 'rev-1', {
			'PRP1-1': { result: 'non-compliant', edited: true }
		});
		const r = get(reviews).find((x) => x.id === 'rev-1')!;
		expect(r.results['PRP1-1'].result).toBe('non-compliant');
	});

	it('submitForApproval calls the api and moves the review into the queue as pending', async () => {
		reviews.set([
			{
				id: 'rev-1',
				policyMeta: {} as never,
				checklistVersionId: 'v2.0',
				results: {},
				status: 'draft',
				approval: { status: 'idle', sentAt: null, decidedAt: null, decidedBy: null, note: '' },
				strengths: [],
				createdBy: 'Test Reviewer',
				createdAt: ''
			}
		]);
		activeReviewId.set('rev-1');
		await submitForApproval('rev-1', 'please review');
		expect(api.submitReviewApi).toHaveBeenCalledWith('', 'rev-1');
		expect(get(activeReview)!.status).toBe('pending');
		expect(get(approvalQueue).some((r) => r.id === 'rev-1')).toBe(true);
	});
});
