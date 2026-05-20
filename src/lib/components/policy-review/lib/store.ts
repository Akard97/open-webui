// Writable stores backing the Policy Review tool.
// Mirrors the React state machine in the design's app.jsx, plus
// localStorage persistence so an in-progress review survives a refresh.

import { writable, get, type Writable } from 'svelte/store';
import { browser } from '$app/environment';
import { SECTIONS } from './mocks';
import type { ChecklistItem, OEState, Section, Stage, ViewKey } from './types';

const STORAGE_KEY = 'osool.policyReview.v1';

interface PersistedState {
	sections: Section[];
	oeState: OEState;
	stage: Stage;
	view: ViewKey;
}

function freshInitial(): PersistedState {
	return {
		sections: structuredClone(SECTIONS),
		oeState: { status: 'idle', sentAt: null, decidedAt: null, note: '' },
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
				oeState: parsed.oeState ?? freshInitial().oeState,
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
export const oeState: Writable<OEState> = writable(initial.oeState);
export const stage: Writable<Stage> = writable(initial.stage);
export const view: Writable<ViewKey> = writable(initial.view);

// Transient (not persisted) — UI focus state.
export const picked: Writable<{ sectionId: string; n: number } | null> = writable(null);
export const drawerOpen: Writable<boolean> = writable(false);
export const oeModalOpen: Writable<boolean> = writable(false);

if (browser) {
	const persist = () => {
		const snapshot: PersistedState = {
			sections: get(sections),
			oeState: get(oeState),
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
	oeState.subscribe(persist);
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
	oeState.set({ status: 'idle', sentAt: null, decidedAt: null, note: '' });
	stage.set('upload');
}

export function submitToOE(note: string): void {
	const fmt = new Date().toLocaleString('en-GB', {
		day: '2-digit',
		month: 'short',
		hour: '2-digit',
		minute: '2-digit'
	});
	oeState.set({ status: 'pending', sentAt: fmt, decidedAt: null, note });
}

const SIM_NOTES: Record<'approved' | 'returned' | 'rejected', string> = {
	approved:
		'Excellent work — verdicts are well-supported. Policy is approved for issuance subject to corrective action on the four open gaps. Closure required within 30 days.',
	returned:
		'Please clarify the §6.3 procedural detail and ensure objective (iv) has a named owner. Resubmit once these are addressed.',
	rejected:
		'Mandatory gate T2 has not been adequately addressed (approval thresholds duplicate the DoA). Policy must be revised and re-reviewed before resubmission.'
};

export function simulateOEDecision(status: 'approved' | 'returned' | 'rejected'): void {
	const fmt = new Date().toLocaleString('en-GB', {
		day: '2-digit',
		month: 'short',
		hour: '2-digit',
		minute: '2-digit'
	});
	oeState.update((prev) => ({ ...prev, status, decidedAt: fmt, note: SIM_NOTES[status] }));
}

export function resetOE(): void {
	oeState.set({ status: 'idle', sentAt: null, decidedAt: null, note: '' });
}
