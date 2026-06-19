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
		created_at: 1767225600000000000, // 2026-01-01T00:00:00Z in nanoseconds
		...over
	};
}

vi.mock('./api', () => ({
	getActiveChecklist: vi.fn(),
	getMyReviews: vi.fn(async () => []),
	getApprovalQueue: vi.fn(async () => []),
	getLibrary: vi.fn(async () => []),
	createReviewApi: vi.fn(async () => backendReview()),
	replaceReviewDocumentApi: vi.fn(async (_t: unknown, id: string) => backendReview({ id, status: 'draft' })),
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
	discardChecklistDraft: vi.fn(async () => ({ success: true })),
	getChecklistVersions: vi.fn(async () => []),
	deleteReviewApi: vi.fn(async () => ({ success: true })),
	deleteLibraryApi: vi.fn(async () => ({ success: true })),
	activateVersionApi: vi.fn(async (_t, id) => ({ id, label: 'v2.0', status: 'active', data: {} }))
}));

import {
	reviews,
	activeReviewId,
	activeReview,
	approvalQueue,
	checklistVersions,
	libraryEntries,
	view,
	stage,
	openReview,
	goNewReview,
	createReview,
	replaceDocument,
	updateItemResult,
	submitForApproval,
	deleteReview,
	unpublishPolicy,
	reactivateVersion
} from './store';
import * as api from './api';

function review(over: Record<string, unknown> = {}) {
	return {
		id: 'rev-1',
		policyMeta: {} as never,
		checklistVersionId: 'v2.0',
		results: {},
		status: 'draft' as const,
		approval: { status: 'idle' as const, sentAt: null, decidedAt: null, decidedBy: null, note: '' },
		strengths: [],
		createdBy: 'Test Reviewer',
		createdAt: '',
		...over
	};
}

beforeEach(() => {
	reviews.set([]);
	activeReviewId.set(null);
	checklistVersions.set([]);
	libraryEntries.set([]);
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
		const file = new File([new Uint8Array([1, 2, 3])], 'policy.pdf', { type: 'application/pdf' });
		const created = await createReview(
			{
				name: 'Test Policy',
				code: 'POL-1',
				version: 'v1.0',
				owner: 'OE',
				reviewer: 'Rev',
				reviewDate: '2026-01-01',
				pages: 4,
				filename: ''
			},
			file
		);
		expect(api.createReviewApi).toHaveBeenCalledOnce();
		// The selected file must be forwarded to the api (3rd arg).
		expect((api.createReviewApi as unknown as { mock: { calls: unknown[][] } }).mock.calls[0][2]).toBe(file);
		// Backend snake_case is mapped to the frontend Review shape.
		expect(created.policyMeta.code).toBe('POL-1');
		expect(created.createdBy).toBe('Test Reviewer');
		// ns timestamp must be formatted as a readable date, not a raw integer.
		expect(created.createdAt).toBe(
			new Date(1767225600000000000 / 1e6).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
		);
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
		// The reviewer's note must be forwarded to the api, not dropped.
		expect(api.submitReviewApi).toHaveBeenCalledWith('', 'rev-1', 'please review');
		expect(get(activeReview)!.status).toBe('pending');
		expect(get(approvalQueue).some((r) => r.id === 'rev-1')).toBe(true);
	});

	it('replaceDocument forwards the file and updates the review from the response', async () => {
		reviews.set([
			{
				id: 'rev-1',
				policyMeta: {} as never,
				checklistVersionId: 'v2.0',
				results: {},
				status: 'rejected',
				approval: { status: 'rejected', sentAt: null, decidedAt: null, decidedBy: 'A', note: 'fix' },
				strengths: [],
				createdBy: 'Test Reviewer',
				createdAt: ''
			}
		]);
		const file = new File([new Uint8Array([9])], 'fixed.pdf', { type: 'application/pdf' });
		await replaceDocument('rev-1', file);
		expect(api.replaceReviewDocumentApi).toHaveBeenCalledWith('', 'rev-1', file);
		expect(get(reviews).find((r) => r.id === 'rev-1')!.status).toBe('draft');
	});
});

describe('delete / unpublish / re-activate mutators', () => {
	it('deleteReview removes the review from the store and clears the active selection', async () => {
		reviews.set([review({ id: 'rev-1' }), review({ id: 'rev-2' })]);
		activeReviewId.set('rev-1');
		await deleteReview('rev-1');
		expect(api.deleteReviewApi).toHaveBeenCalledWith('', 'rev-1');
		expect(get(reviews).some((r) => r.id === 'rev-1')).toBe(false);
		expect(get(reviews).some((r) => r.id === 'rev-2')).toBe(true);
		// The deleted review was active, so the selection is cleared.
		expect(get(activeReviewId)).toBe(null);
	});

	it('deleteReview leaves the active selection alone when a different review is deleted', async () => {
		reviews.set([review({ id: 'rev-1' }), review({ id: 'rev-2' })]);
		activeReviewId.set('rev-2');
		await deleteReview('rev-1');
		expect(get(activeReviewId)).toBe('rev-2');
	});

	it('unpublishPolicy calls the api then reloads the library from the source of truth', async () => {
		await unpublishPolicy('POL-1');
		expect(api.deleteLibraryApi).toHaveBeenCalledWith('', 'POL-1');
		// loadLibrary() re-fetches so publishedPolicies reflects the removal.
		expect(api.getLibrary).toHaveBeenCalledOnce();
	});

	it('reactivateVersion marks the returned version active and archives the rest', async () => {
		checklistVersions.set([
			{ id: 'ver-21', label: 'v2.1', status: 'active' } as never,
			{ id: 'ver-20', label: 'v2.0', status: 'archived' } as never
		]);
		await reactivateVersion('ver-20');
		expect(api.activateVersionApi).toHaveBeenCalledWith('', 'ver-20');
		const vs = get(checklistVersions);
		expect(vs.find((v) => v.status === 'active')!.id).toBe('ver-20');
		expect(vs.find((v) => v.id === 'ver-21')!.status).toBe('archived');
	});
});
