// Writable stores backing the Policy Review tool.
// Mirrors the React state machine in the design's app.jsx, plus
// localStorage persistence so an in-progress review survives a refresh.

import { writable, get, derived, type Writable } from 'svelte/store';
import { browser } from '$app/environment';
import { SECTIONS } from './mocks';
import type { ApprovalState, ChecklistItem, Section, Stage, ViewKey } from './types';
import { user } from '$lib/stores';

const STORAGE_KEY = 'osool.policyReview.v2';

interface PersistedState {
	sections: Section[];
	approval: ApprovalState;
	stage: Stage;
	view: ViewKey;
}

function freshInitial(): PersistedState {
	return {
		sections: structuredClone(SECTIONS),
		approval: { status: 'idle', sentAt: null, decidedAt: null, decidedBy: null, note: '' },
		stage: 'upload',
		view: 'all-policies'
	};
}

function loadInitial(): PersistedState {
	if (!browser) return freshInitial();
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		if (raw) {
			const parsed = JSON.parse(raw) as Partial<PersistedState>;
			return {
				sections: parsed.sections ?? freshInitial().sections,
				approval: parsed.approval ?? freshInitial().approval,
				stage: parsed.stage ?? 'upload',
				view: parsed.view ?? 'all-policies'
			};
		}
	} catch {
		// Corrupt storage — fall back to fresh state.
	}
	return freshInitial();
}

const initial = loadInitial();

export const sections: Writable<Section[]> = writable(initial.sections);
export const approval: Writable<ApprovalState> = writable(initial.approval);
export const stage: Writable<Stage> = writable(initial.stage);
export const view: Writable<ViewKey> = writable(initial.view);

// Access gate: only the OE team (or admins) may run the checker workflow
// (upload, scan, review, submit for approval). Everyone else sees the Library only.
// Mirrors the feature-permission idiom used across Osool (e.g. features.notes).
export const canUseChecker = derived(
	user,
	($u) => $u?.role === 'admin' || ($u?.permissions?.features?.policy_checker ?? false)
);

// Approver gate: OE leads (or admins) who make the final approve/publish or reject
// decision on a submitted review. Maker-checker — distinct from canUseChecker.
export const canApprove = derived(
	user,
	($u) => $u?.role === 'admin' || ($u?.permissions?.features?.policy_approver ?? false)
);

// Transient (not persisted) — UI focus state.
export const picked: Writable<{ sectionId: string; n: number } | null> = writable(null);
export const drawerOpen: Writable<boolean> = writable(false);
export const submitModalOpen: Writable<boolean> = writable(false);

// Policy Library — selected policy + popup open state.
export const policyPopupOpen: Writable<boolean> = writable(false);
export const selectedPolicy: Writable<import('./types').LibraryPolicy | null> = writable(null);

if (browser) {
	const persist = () => {
		const snapshot: PersistedState = {
			sections: get(sections),
			approval: get(approval),
			stage: get(stage),
			view: get(view)
		};
		try {
			localStorage.setItem(STORAGE_KEY, JSON.stringify(snapshot));
		} catch {
			// Quota errors etc. are non-fatal — review state stays in memory.
		}
	};
	sections.subscribe(persist);
	approval.subscribe(persist);
	stage.subscribe(persist);
	view.subscribe(persist);
}

// ─── Mutators ───────────────────────────────────────────────────────────────

export function updateItem(
	sectionId: string,
	n: number,
	patch: Partial<ChecklistItem>
): void {
	sections.update((arr) =>
		arr.map((sec) =>
			sec.id === sectionId
				? { ...sec, items: sec.items.map((it) => (it.n === n ? { ...it, ...patch } : it)) }
				: sec
		)
	);
}

export function markReviewed(sectionId: string, n: number): void {
	updateItem(sectionId, n, { reviewed: true, confidence: 0.99 });
}

export function resetReview(): void {
	sections.set(structuredClone(SECTIONS));
	approval.set({ status: 'idle', sentAt: null, decidedAt: null, decidedBy: null, note: '' });
	stage.set('upload');
}

function stamp(): string {
	return new Date().toLocaleString('en-GB', {
		day: '2-digit',
		month: 'short',
		hour: '2-digit',
		minute: '2-digit'
	});
}

// OE reviewer hands a completed review to an OE approver.
export function submitForApproval(note: string): void {
	approval.set({ status: 'pending', sentAt: stamp(), decidedAt: null, decidedBy: null, note });
}

const DEFAULT_APPROVE_NOTE = 'Approved for issuance and published to the policy library.';
const DEFAULT_REJECT_NOTE =
	'Rejected — policy must be revised and re-reviewed before it can be resubmitted.';

// OE approver decisions (maker-checker). Records who decided and when.
export function approveAndPublish(note?: string): void {
	const by = get(user)?.name ?? 'OE Approver';
	approval.update((prev) => ({
		...prev,
		status: 'approved',
		decidedAt: stamp(),
		decidedBy: by,
		note: note?.trim() || DEFAULT_APPROVE_NOTE
	}));
}

export function rejectPolicy(note?: string): void {
	const by = get(user)?.name ?? 'OE Approver';
	approval.update((prev) => ({
		...prev,
		status: 'rejected',
		decidedAt: stamp(),
		decidedBy: by,
		note: note?.trim() || DEFAULT_REJECT_NOTE
	}));
}

export function resetApproval(): void {
	approval.set({ status: 'idle', sentAt: null, decidedAt: null, decidedBy: null, note: '' });
}

// ─── Policy Library popup helpers ──────────────────────────────────────────

export function openPolicyPopup(policy: import('./types').LibraryPolicy): void {
	selectedPolicy.set(policy);
	policyPopupOpen.set(true);
}

export function closePolicyPopup(): void {
	policyPopupOpen.set(false);
	// Keep selectedPolicy set so the close animation has content to render
	// against; the next openPolicyPopup() overwrites it.
}
