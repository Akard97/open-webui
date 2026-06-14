// Score + verdict calculation for the Policy Review tool.
// Port of scoring.js from the PRP-2 design handoff.
//
// Per-theme score = compliant / (compliant + non-compliant).
// `human` items are held aside until resolved.
// T1 + T2 are mandatory gates (threshold 85). Overall is the weight-weighted
// average of theme scores; verdict applies the gate + overall rules.

import type { Section, Theme, Verdict } from './types';

interface ThemeBucket {
	total: number;
	yes: number;
	no: number;
	human: number;
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

export function computeScores(sections: Section[], themes: Theme[]): ScoreResult {
	const byTheme: Record<string, ThemeBucket> = {};
	themes.forEach((t) => {
		byTheme[t.id] = { total: 0, yes: 0, no: 0, human: 0, items: 0 };
	});

	sections.forEach((sec) => {
		sec.items.forEach((it) => {
			const t = byTheme[sec.theme];
			if (!t) return;
			t.items += 1;
			if (it.result === 'compliant') {
				t.yes += 1;
				t.total += 1;
			} else if (it.result === 'non-compliant') {
				t.no += 1;
				t.total += 1;
			} else if (it.result === 'human') {
				t.human += 1;
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

	const gatesPass = themeRows.filter((t) => t.gate).every((t) => t.pct >= (t.threshold || 85));
	const humanItemsRemain = themeRows.some((t) => t.human > 0);

	let verdict: Verdict;
	if (humanItemsRemain) {
		verdict = { key: 'draft', label: 'Pending review', reason: 'Awaiting human-judgement items' };
	} else if (overall >= 85 && gatesPass) {
		verdict = { key: 'approved', label: 'Approved', reason: 'Meets all requirements' };
	} else if (overall >= 70 && gatesPass) {
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
