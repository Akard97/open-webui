// API-backed stores for the Policy Review tool (Phase 1 backend).
// Public store/mutator names are unchanged so views need no edits.

import { writable, get, derived, type Writable } from 'svelte/store';
import { browser } from '$app/environment';
import type {
	ChecklistVersion,
	ItemResult,
	LibraryPolicy,
	Review,
	Stage,
	ViewKey
} from './types';
import { user } from '$lib/stores';
import * as api from './api';

function token(): string {
	return browser ? localStorage.token : '';
}

// Map a backend review (snake_case + snapshot) to the frontend Review shape.
function mapReview(r: any): Review {
	return {
		id: r.id,
		policyMeta: r.policy_meta,
		checklistVersionId: r.checklist_version_id,
		checklistSnapshot: r.checklist_snapshot
			? ({ ...r.checklist_snapshot, id: r.checklist_version_id, status: 'archived' } as ChecklistVersion)
			: undefined,
		results: r.results ?? {},
		status: r.status,
		approval: r.approval ?? { status: 'idle', sentAt: null, decidedAt: null, decidedBy: null, note: '' },
		strengths: r.strengths ?? [],
		createdBy: r.created_by_name,
		createdAt: r.created_at
			? new Date(r.created_at / 1e6).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
			: ''
	};
}

function mapVersion(v: any): ChecklistVersion {
	const d = v.data ?? {};
	return {
		id: v.id,
		label: v.label,
		status: v.status,
		publishedAt: v.published_at
			? new Date(v.published_at / 1e6).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
			: null,
		publishedBy: v.published_by_name ?? null,
		changeSummary: d.changeSummary ?? '',
		themes: d.themes ?? [],
		sections: d.sections ?? [],
		verdictBands: d.verdictBands ?? { approved: 85, conditional: 70 },
		standards: d.standards ?? []
	};
}

// ── Stores ──
export const checklistVersions: Writable<ChecklistVersion[]> = writable([]);
export const checklistDraft: Writable<ChecklistVersion | null> = writable(null);
export const reviews: Writable<Review[]> = writable([]);
export const activeReviewId: Writable<string | null> = writable(null);
export const stage: Writable<Stage> = writable('upload');
export const view: Writable<ViewKey> = writable('overview');
export const libraryEntries: Writable<LibraryPolicy[]> = writable([]);

// ── Derived ──
export const activeVersion = derived(checklistVersions, ($v) => $v.find((x) => x.status === 'active') ?? $v[0]);
export const activeReview = derived([reviews, activeReviewId], ([$r, $id]) => $r.find((x) => x.id === $id) ?? null);
export const approvalQueue = derived(reviews, ($r) => $r.filter((x) => x.status === 'pending'));
export const myReviews = derived([reviews, user], ([$r, $u]) => $r.filter((x) => x.createdBy === ($u?.name ?? '')));
export const publishedPolicies = derived(libraryEntries, ($l) => $l);

// ── Access gates (unchanged) ──
export const canUseChecker = derived(user, ($u) => $u?.role === 'admin' || ($u?.permissions?.features?.policy_checker ?? false));
export const canApprove = derived(user, ($u) => $u?.role === 'admin' || ($u?.permissions?.features?.policy_approver ?? false));
export const canAdmin = derived(user, ($u) => $u?.role === 'admin' || ($u?.permissions?.features?.policy_admin ?? false));

// ── Transient UI (not persisted) ──
export const picked: Writable<{ sectionId: string; n: number } | null> = writable(null);
export const drawerOpen: Writable<boolean> = writable(false);
export const submitModalOpen: Writable<boolean> = writable(false);
export const policyPopupOpen: Writable<boolean> = writable(false);
export const selectedPolicy: Writable<LibraryPolicy | null> = writable(null);

// ── Loaders ──
export async function loadChecklist(): Promise<void> {
	const active = await api.getActiveChecklist(token());
	checklistVersions.set([mapVersion(active)]);
}

