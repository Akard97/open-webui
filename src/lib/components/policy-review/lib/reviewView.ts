// Pure presentation logic for the Policy Review detail page.
// No SvelteKit/store imports — kept framework-free so it is unit-testable
// and shared by ReviewView.svelte and ReviewSummaryBand.svelte.

import type { ChecklistVersion, ItemResult, ReviewStatus } from './types';

export type ReviewMode = 'reviewer' | 'decide' | 'readonly';

// Which interaction mode the page is in, given review state + role.
// Order matters: a pending review for an approver is a DECISION, even for an
// admin who also satisfies canUseChecker.
export function resolveMode(
	status: ReviewStatus,
	canUseChecker: boolean,
	canApprove: boolean
): ReviewMode {
	if (status === 'pending' && canApprove) return 'decide';
	if ((status === 'draft' || status === 'rejected') && canUseChecker) return 'reviewer';
	return 'readonly';
}

// Items are editable only while the review is draft or rejected.
export function isLocked(status: ReviewStatus): boolean {
	return status !== 'draft' && status !== 'rejected';
}

export interface ResultCounts {
	compliant: number;
	'non-compliant': number;
	human: number;
	pending: number;
	total: number;
}

export function countResults(
	version: ChecklistVersion,
	results: Record<string, ItemResult>
): ResultCounts {
	const c: ResultCounts = { compliant: 0, 'non-compliant': 0, human: 0, pending: 0, total: 0 };
	version.sections.forEach((sec) =>
		sec.items.forEach((it) => {
			const r = results[it.id]?.result ?? 'pending';
			c[r] += 1;
			c.total += 1;
		})
	);
	return c;
}

export function openCount(c: ResultCounts): number {
	return c.human + c.pending;
}

export function resolvedCount(c: ResultCounts): number {
	return c.compliant + c['non-compliant'];
}

// Display number: sectionId 'PRP1', n 2 → '1.2'. Strips the PRP prefix.
export function itemNumber(sectionId: string, n: number): string {
	return `${sectionId.replace('PRP', '')}.${n}`;
}

export interface Gap {
	ref: string; // '1.4'
	title: string;
	theme: string; // 'T1'
	sectionId: string; // 'PRP1'
	n: number;
	comment?: string;
}

// Non-compliant items, ranked by the version's theme order (unknown themes
// last), capped at `limit`.
export function topGaps(
	version: ChecklistVersion,
	results: Record<string, ItemResult>,
	limit = 5
): Gap[] {
	const themeRank = new Map(version.themes.map((t, i) => [t.id, i]));
	const gaps: Gap[] = [];
	version.sections.forEach((sec) =>
		sec.items.forEach((it) => {
			const r = results[it.id];
			if ((r?.result ?? 'pending') === 'non-compliant') {
				gaps.push({
					ref: itemNumber(sec.id, it.n),
					title: it.text,
					theme: sec.theme,
					sectionId: sec.id,
					n: it.n,
					comment: r?.comment
				});
			}
		})
	);
	const rank = (id: string) => themeRank.get(id) ?? Number.MAX_SAFE_INTEGER;
	gaps.sort((a, b) => rank(a.theme) - rank(b.theme));
	return gaps.slice(0, limit);
}

// Collapsed-by-default disclosure map. This deliberately inverts the legacy
// behaviour where a missing key meant "open"; every PRP group starts closed.
export function initOpenMap(version: ChecklistVersion, open = false): Record<string, boolean> {
	const m: Record<string, boolean> = {};
	version.sections.forEach((s) => (m[s.id] = open));
	return m;
}
