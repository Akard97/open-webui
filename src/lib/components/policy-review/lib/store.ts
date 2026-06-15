// Writable stores backing the Policy Review tool.
// Two aggregate roots: the versioned checklist definition and per-policy reviews.
// localStorage persistence keeps in-flight work across refreshes.

import { writable, get, derived, type Writable } from 'svelte/store';
import { browser } from '$app/environment';
import {
	buildActiveVersion,
	buildSeedReviews,
	POLICIES
} from './seed';
import { cloneAsDraft, publishDraft as publishDraftPure, validateDraft } from './checklist';
import type {
	ChecklistVersion,
	ItemResult,
	LibraryPolicy,
	Review,
	Stage,
	ViewKey
} from './types';
import { user } from '$lib/stores';

const STORAGE_KEY = 'osool.policyReview.v3';

interface PersistedState {
	versions: ChecklistVersion[];
	draft: ChecklistVersion | null;
	reviews: Review[];
	activeReviewId: string | null;
	stage: Stage;
	view: ViewKey;
}

function freshInitial(): PersistedState {
	const reviews = buildSeedReviews();
	return {
		versions: [buildActiveVersion()],
		draft: null,
		reviews,
		activeReviewId: reviews[0]?.id ?? null,
		stage: 'review',
		view: 'overview'
	};
}

function loadInitial(): PersistedState {
	if (!browser) return freshInitial();
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (raw) {
			const parsed = JSON.parse(raw) as Partial<PersistedState>;
			const fresh = freshInitial();
			return {
				versions: parsed.versions ?? fresh.versions,
				draft: parsed.draft ?? null,
				reviews: parsed.reviews ?? fresh.reviews,
				activeReviewId: parsed.activeReviewId ?? fresh.activeReviewId,
				stage: parsed.stage ?? 'review',
				view: (
					['overview', 'library', 'new-review', 'my-reviews', 'approvals', 'review', 'admin'] as const
				).includes(parsed.view as ViewKey)
					? (parsed.view as ViewKey)
					: 'overview',
			};
		}
	} catch {
		// Corrupt storage — fall back to fresh state.
	}
	return freshInitial();
}

const initial = loadInitial();

export const checklistVersions: Writable<ChecklistVersion[]> = writable(initial.versions);
export const checklistDraft: Writable<ChecklistVersion | null> = writable(initial.draft);
export const reviews: Writable<Review[]> = writable(initial.reviews);
export const activeReviewId: Writable<string | null> = writable(initial.activeReviewId);
export const stage: Writable<Stage> = writable(initial.stage);
export const view: Writable<ViewKey> = writable(initial.view);

// ─── Derived: checklist + reviews ──────────────────────────────────────────

export const activeVersion = derived(checklistVersions, ($v) => {
	return $v.find((x) => x.status === 'active') ?? $v[0];
});

export const activeReview = derived([reviews, activeReviewId], ([$r, $id]) =>
	$r.find((x) => x.id === $id) ?? null
);

export const approvalQueue = derived(reviews, ($r) => $r.filter((x) => x.status === 'pending'));

export const myReviews = derived([reviews, user], ([$r, $u]) =>
	$r.filter((x) => x.createdBy === ($u?.name ?? ''))
);

// Published canon = seeded library + any review that reached approved.
export const publishedPolicies = derived(reviews, ($r): LibraryPolicy[] => {
	const approvedCodes = new Set($r.filter((x) => x.status === 'approved').map((x) => x.policyMeta.code));
	const extra: LibraryPolicy[] = $r
		.filter((x) => x.status === 'approved' && !POLICIES.some((p) => p.code === x.policyMeta.code))
		.map((x) => ({
			code: x.policyMeta.code,
			title: x.policyMeta.name,
			fn: x.policyMeta.code.split('-')[1] ?? 'GOV',
			owner: x.policyMeta.owner,
			version: x.policyMeta.version.replace(/^v/, ''),
			status: 'approved',
			score: null,
			pages: x.policyMeta.pages,
			nextReview: '—',
			updatedDays: 0
		}));
	const merged = POLICIES.map((p) =>
		approvedCodes.has(p.code) ? { ...p, status: 'approved' as const } : p
	);
	return [...merged, ...extra];
});

// ─── Access gates ──────────────────────────────────────────────────────────

export const canUseChecker = derived(
	user,
	($u) => $u?.role === 'admin' || ($u?.permissions?.features?.policy_checker ?? false)
);

export const canApprove = derived(
	user,
	($u) => $u?.role === 'admin' || ($u?.permissions?.features?.policy_approver ?? false)
);

export const canAdmin = derived(
	user,
	($u) => $u?.role === 'admin' || ($u?.permissions?.features?.policy_admin ?? false)
);

// ─── Transient UI (not persisted) ──────────────────────────────────────────

