// Score + verdict calculation for the Policy Review tool.
//
// Per-theme score = compliant / (compliant + non-compliant).
// `human` and missing/`pending` items are held aside (not scored, but
// they block a final verdict). Gate themes must clear their threshold.
// Overall is the weight-weighted average of theme scores.

import type { ChecklistVersion, ItemResult, Theme, Verdict } from './types';

interface ThemeBucket {
	total: number;
	yes: number;
	no: number;
	human: number;
	pending: number;
	items: number;
}

export type ThemeRow = Theme & ThemeBucket & { pct: number };

export interface ScoreResult {
	themeRows: ThemeRow[];
	overall: number;
	gatesPass: boolean;
	verdict: Verdict;
	humanItemsRemain: boolean;
}

export function computeScores(
	version: ChecklistVersion,
	results: Record<string, ItemResult>
): ScoreResult {
	const { themes, sections, verdictBands } = version;
	const byTheme: Record<string, ThemeBucket> = {};
	themes.forEach((t) => {
		byTheme[t.id] = { total: 0, yes: 0, no: 0, human: 0, pending: 0, items: 0 };
	});

	sections.forEach((sec) => {
		const bucket = byTheme[sec.theme];
		if (!bucket) return;
		sec.items.forEach((item) => {
			bucket.items += 1;
			const result = results[item.id]?.result ?? 'pending';
			if (result === 'compliant') {
				bucket.yes += 1;
				bucket.total += 1;
			} else if (result === 'non-compliant') {
				bucket.no += 1;
				bucket.total += 1;
			} else if (result === 'human') {
				bucket.human += 1;
			} else {
				bucket.pending += 1;
			}
		});
	});

	const themeRows: ThemeRow[] = themes.map((t) => {
		const s = byTheme[t.id];
		const pct = s.total > 0 ? Math.round((s.yes / s.total) * 100) : 0;
		return { ...t, ...s, pct };
	});

	let weighted = 0;
	let weightTotal = 0;
	themeRows.forEach((t) => {
		if (t.total > 0) {
			weighted += t.pct * t.weight;
			weightTotal += t.weight;
		}
	});
	const overall = weightTotal > 0 ? Math.round(weighted / weightTotal) : 0;

	const gatesPass = themeRows.filter((t) => t.gate).every((t) => t.pct >= t.threshold);
	const humanItemsRemain = themeRows.some((t) => t.human > 0 || t.pending > 0);

	let verdict: Verdict;
	if (humanItemsRemain) {
		verdict = { key: 'draft', label: 'Pending review', reason: 'Awaiting unresolved items' };
	} else if (overall >= verdictBands.approved && gatesPass) {
		verdict = { key: 'approved', label: 'Approved', reason: 'Meets all requirements' };
	} else if (overall >= verdictBands.conditional && gatesPass) {
		verdict = {
			key: 'conditional',
			label: 'Conditionally Approved',
			reason: 'Minimum threshold met — CAP required'
		};
	} else {
		verdict = {
			key: 'rejected',
			label: 'Rejected',
			reason: gatesPass ? 'Below minimum overall threshold' : 'Mandatory gate failed'
		};
	}

	return { themeRows, overall, gatesPass, verdict, humanItemsRemain };
}
