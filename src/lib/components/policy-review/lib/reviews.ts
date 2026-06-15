// Pure helpers for summarizing a Review for list/landing surfaces.

import type { ChecklistVersion, Review, ReviewStatus, VerdictKey } from './types';
import { computeScores } from './scoring';

export interface ReviewSummary {
	overall: number;
	verdictKey: VerdictKey;
	verdictLabel: string;
	gatesPass: boolean;
	open: number; // unresolved items (human + pending) blocking a final verdict
}

// Resolve the checklist version a review was assessed against (its snapshot),
// falling back to the active version, then the first known version.
export function versionFor(
	review: Review,
	versions: ChecklistVersion[]
): ChecklistVersion | undefined {
	return (
		versions.find((v) => v.id === review.checklistVersionId) ??
		versions.find((v) => v.status === 'active') ??
		versions[0]
	);
}

export function summarizeReview(review: Review, version: ChecklistVersion): ReviewSummary {
	const s = computeScores(version, review.results);
	const open = s.themeRows.reduce((a, t) => a + t.human + t.pending, 0);
	return {
		overall: s.overall,
		verdictKey: s.verdict.key,
		verdictLabel: s.verdict.label,
		gatesPass: s.gatesPass,
		open
	};
}

export const REVIEW_STATUS_META: Record<ReviewStatus, { label: string; tone: string }> = {
	draft: { label: 'Draft', tone: 'muted' },
	pending: { label: 'Pending approval', tone: 'info' },
	approved: { label: 'Approved', tone: 'ok' },
	rejected: { label: 'Returned', tone: 'bad' }
};