export async function loadReviews(): Promise<void> {
	const mine = (await api.getMyReviews(token()).catch(() => [])) ?? [];
	let queue: any[] = [];
	if (get(canApprove)) queue = (await api.getApprovalQueue(token()).catch(() => [])) ?? [];
	const byId = new Map<string, Review>();
	[...mine, ...queue].forEach((r) => byId.set(r.id, mapReview(r)));
	reviews.set([...byId.values()]);
}

export async function loadLibrary(): Promise<void> {
	const entries = (await api.getLibrary(token()).catch(() => [])) ?? [];
	libraryEntries.set(entries.map((e: any) => e.data as LibraryPolicy));
}

export async function loadAll(): Promise<void> {
	await Promise.all([loadChecklist(), loadLibrary()]);
	if (get(canUseChecker) || get(canApprove)) await loadReviews();
	if (get(canAdmin)) await loadDraft();
}

// ── Review mutators ──
export async function updateItemResult(reviewId: string, itemId: string, patch: Partial<ItemResult>): Promise<void> {
	const updated = mapReview(await api.updateResultsApi(token(), reviewId, { [itemId]: patch }));
	reviews.update((arr) => arr.map((r) => (r.id === reviewId ? updated : r)));
}

export function markReviewed(reviewId: string, itemId: string): void {
	void updateItemResult(reviewId, itemId, { reviewed: true, confidence: 0.99 });
}

export function openReview(id: string): void {
	activeReviewId.set(id);
	view.set('review');
}

export function goNewReview(): void {
	activeReviewId.set(null);
	stage.set('upload');
	view.set('new-review');
}

export async function createReview(policyMeta: Review['policyMeta'], strengths: string[] = []): Promise<Review> {
	const created = mapReview(await api.createReviewApi(token(), policyMeta, strengths));
	reviews.update((arr) => [created, ...arr]);
	activeReviewId.set(created.id);
	stage.set('review');
	return created;
}

export async function submitForApproval(reviewId: string, _note: string): Promise<void> {
	const updated = mapReview(await api.submitReviewApi(token(), reviewId));
	reviews.update((arr) => arr.map((r) => (r.id === reviewId ? updated : r)));
}

export async function approveAndPublish(reviewId: string, note?: string): Promise<void> {
	const updated = mapReview(await api.approveReviewApi(token(), reviewId, note ?? ''));
	reviews.update((arr) => arr.map((r) => (r.id === reviewId ? updated : r)));
	await loadLibrary();
}

export async function rejectPolicy(reviewId: string, note?: string): Promise<void> {
	const updated = mapReview(await api.rejectReviewApi(token(), reviewId, note ?? ''));
	reviews.update((arr) => arr.map((r) => (r.id === reviewId ? updated : r)));
}

// ── Checklist draft mutators ──
export async function loadDraft(): Promise<void> {
	const d = await api.getChecklistDraft(token()).catch(() => null);
	checklistDraft.set(d ? mapVersion(d) : null);
}

export async function saveDraft(data: unknown): Promise<void> {
	const saved = await api.saveChecklistDraft(token(), data);
	if (saved) checklistDraft.set(mapVersion(saved));
}

export async function startDraft(): Promise<void> {
	checklistDraft.set(mapVersion(await api.startChecklistDraft(token())));
}

export async function discardDraft(): Promise<void> {
	await api.discardChecklistDraft(token());
	checklistDraft.set(null);
}

export async function publishDraft(): Promise<{ ok: boolean; errors: string[] }> {
	try {
		const published = mapVersion(await api.publishChecklistDraft(token()));
		checklistVersions.update((arr) => [published, ...arr.map((v) => ({ ...v, status: 'archived' as const }))]);
		checklistDraft.set(null);
		return { ok: true, errors: [] };
	} catch (e) {
		return { ok: false, errors: [String(e)] };
	}
}

// ── Library popup helpers (unchanged) ──
export function openPolicyPopup(policy: LibraryPolicy): void {
	selectedPolicy.set(policy);
	policyPopupOpen.set(true);
}
export function closePolicyPopup(): void {
	policyPopupOpen.set(false);
}