export const picked: Writable<{ sectionId: string; n: number } | null> = writable(null);
export const drawerOpen: Writable<boolean> = writable(false);
export const submitModalOpen: Writable<boolean> = writable(false);
export const policyPopupOpen: Writable<boolean> = writable(false);
export const selectedPolicy: Writable<LibraryPolicy | null> = writable(null);

if (browser) {
	const persist = () => {
		const snapshot: PersistedState = {
			versions: get(checklistVersions),
			draft: get(checklistDraft),
			reviews: get(reviews),
			activeReviewId: get(activeReviewId),
			stage: get(stage),
			view: get(view)
		};
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
		} catch {
			// Quota errors etc. are non-fatal.
		}
	};
	checklistVersions.subscribe(persist);
	checklistDraft.subscribe(persist);
	reviews.subscribe(persist);
	activeReviewId.subscribe(persist);
	stage.subscribe(persist);
	view.subscribe(persist);
}

// ─── Helpers ────────────────────────────────────────────────────────────────

function stamp(): string {
	return new Date().toLocaleString('en-GB', {
		day: '2-digit',
		month: 'short',
		hour: '2-digit',
		minute: '2-digit'
	});
}

function patchReview(reviewId: string, fn: (r: Review) => Review): void {
	reviews.update((arr) => arr.map((r) => (r.id === reviewId ? fn(r) : r)));
}

// ─── Review mutators ─────────────────────────────────────────────────────────

export function updateItemResult(reviewId: string, itemId: string, patch: Partial<ItemResult>): void {
	patchReview(reviewId, (r) => ({
		...r,
		results: {
			...r.results,
			[itemId]: { ...(r.results[itemId] ?? { result: 'pending' }), ...patch }
		}
	}));
}

export function markReviewed(reviewId: string, itemId: string): void {
	updateItemResult(reviewId, itemId, { reviewed: true, confidence: 0.99 });
}

// Reset the active review back to a fresh draft of the seeded "active" review.
// (Plan 2 replaces this with real createReview() from an upload.)
export function resetReview(): void {
	const seeded = buildSeedReviews();
	const me = get(user)?.name;
	const fresh = me ? { ...seeded[0], createdBy: me } : seeded[0];
	reviews.update((arr) => arr.map((r) => (r.id === 'rev-active' ? fresh : r)));
	activeReviewId.set('rev-active');
	stage.set('upload');
}

// Open an existing review in the workspace (used by My reviews + Approval queue).
export function openReview(id: string): void {
	activeReviewId.set(id);
	view.set('review');
}

// Start the new-review wizard from a fresh draft.
export function goNewReview(): void {
	resetReview(); // fresh rev-active, stage = 'upload', activeReviewId = 'rev-active'
	view.set('new-review');
}

export function submitForApproval(reviewId: string, note: string): void {
	patchReview(reviewId, (r) => ({
		...r,
		status: 'pending',
		approval: { status: 'pending', sentAt: stamp(), decidedAt: null, decidedBy: null, note }
	}));
}

const DEFAULT_APPROVE_NOTE = 'Approved for issuance and published to the policy library.';
const DEFAULT_REJECT_NOTE =
	'Rejected — policy must be revised and re-reviewed before it can be resubmitted.';

export function approveAndPublish(reviewId: string, note?: string): void {
	const by = get(user)?.name ?? 'OE Approver';
	patchReview(reviewId, (r) => ({
		...r,
		status: 'approved',
		approval: {
			...r.approval,
			status: 'approved',
			decidedAt: stamp(),
			decidedBy: by,
			note: note?.trim() || DEFAULT_APPROVE_NOTE
		}
	}));
}

export function rejectPolicy(reviewId: string, note?: string): void {
	const by = get(user)?.name ?? 'OE Approver';
	patchReview(reviewId, (r) => ({
		...r,
		status: 'rejected',
		approval: {
			...r.approval,
			status: 'rejected',
			decidedAt: stamp(),
			decidedBy: by,
			note: note?.trim() || DEFAULT_REJECT_NOTE
		}
	}));
}

// ─── Checklist draft mutators (UI lands in Plan 3) ──────────────────────────

export function startDraft(): void {
	const active = get(activeVersion);
	if (active) checklistDraft.set(cloneAsDraft(active));
}

export function discardDraft(): void {
	checklistDraft.set(null);
}

export function publishDraft(): { ok: boolean; errors: string[] } {
	const draft = get(checklistDraft);
	if (!draft) return { ok: false, errors: ['No draft to publish.'] };
	const validation = validateDraft(draft);
	if (!validation.ok) return validation;
	const by = get(user)?.name ?? 'Policy Admin';
	const { versions } = publishDraftPure(get(checklistVersions), draft, by, stamp());
	checklistVersions.set(versions);
	checklistDraft.set(null);
	return { ok: true, errors: [] };
}

// ─── Policy Library popup helpers ──────────────────────────────────────────

export function openPolicyPopup(policy: LibraryPolicy): void {
	selectedPolicy.set(policy);
	policyPopupOpen.set(true);
}

export function closePolicyPopup(): void {
	policyPopupOpen.set(false);
}
